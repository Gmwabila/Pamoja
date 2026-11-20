import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    Notification,
    NotificationPushDelivery,
    PushSubscription,
    User,
)
from core.notifications import generate_notifications
from core.push import send_push_to_subscription

logger = logging.getLogger(__name__)

PREFERENCE_FIELDS = {
    "task": "reminders",
    "planning": "daily_planning_notifications",
    "milestone": "goal_notifications",
}


class Command(BaseCommand):
    help = "Generate and deliver PAMOJA push notifications."

    def handle(self, *args, **options):
        generated_users = 0
        delivered = 0
        failed = 0

        # Generate notifications for all users.
        for user in User.objects.iterator():
            try:
                generate_notifications(user)
                generated_users += 1
            except Exception:
                logger.exception(
                    "Notification generation failed for user %s",
                    user.pk,
                )

        # Allow delayed scheduler runs to recover recent notifications.
        cutoff = timezone.now() - timedelta(hours=24)

        notifications = (
            Notification.objects
            .filter(created_at__gte=cutoff)
            .select_related("user", "user__profile")
            .order_by("id")
        )

        for notification in notifications.iterator():
            profile = notification.user.profile
            preference = PREFERENCE_FIELDS.get(notification.kind)

            # Respect the user's current notification preferences.
            if not preference or not getattr(profile, preference, False):
                continue


            # Deliver notifications only on the user's local date.
            local_now = timezone.localtime(
                timezone.now(),
                ZoneInfo(profile.timezone),
            )
            today = local_now.date()

            if notification.kind == "planning":
                if notification.event_key != f"planning:{today}":
                    continue

                # Respect the user's chosen planning time.
                if (
                    local_now.time().replace(tzinfo=None)
                    < profile.daily_planning_time
                ):
                    continue

            elif notification.kind == "task":
                if not notification.event_key.endswith(f":{today}"):
                    continue

            elif notification.kind == "milestone":
                if not notification.event_key.startswith(
                    f"milestone:{today}:"
                ):
                    continue

            subscriptions = PushSubscription.objects.filter(
                user=notification.user
            )

            for subscription in subscriptions.iterator():
                delivery, _ = NotificationPushDelivery.objects.get_or_create(
                    notification=notification,
                    subscription=subscription,
                )

                if delivery.sent_at is not None:
                    continue

                # Claim this delivery so concurrent jobs do not send it
                # at the same time on databases supporting row locks.
                with transaction.atomic():
                    delivery = (
                        NotificationPushDelivery.objects
                        .select_for_update()
                        .get(pk=delivery.pk)
                    )

                    if delivery.sent_at is not None:
                        continue

                    delivery.attempts += 1
                    delivery.save(update_fields=["attempts"])

                    success = send_push_to_subscription(
                        subscription,
                        notification.title,
                        notification.message,
                        f"notification-{notification.pk}",
                    )

                    if success:
                        delivery.sent_at = timezone.now()
                        delivery.save(update_fields=["sent_at"])
                        delivered += 1
                    else:
                        failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {generated_users} users; "
                f"delivered {delivered} device notifications; "
                f"failed {failed}."
            )
        )

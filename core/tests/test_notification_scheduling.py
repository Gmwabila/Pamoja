
from datetime import datetime, time, timezone as dt_timezone
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.models import (
    Notification,
    NotificationPushDelivery,
    Profile,
    PushSubscription,
    User,
)
from core.notifications import generate_notifications


def utc_time(hour, minute):
    return datetime(
        2026, 11, 19,
        hour, minute,
        tzinfo=dt_timezone.utc,
    )


class NotificationSchedulingTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="scheduling_test@example.com",
            password="TestPassword123!",
        )

        self.profile, _ = Profile.objects.get_or_create(
            user=self.user,
        )

        self.profile.timezone = "America/Chicago"
        self.profile.daily_planning_time = time(8, 0)
        self.profile.daily_planning_notifications = True
        self.profile.reminders = False
        self.profile.goal_notifications = False
        self.profile.save()

    def planning_notifications(self):
        return Notification.objects.filter(
            user=self.user,
            kind="planning",
        )

    def test_yesterdays_task_notification_is_not_pushed(self):
        self.profile.reminders = True
        self.profile.daily_planning_notifications = False
        self.profile.save()

        subscription = PushSubscription.objects.create(
            user=self.user,
            endpoint="https://example.com/push/old-task",
            p256dh="test-key",
            auth="test-auth",
        )

        old_notification = Notification.objects.create(
            user=self.user,
            kind="task",
            event_key="task:999:today:2026-11-18",
            title="Task due today",
            message="An old reminder.",
        )

        # Make the notification recent enough for the
        # 24-hour delivery query.
        Notification.objects.filter(
            pk=old_notification.pk
        ).update(created_at=utc_time(14, 0))

        with patch(
            "django.utils.timezone.now",
            return_value=utc_time(14, 5),
        ):
            with patch(
                "core.management.commands.send_notifications."
                "send_push_to_subscription",
                return_value=True,
            ) as send_push:
                call_command("send_notifications")

        send_push.assert_not_called()


    def test_no_planning_reminder_before_selected_time(self):
        # 13:59 UTC = 7:59 AM in Chicago.
        with patch(
            "django.utils.timezone.now",
            return_value=utc_time(13, 59),
        ):
            generate_notifications(self.user)

        self.assertEqual(
            self.planning_notifications().count(),
            0,
        )

    def test_planning_reminder_after_selected_time_only_once(self):
        # 14:05 UTC = 8:05 AM in Chicago.
        with patch(
            "django.utils.timezone.now",
            return_value=utc_time(14, 5),
        ):
            generate_notifications(self.user)
            generate_notifications(self.user)

        self.assertEqual(
            self.planning_notifications().count(),
            1,
        )

        self.assertEqual(
            self.planning_notifications().first().event_key,
            "planning:2026-11-19",
        )

    def test_planning_works_without_task_reminders(self):
        self.assertFalse(self.profile.reminders)

        with patch(
            "django.utils.timezone.now",
            return_value=utc_time(14, 10),
        ):
            generate_notifications(self.user)

        self.assertEqual(
            self.planning_notifications().count(),
            1,
        )

    def test_planning_respects_user_timezone(self):
        self.profile.timezone = "America/Los_Angeles"
        self.profile.save()

        # 14:05 UTC = 6:05 AM in Los Angeles.
        with patch(
            "django.utils.timezone.now",
            return_value=utc_time(14, 5),
        ):
            generate_notifications(self.user)

        self.assertEqual(
            self.planning_notifications().count(),
            0,
        )

        # 16:05 UTC = 8:05 AM in Los Angeles.
        with patch(
            "django.utils.timezone.now",
            return_value=utc_time(16, 5),
        ):
            generate_notifications(self.user)

        self.assertEqual(
            self.planning_notifications().count(),
            1,
        )

    def test_push_delivery_occurs_once_per_device(self):
        for number in (1, 2):
            PushSubscription.objects.create(
                user=self.user,
                endpoint=f"https://example.com/push/{number}",
                p256dh=f"test-key-{number}",
                auth=f"test-auth-{number}",
            )

        with patch(
            "core.management.commands.send_notifications."
            "send_push_to_subscription",
            return_value=True,
        ) as send_push:

            # Before 8 AM: no push.
            with patch(
                "django.utils.timezone.now",
                return_value=utc_time(13, 59),
            ):
                call_command("send_notifications")

            self.assertEqual(send_push.call_count, 0)

            # After 8 AM: one push per device.
            with patch(
                "django.utils.timezone.now",
                return_value=utc_time(14, 5),
            ):
                call_command("send_notifications")
                call_command("send_notifications")

            self.assertEqual(send_push.call_count, 2)

        self.assertEqual(
            NotificationPushDelivery.objects.filter(
                sent_at__isnull=False,
            ).count(),
            2,
        )

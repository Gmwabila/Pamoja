
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import (
    Notification,
    NotificationPushDelivery,
    Profile,
    PushSubscription,
)


class PushDeliveryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="push_test@example.com",
            password="test-password-123",
        )

        self.profile, _ = Profile.objects.get_or_create(
            user=self.user,
        )
        self.profile.reminders = True
        self.profile.save()


        # Match the event-key format used by the scheduler.
        local_today = timezone.localtime(
            timezone.now(),
            ZoneInfo(self.profile.timezone),
        ).date()

        self.notification = Notification.objects.create(
            user=self.user,
            kind="task",
            title="Test reminder",
            message="Your task is due today.",
            event_key=f"task:999:today:{local_today}",
        )


        for number in (1, 2):
            PushSubscription.objects.create(
                user=self.user,
                endpoint=f"https://example.com/push/device{number}",
                p256dh=f"test-key-{number}",
                auth=f"test-auth-{number}",
            )

    @patch(
        "core.management.commands.send_notifications."
        "send_push_to_subscription",
        return_value=True,
    )
    @patch(
        "core.management.commands.send_notifications."
        "generate_notifications",
    )
    def test_sends_to_each_device_once(self, generate, send):
        call_command("send_notifications")
        self.assertEqual(send.call_count, 2)

        self.assertEqual(
            NotificationPushDelivery.objects.filter(
                notification=self.notification,
                sent_at__isnull=False,
            ).count(),
            2,
        )

        call_command("send_notifications")
        self.assertEqual(send.call_count, 2)

    @patch(
        "core.management.commands.send_notifications."
        "send_push_to_subscription",
        return_value=True,
    )
    @patch(
        "core.management.commands.send_notifications."
        "generate_notifications",
    )
    def test_disabled_reminders_are_not_sent(self, generate, send):
        self.profile.reminders = False
        self.profile.save()

        call_command("send_notifications")
        send.assert_not_called()

    @patch(
        "core.management.commands.send_notifications."
        "send_push_to_subscription",
        side_effect=[True, False, True],
    )
    @patch(
        "core.management.commands.send_notifications."
        "generate_notifications",
    )
    def test_failed_device_is_retried(self, generate, send):
        call_command("send_notifications")

        self.assertEqual(
            NotificationPushDelivery.objects.filter(
                notification=self.notification,
                sent_at__isnull=False,
            ).count(),
            1,
        )

        call_command("send_notifications")

        self.assertEqual(send.call_count, 3)
        self.assertEqual(
            NotificationPushDelivery.objects.filter(
                notification=self.notification,
                sent_at__isnull=False,
            ).count(),
            2,
        )

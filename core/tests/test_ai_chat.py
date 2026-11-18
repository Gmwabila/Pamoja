import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from core.ai_chat import rate_limit_exceeded
from core.models import AIConversation, AIMessage, AIUsageGlobal, AIUsageLimit


User = get_user_model()


class AIChatSecurityTests(TestCase):

    def setUp(self):
        self.user_a = User.objects.create_user(
            email="ai-user-a@example.com",
            password="TestPassword123!"
        )
        self.user_b = User.objects.create_user(
            email="ai-user-b@example.com",
            password="TestPassword123!"
        )

        self.conversation = AIConversation.objects.create(
            user=self.user_a,
            title="Private conversation"
        )

        AIMessage.objects.create(
            conversation=self.conversation,
            role="user",
            content="This is private information."
        )

    def test_owner_can_open_conversation(self):
        self.client.force_login(self.user_a)

        response = self.client.get(
            reverse(
                "chat_conversation_detail",
                args=[self.conversation.pk]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["messages"][0]["text"],
            "This is private information."
        )

    def test_other_user_cannot_open_conversation(self):
        self.client.force_login(self.user_b)

        response = self.client.get(
            reverse(
                "chat_conversation_detail",
                args=[self.conversation.pk]
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_see_conversation_in_list(self):
        self.client.force_login(self.user_b)

        response = self.client.get(
            reverse("chat_conversations")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["conversations"],
            []
        )

    def test_other_user_cannot_delete_conversation(self):
        self.client.force_login(self.user_b)

        response = self.client.post(
            reverse(
                "chat_conversation_delete",
                args=[self.conversation.pk]
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            AIConversation.objects.filter(
                pk=self.conversation.pk
            ).exists()
        )

    def test_owner_can_delete_conversation_and_messages(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse(
                "chat_conversation_delete",
                args=[self.conversation.pk]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AIConversation.objects.filter(
                pk=self.conversation.pk
            ).exists()
        )
        self.assertFalse(
            AIMessage.objects.filter(
                conversation_id=self.conversation.pk
            ).exists()
        )

    def test_other_user_cannot_send_to_private_conversation(self):
        self.client.force_login(self.user_b)

        with patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "test-only-key"}
        ):
            response = self.client.post(
                reverse("chat_message"),
                data=json.dumps({
                    "message": "Access another user's chat",
                    "conversation_id": self.conversation.pk
                }),
                content_type="application/json"
            )

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_read_conversation(self):
        response = self.client.get(
            reverse(
                "chat_conversation_detail",
                args=[self.conversation.pk]
            )
        )

        self.assertEqual(response.status_code, 302)


class AIUsageLimitTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="usage-test@example.com",
            password="TestPassword123!"
        )
        self.start = 1800000000

    def test_ten_messages_per_minute(self):
        with patch(
            "core.ai_chat.time.time",
            return_value=self.start
        ):
            for _ in range(10):
                self.assertFalse(
                    rate_limit_exceeded(self.user.pk)
                )

            self.assertTrue(
                rate_limit_exceeded(self.user.pk)
            )

        usage = AIUsageLimit.objects.get(user=self.user)
        self.assertEqual(usage.minute_count, 10)

    def test_forty_messages_per_day(self):
        # Four separate minutes, ten requests each.
        for minute in range(4):
            with patch(
                "core.ai_chat.time.time",
                return_value=self.start + minute * 60
            ):
                for _ in range(10):
                    self.assertFalse(
                        rate_limit_exceeded(self.user.pk)
                    )

        # A new minute cannot bypass the daily limit.
        with patch(
            "core.ai_chat.time.time",
            return_value=self.start + 240
        ):
            self.assertTrue(
                rate_limit_exceeded(self.user.pk)
            )

        usage = AIUsageLimit.objects.get(user=self.user)
        self.assertEqual(usage.day_count, 40)

    def test_new_minute_resets_minute_limit(self):
        with patch(
            "core.ai_chat.time.time",
            return_value=self.start
        ):
            for _ in range(10):
                rate_limit_exceeded(self.user.pk)

        with patch(
            "core.ai_chat.time.time",
            return_value=self.start + 60
        ):
            self.assertFalse(
                rate_limit_exceeded(self.user.pk)
            )

        usage = AIUsageLimit.objects.get(user=self.user)
        self.assertEqual(usage.minute_count, 1)
        self.assertEqual(usage.day_count, 11)

    def test_users_have_separate_limits(self):
        other_user = User.objects.create_user(
            email="other-usage@example.com",
            password="TestPassword123!"
        )

        # Temporarily increase the global minute limit
        # to test individual user limits independently.
        with patch(
            "core.ai_chat.GLOBAL_MINUTE_LIMIT", 20
        ), patch(
            "core.ai_chat.time.time",
            return_value=self.start
        ):
            for _ in range(10):
                self.assertFalse(
                    rate_limit_exceeded(self.user.pk)
                )

            # User A has reached their personal limit.
            self.assertTrue(
                rate_limit_exceeded(self.user.pk)
            )

            # User B still has their own allowance.
            self.assertFalse(
                rate_limit_exceeded(other_user.pk)
            )


class AIGlobalUsageTests(TestCase):

    def test_rolling_limit_blocks_minute_boundary_burst(self):
        start = self.now + 59

        # Fill the global allowance just before a
        # calendar-minute boundary.
        with patch("core.ai_chat.time.time", return_value=start):
            for i in range(10):
                self.assertFalse(
                    rate_limit_exceeded(self.users[i % 4].pk)
                )

        # Crossing into the next minute must NOT
        # immediately reset the global allowance.
        with patch("core.ai_chat.time.time", return_value=start + 2):
            self.assertTrue(
                rate_limit_exceeded(self.users[0].pk)
            )

        # Once 60 seconds have elapsed, requests
        # from the original burst have expired.
        with patch("core.ai_chat.time.time", return_value=start + 60):
            self.assertFalse(
                rate_limit_exceeded(self.users[0].pk)
            )

        global_usage = AIUsageGlobal.objects.get(
            day_window=start // 86400
        )

        self.assertEqual(global_usage.minute_count, 1)
        self.assertEqual(global_usage.request_count, 11)

    def test_global_minute_limit_across_users(self):
        with patch(
            "core.ai_chat.time.time",
            return_value=self.now
        ):
            for i in range(10):
                user = self.users[i % 4]
                self.assertFalse(
                    rate_limit_exceeded(user.pk)
                )

            self.assertTrue(
                rate_limit_exceeded(self.users[3].pk)
            )

        global_usage = AIUsageGlobal.objects.get(
            day_window=self.now // 86400
        )

        self.assertEqual(global_usage.minute_count, 10)
        self.assertEqual(global_usage.request_count, 10)

    def test_global_minute_limit_resets(self):
        with patch(
            "core.ai_chat.GLOBAL_MINUTE_LIMIT", 2
        ):
            with patch(
                "core.ai_chat.time.time",
                return_value=self.now
            ):
                self.assertFalse(
                    rate_limit_exceeded(self.users[0].pk)
                )
                self.assertFalse(
                    rate_limit_exceeded(self.users[1].pk)
                )
                self.assertTrue(
                    rate_limit_exceeded(self.users[2].pk)
                )

            with patch(
                "core.ai_chat.time.time",
                return_value=self.now + 60
            ):
                self.assertFalse(
                    rate_limit_exceeded(self.users[2].pk)
                )

        global_usage = AIUsageGlobal.objects.get(
            day_window=self.now // 86400
        )

        self.assertEqual(global_usage.minute_count, 1)
        self.assertEqual(global_usage.request_count, 3)
        
    def setUp(self):
        self.users = [
            User.objects.create_user(
                email=f"global-user-{i}@example.com",
                password="TestPassword123!",
            )
            for i in range(4)
        ]
        self.now = 1800000000

    def test_global_limit_applies_across_users(self):
        with patch(
            "core.ai_chat.GLOBAL_DAILY_LIMIT", 3
        ), patch(
            "core.ai_chat.time.time",
            return_value=self.now
        ):
            for user in self.users[:3]:
                self.assertFalse(
                    rate_limit_exceeded(user.pk)
                )

            self.assertTrue(
                rate_limit_exceeded(self.users[3].pk)
            )

        global_usage = AIUsageGlobal.objects.get(
            day_window=self.now // 86400
        )

        self.assertEqual(global_usage.request_count, 3)

    def test_global_limit_resets_next_day(self):
        with patch(
            "core.ai_chat.GLOBAL_DAILY_LIMIT", 1
        ):
            with patch(
                "core.ai_chat.time.time",
                return_value=self.now
            ):
                self.assertFalse(
                    rate_limit_exceeded(self.users[0].pk)
                )
                self.assertTrue(
                    rate_limit_exceeded(self.users[1].pk)
                )

            with patch(
                "core.ai_chat.time.time",
                return_value=self.now + 86400
            ):
                self.assertFalse(
                    rate_limit_exceeded(self.users[1].pk)
                )

        self.assertEqual(
            AIUsageGlobal.objects.count(), 2
        )

    def test_rejected_request_does_not_charge_user(self):
        with patch(
            "core.ai_chat.GLOBAL_DAILY_LIMIT", 1
        ), patch(
            "core.ai_chat.time.time",
            return_value=self.now
        ):
            self.assertFalse(
                rate_limit_exceeded(self.users[0].pk)
            )

            self.assertTrue(
                rate_limit_exceeded(self.users[1].pk)
            )

        self.assertFalse(
            AIUsageLimit.objects.filter(
                user=self.users[1]
            ).exists()
        )


class AIConcurrentUsageTests(TransactionTestCase):

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_requests_respect_global_limit(self):
        users = [
            User.objects.create_user(
                email=f"concurrent-{i}@example.com",
                password="TestPassword123!",
            )
            for i in range(6)
        ]

        barrier = Barrier(6)
        now = 1800000000

        def attempt(user_id):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return rate_limit_exceeded(user_id)
            finally:
                connections.close_all()

        with patch(
            "core.ai_chat.GLOBAL_DAILY_LIMIT", 3
        ), patch(
            "core.ai_chat.time.time",
            return_value=now
        ):
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(
                    pool.map(
                        attempt,
                        [user.pk for user in users]
                    )
                )

        self.assertEqual(results.count(False), 3)
        self.assertEqual(results.count(True), 3)

        global_usage = AIUsageGlobal.objects.get(
            day_window=now // 86400
        )

        self.assertEqual(global_usage.request_count, 3)

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_requests_respect_minute_limit(self):
        users = [
            User.objects.create_user(
                email=f"minute-user-{i}@example.com",
                password="TestPassword123!",
            )
            for i in range(6)
        ]

        barrier = Barrier(6)
        now = 1800000000

        def attempt(user_id):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return rate_limit_exceeded(user_id)
            finally:
                connections.close_all()

        with patch(
            "core.ai_chat.GLOBAL_MINUTE_LIMIT", 3
        ), patch(
            "core.ai_chat.time.time",
            return_value=now
        ):
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(
                    pool.map(attempt, [user.pk for user in users])
                )

        self.assertEqual(results.count(False), 3)
        self.assertEqual(results.count(True), 3)

        global_usage = AIUsageGlobal.objects.get(
            day_window=now // 86400
        )

        self.assertEqual(global_usage.minute_count, 3)
        self.assertEqual(global_usage.request_count, 3)

"""Guided task creation should never save without explicit user approval."""
import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.app_knowledge import PAMOJA_APP_GUIDE
from core.models import Profile, Task

User = get_user_model()


class AITaskGuideTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="guided-task@example.com", password="TestPassword123!"
        )
        Profile.objects.create(user=self.user, timezone="UTC", onboarded=True)
        self.client.force_login(self.user)

    def test_chat_has_guided_task_form_and_help_action(self):
        response = self.client.get(reverse("chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ai-task-guide"')
        self.assertContains(response, 'id="ai-help-start"')
        self.assertContains(response, 'name="title"')

    def test_prefill_does_not_save_until_user_submits(self):
        response = self.client.get(reverse("task_add"), {
            "title": "Review algorithms",
            "space": "education",
            "due_date": "2026-11-25",
            "priority": "high",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)
        form = response.context["form"]
        self.assertEqual(form.initial["title"], "Review algorithms")
        self.assertEqual(form.initial["space"], "education")
        self.assertEqual(form.initial["due_date"], date(2026, 11, 25))
        self.assertEqual(form.initial["priority"], "high")

    def test_invalid_prefill_is_ignored(self):
        response = self.client.get(reverse("task_add"), {
            "title": "x" * 200,
            "space": "not-a-space",
            "due_date": "not-a-date",
            "priority": "urgent",
            "due_time": "not-a-time",
        })
        self.assertEqual(response.status_code, 200)
        initial = response.context["form"].initial
        self.assertNotIn("title", initial)
        self.assertEqual(initial["space"], "planning")
        self.assertEqual(initial["priority"], "normal")
        self.assertNotIn("due_time", initial)
        self.assertEqual(Task.objects.count(), 0)

    def test_post_creates_task_for_current_user_only(self):
        response = self.client.post(reverse("task_add"), {
            "title": "Review algorithms",
            "space": "education",
            "due_date": "2026-11-25",
            "due_time_0": "",
            "due_time_1": "",
            "due_time_2": "",
            "priority": "high",
        })
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get()
        self.assertEqual(task.user, self.user)
        self.assertEqual(task.title, "Review algorithms")
        self.assertEqual(task.priority, "high")

    def test_app_guide_has_real_routes_and_no_auto_save_claim(self):
        self.assertIn("/tasks/new/", PAMOJA_APP_GUIDE)
        self.assertIn("/notifications/", PAMOJA_APP_GUIDE)
        self.assertIn("explicitly approves", PAMOJA_APP_GUIDE)

    def test_gemini_receives_official_app_guide(self):
        """The app guide is sent as system context, not as user content."""
        self.client.force_login(self.user)
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps({
                    "candidates": [{
                        "content": {"parts": [{"text": "Open the Planner."}]}
                    }]
                }).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["request"] = json.loads(request.data)
            return FakeResponse()

        with patch.dict("os.environ", {
            "GEMINI_API_KEY": "test-only-key",
            "PAMOJA_AI_TESTING_ONLY": "false",
        }), patch("core.ai_chat.urlopen", side_effect=fake_urlopen):
            response = self.client.post(
                reverse("chat_message"),
                data=json.dumps({"message": "How do I use PAMOJA?"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        system_text = captured["request"]["system_instruction"]["parts"][0]["text"]
        self.assertIn("OFFICIAL PAMOJA APP GUIDE", system_text)
        self.assertIn("/planner/", system_text)
        self.assertIn("/tasks/new/", system_text)
        self.assertEqual(Task.objects.count(), 0)

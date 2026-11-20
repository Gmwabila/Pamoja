"""AI task proposals must be user-owned, editable and approval-only."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import AIConversation, AIMessage, AITaskProposal, Profile, Task

User = get_user_model()


class FakeGeminiResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return json.dumps(self.payload).encode("utf-8")


class AIConversationalTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="task-proposal@example.com", password="TestPassword123!"
        )
        self.other = User.objects.create_user(
            email="other-task@example.com", password="TestPassword123!"
        )
        Profile.objects.create(user=self.user, timezone="America/Chicago", onboarded=True)
        self.client.force_login(self.user)

    def _propose(self, args=None):
        if args is None:
            args = {
                "title": "Study Python", "space": "education",
                "due_date": "2026-11-21", "priority": "high",
            }
        response = FakeGeminiResponse({"candidates": [{"content": {"parts": [
            {"functionCall": {"name": "propose_task", "args": args}}
        ]}}]})
        captured = {}

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data)
            return response

        with patch.dict("os.environ", {
            "GEMINI_API_KEY": "fake-test-key",
            "PAMOJA_AI_TESTING_ONLY": "false",
        }), patch("core.ai_chat.urlopen", side_effect=fake_urlopen):
            result = self.client.post(
                reverse("chat_message"),
                data=json.dumps({"message": "Create a Python study task tomorrow"}),
                content_type="application/json",
            )
        return result, captured

    def _save(self, proposal_id, **changes):
        data = {
            "title": "Study Python", "space": "education",
            "due_date": "2026-11-21", "due_time": "",
            "priority": "high",
        }
        data.update(changes)
        return self.client.post(
            reverse("chat_task_save", args=[proposal_id]),
            data=json.dumps(data), content_type="application/json",
        )

    def test_gemini_proposes_without_saving(self):
        response, captured = self._propose()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["task_proposal"]["title"], "Study Python")
        self.assertFalse(data["task_proposal"]["saved"])
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(AITaskProposal.objects.count(), 1)
        self.assertIn("tools", captured["payload"])
        self.assertIn("2026-", captured["payload"]["system_instruction"]["parts"][0]["text"])
        self.assertIn("America/Chicago", captured["payload"]["system_instruction"]["parts"][0]["text"])

    def test_save_requires_explicit_post_and_is_idempotent(self):
        response, _ = self._propose()
        proposal_id = response.json()["task_proposal"]["id"]
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(self.client.get(reverse("chat_task_save", args=[proposal_id])).status_code, 405)
        saved = self._save(proposal_id)
        self.assertEqual(saved.status_code, 200)
        self.assertTrue(saved.json()["task_proposal"]["saved"])
        task = Task.objects.get()
        self.assertEqual(task.user, self.user)
        self.assertEqual(task.space, "education")
        self.assertEqual(task.priority, "high")
        self.assertEqual(self._save(proposal_id).status_code, 200)
        self.assertEqual(Task.objects.count(), 1)

    def test_user_can_edit_before_approval(self):
        response, _ = self._propose()
        proposal_id = response.json()["task_proposal"]["id"]
        saved = self._save(proposal_id, title="Practice Python lists", due_time="18:30", priority="normal")
        self.assertEqual(saved.status_code, 200)
        task = Task.objects.get()
        self.assertEqual(task.title, "Practice Python lists")
        self.assertEqual(task.due_time.hour, 18)
        self.assertEqual(task.due_time.minute, 30)
        self.assertEqual(task.priority, "normal")

    def test_other_user_cannot_save_or_read_proposal(self):
        response, _ = self._propose()
        proposal_id = response.json()["task_proposal"]["id"]
        conversation_id = response.json()["conversation_id"]
        self.client.force_login(self.other)
        self.assertEqual(self._save(proposal_id).status_code, 404)
        self.assertEqual(self.client.get(reverse("chat_conversation_detail", args=[conversation_id])).status_code, 404)
        self.assertEqual(Task.objects.count(), 0)

    def test_invalid_edit_cannot_save(self):
        response, _ = self._propose()
        proposal_id = response.json()["task_proposal"]["id"]
        self.assertEqual(self._save(proposal_id, space="invalid").status_code, 400)
        self.assertEqual(self._save(proposal_id, due_date="bad").status_code, 400)
        self.assertEqual(self._save(proposal_id, due_time="27:99").status_code, 400)
        self.assertEqual(Task.objects.count(), 0)

    def test_invalid_model_proposal_is_not_saved(self):
        response, _ = self._propose({"title": "", "due_date": "nonsense"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["task_proposal"])
        self.assertEqual(AITaskProposal.objects.count(), 0)
        self.assertEqual(Task.objects.count(), 0)

    def test_proposal_survives_chat_reload(self):
        response, _ = self._propose()
        conversation_id = response.json()["conversation_id"]
        loaded = self.client.get(reverse("chat_conversation_detail", args=[conversation_id]))
        self.assertEqual(loaded.status_code, 200)
        last = loaded.json()["messages"][-1]
        self.assertEqual(last["task_proposal"]["title"], "Study Python")
        self.assertFalse(last["task_proposal"]["saved"])

    def test_normal_gemini_chat_has_no_proposal(self):
        response = FakeGeminiResponse({"candidates": [{"content": {"parts": [
            {"text": "Hello! How can I help?"}
        ]}}]})
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-test-key", "PAMOJA_AI_TESTING_ONLY": "false"}), \
                patch("core.ai_chat.urlopen", return_value=response):
            result = self.client.post(reverse("chat_message"),
                data=json.dumps({"message": "Hey there"}), content_type="application/json")
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.json()["task_proposal"])
        self.assertEqual(Task.objects.count(), 0)

    def test_anonymous_cannot_save(self):
        response, _ = self._propose()
        self.client.logout()
        self.assertEqual(self._save(response.json()["task_proposal"]["id"]).status_code, 302)

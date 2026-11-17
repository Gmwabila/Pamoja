import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import AdminAudit, Feedback, FeedbackReply


class FeedbackReplyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-password",
        )
        self.member = User.objects.create_user(
            email="member@example.com",
            password="test-password",
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="test-password",
        )
        self.enterContext(patch.dict(
            os.environ,
            {"PAMOJA_OWNER_USER_ID": str(self.owner.pk)},
        ))
        self.feedback = Feedback.objects.create(
            user=self.member,
            title="Private member feedback",
            body="A private submission.",
        )
        self.url = reverse(
            "owner_reply",
            args=[self.feedback.pk],
        )

    def test_reply_page_requires_owner(self):
        self.assertEqual(
            self.client.get(self.url).status_code, 302
        )

        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(self.url).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                self.url, {"body": "Unauthorized reply"}
            ).status_code,
            403,
        )
        self.assertFalse(FeedbackReply.objects.exists())

        self.client.force_login(self.owner)
        with patch.dict(os.environ, {"PAMOJA_OWNER_USER_ID": ""}):
            self.assertEqual(
                self.client.post(
                    self.url, {"body": "Blocked reply"}
                ).status_code,
                403,
            )

    def test_owner_reply_saves_author_and_audit(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {
            "body": "Thank you for the suggestion.",
            "author": self.other.pk,
        })

        self.assertRedirects(response, self.url)
        reply = FeedbackReply.objects.get()
        self.assertEqual(reply.author, self.owner)
        self.assertEqual(reply.feedback, self.feedback)
        

        entry = AdminAudit.objects.get()
        self.assertEqual(entry.action, "feedback.reply_sent")
        self.assertEqual(entry.actor, self.owner)
        self.assertEqual(entry.feedback, self.feedback)

    def test_users_only_see_their_own_feedback_and_replies(self):
        FeedbackReply.objects.create(
            feedback=self.feedback,
            author=self.owner,
            body="Private team response.",
        )
        url = reverse("my_feedback")

        self.client.force_login(self.member)
        response = self.client.get(url)
        self.assertContains(response, self.feedback.title)
        self.assertContains(response, "Private team response.")

        self.client.force_login(self.other)
        response = self.client.get(url)
        self.assertNotContains(response, self.feedback.title)
        self.assertNotContains(response, "Private team response.")

    def test_invalid_replies_are_not_saved(self):
        self.client.force_login(self.owner)

        for body in ("", "   ", "x" * 3001):
            with self.subTest(body_length=len(body)):
                response = self.client.post(
                    self.url, {"body": body}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)

        self.assertFalse(FeedbackReply.objects.exists())
        self.assertFalse(AdminAudit.objects.exists())

    def test_reply_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(
            self.url, {"body": "Missing token"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(FeedbackReply.objects.exists())

    def test_audit_failure_rolls_back_reply(self):
        self.client.force_login(self.owner)

        with patch(
            "core.feedback_replies.AdminAudit.objects.create",
            side_effect=RuntimeError("Audit failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    self.url, {"body": "Test response"}
                )

        self.assertFalse(FeedbackReply.objects.exists())

    def test_reply_html_is_escaped(self):
        FeedbackReply.objects.create(
            feedback=self.feedback,
            author=self.owner,
            body="<script>alert('test')</script>",
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse("my_feedback"))

        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(")
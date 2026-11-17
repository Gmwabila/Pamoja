import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import Client, TestCase, RequestFactory
from core.owner_tools import owner_health
from django.urls import reverse

from core.models import AdminAudit, Feedback


class OwnerToolsTests(TestCase):
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
        self.enterContext(patch.dict(
            os.environ,
            {"PAMOJA_OWNER_USER_ID": str(self.owner.pk)},
        ))
        self.feedback = Feedback.objects.create(
            user=self.member,
            kind="bug",
            title="Planner issue",
            body="Private feedback example",
        )

    def test_admin_pages_restrict_access(self):
        for name in ("owner_feedback", "owner_health"):
            url = reverse(name)
            self.assertEqual(self.client.get(url).status_code, 302)

            self.client.force_login(self.member)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(
                response,
                self.feedback.body,
                status_code=403,
            )
            self.client.logout()

        self.client.force_login(self.owner)
        with patch.dict(os.environ, {"PAMOJA_OWNER_USER_ID": ""}):
            self.assertEqual(
                self.client.get(
                    reverse("owner_feedback")
                ).status_code,
                403,
            )

    def test_submission_uses_logged_in_user(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse("feedback"), {
            "kind": "feature",
            "title": "Calendar view",
            "body": "Please add a monthly calendar.",
            "user": self.owner.pk,
            "status": "resolved",
        })
        self.assertRedirects(response, reverse("feedback"))
        item = Feedback.objects.get(title="Calendar view")
        self.assertEqual(item.user, self.member)
        self.assertEqual(item.status, "new")

    def test_invalid_feedback_is_not_saved(self):
        self.client.force_login(self.member)
        before = Feedback.objects.count()
        response = self.client.post(reverse("feedback"), {
            "kind": "invalid",
            "title": "",
            "body": "x" * 3001,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Feedback.objects.count(), before)

    def test_status_changes_require_owner_and_post(self):
        url = reverse(
            "owner_feedback_status",
            args=[self.feedback.pk],
        )
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.post(
                url, {"status": "resolved"}
            ).status_code,
            403,
        )

        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(
            self.client.post(
                url, {"status": "invalid"}
            ).status_code,
            400,
        )

        self.client.post(url, {"status": "reviewed"})
        self.feedback.refresh_from_db()
        self.assertEqual(self.feedback.status, "reviewed")

        entry = AdminAudit.objects.get()
        self.assertEqual(entry.actor, self.owner)
        self.assertEqual(entry.previous_status, "new")
        self.assertEqual(entry.new_status, "reviewed")

        self.client.post(url, {"status": "reviewed"})
        self.assertEqual(AdminAudit.objects.count(), 1)

    def test_failed_audit_rolls_back_status_change(self):
        self.client.force_login(self.owner)
        url = reverse(
            "owner_feedback_status",
            args=[self.feedback.pk],
        )
        with patch(
            "core.owner_tools.AdminAudit.objects.create",
            side_effect=RuntimeError("Audit failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(url, {"status": "resolved"})

        self.feedback.refresh_from_db()
        self.assertEqual(self.feedback.status, "new")

    def test_posts_require_csrf_tokens(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.member)
        self.assertEqual(
            client.post(reverse("feedback"), {
                "kind": "bug",
                "title": "Test",
                "body": "Test message",
            }).status_code,
            403,
        )

        client.force_login(self.owner)
        self.assertEqual(
            client.post(
                reverse(
                    "owner_feedback_status",
                    args=[self.feedback.pk],
                ),
                {"status": "resolved"},
            ).status_code,
            403,
        )

    def test_feedback_content_is_escaped(self):
        self.feedback.body = "<script>alert('test')</script>"
        self.feedback.save()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("owner_feedback"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(")

    def test_submission_limit(self):
        self.client.force_login(self.member)
        for number in range(4):
            Feedback.objects.create(
                user=self.member,
                title=f"Feedback {number}",
                body="Example",
            )

        before = Feedback.objects.count()
        response = self.client.post(reverse("feedback"), {
            "kind": "suggestion",
            "title": "Another suggestion",
            "body": "Example",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertEqual(Feedback.objects.count(), before)

    def test_health_success_and_failure(self):
        self.client.force_login(self.owner)
        url = reverse("owner_health")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["database_ok"])

        request = RequestFactory().get(url)
        request.user = self.owner

        with patch(
            "core.owner_tools.connection.cursor",
            side_effect=DatabaseError("Sensitive details"),
        ):
            response = owner_health(request)

        self.assertEqual(response.status_code, 503)
        self.assertNotContains(
            response,
            "Sensitive details",
            status_code=503,
        )
        self.assertContains(
            response,
            "The database check failed.",
            status_code=503,
        )
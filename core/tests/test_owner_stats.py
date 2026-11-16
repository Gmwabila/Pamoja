import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class OwnerStatsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            "owner@example.com", "TestingOnly!4389"
        )
        self.member = User.objects.create_user(
            "member@example.com", "TestingOnly!4389"
        )
        self.admin = User.objects.create_user(
            "admin@example.com", "TestingOnly!4389",
            is_staff=True, is_superuser=True
        )
        environment = patch.dict(os.environ, {
            "PAMOJA_OWNER_USER_ID": str(self.owner.pk)
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_guest_and_other_accounts_cannot_view_counts(self):
        url = reverse("owner_dashboard")
        self.assertEqual(self.client.get(url).status_code, 302)
        for user in (self.member, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_owner_sees_counts_without_account_details(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["total"], 3)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotContains(response, self.member.email)
        self.assertNotContains(response, self.admin.email)

    def test_access_is_denied_when_owner_is_not_configured(self):
        self.client.force_login(self.owner)
        with patch.dict(os.environ, {"PAMOJA_OWNER_USER_ID": ""}):
            response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 403)

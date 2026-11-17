from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.translation import gettext, override

from core.forms import PreferencesForm
from core.models import Profile


class LanguageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="language-test@example.com",
            password="Pamoja-Test-7392!",
            first_name="Gloire",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            onboarded=True,
            language="en",
            timezone="UTC",
            spaces=["planning"],
        )

    def test_anonymous_language_selection_for_all_six_languages(self):
        expected_labels = {
            "en": "Apply",
            "fr": "Appliquer",
            "es": "Aplicar",
            "ln": "Salela",
            "sw": "Tumia",
            "ja": "適用",
        }

        for language, label in expected_labels.items():
            with self.subTest(language=language):
                client = Client(HTTP_ACCEPT_LANGUAGE="en")

                response = client.post(
                    reverse("change_language"),
                    {
                        "language": language,
                        "next": reverse("login"),
                    },
                )

                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.cookies[
                        settings.LANGUAGE_COOKIE_NAME
                    ].value,
                    language,
                )

                response = client.get(reverse("login"))

                self.assertEqual(
                    response.headers["Content-Language"],
                    language,
                )
                self.assertContains(
                    response,
                    f'<html lang="{language}">',
                )
                self.assertContains(response, label)

    def test_saved_preference_follows_user_to_another_browser(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("change_language"),
            {
                "language": "fr",
                "next": reverse("dashboard"),
            },
        )
        self.assertEqual(response.status_code, 302)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.language, "fr")

        # A different browser prefers Japanese, but this
        # account's saved preference should take priority.
        other_browser = Client(HTTP_ACCEPT_LANGUAGE="ja")
        other_browser.force_login(self.user)

        response = other_browser.get(reverse("dashboard"))

        self.assertEqual(
            response.headers["Content-Language"],
            "fr",
        )
        self.assertContains(response, "Vos progrès du jour")
        self.assertContains(response, "Gloire")

    def test_invalid_language_does_not_change_preference(self):
        self.client.force_login(self.user)

        cookie_name = settings.LANGUAGE_COOKIE_NAME
        self.client.cookies[cookie_name] = "en"

        response = self.client.post(
            reverse("change_language"),
            {"language": "invalid-language"},
        )

        self.assertEqual(response.status_code, 400)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.language, "en")

        # The rejected selection must not replace the cookie.
        self.assertNotIn(cookie_name, response.cookies)
        self.assertEqual(
            self.client.cookies[cookie_name].value,
            "en",
        )

    def test_language_change_requires_post(self):
        response = self.client.get(reverse("change_language"))
        self.assertEqual(response.status_code, 405)

    def test_external_redirect_is_rejected(self):
        response = self.client.post(
            reverse("change_language"),
            {
                "language": "es",
                "next": "https://example.org/untrusted",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_language_change_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        url = reverse("change_language")

        response = client.post(url, {"language": "fr"})
        self.assertEqual(response.status_code, 403)

        client.get(reverse("login"))
        token = client.cookies[
            settings.CSRF_COOKIE_NAME
        ].value

        response = client.post(
            url,
            {
                "language": "fr",
                "csrfmiddlewaretoken": token,
                "next": reverse("login"),
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_signup_keeps_language_selected_before_registration(self):
        self.client.cookies[
            settings.LANGUAGE_COOKIE_NAME
        ] = "fr"

        response = self.client.post(
            reverse("signup"),
            {
                "first_name": "New User",
                "email": "new-language-user@example.com",
                "password1": "Pamoja-Test-7392!",
                "password2": "Pamoja-Test-7392!",
            },
        )

        self.assertEqual(response.status_code, 302)

        profile = Profile.objects.get(
            user__email="new-language-user@example.com"
        )
        self.assertEqual(profile.language, "fr")

    def test_older_preferences_form_preserves_saved_language(self):
        self.profile.language = "sw"
        self.profile.save(update_fields=["language"])

        form = PreferencesForm(
            data={
                "spaces": ["planning"],
                "goal": "",
                "timezone": "UTC",
            },
            instance=self.profile,
        )

        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save()
        self.assertEqual(profile.language, "sw")

    def test_dashboard_catalogs_have_translations(self):
        expected_titles = {
            "en": "Your day",
            "fr": "Votre journée",
            "es": "Tu día",
            "ln": "Mokolo na yo",
            "sw": "Siku yako",
            "ja": "今日の予定",
        }

        for language, expected in expected_titles.items():
            with self.subTest(language=language):
                with override(language):
                    self.assertEqual(
                        gettext("Your day"),
                        expected,
                    )
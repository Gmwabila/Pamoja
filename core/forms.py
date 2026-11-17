from zoneinfo import available_timezones

from django import forms
from django.conf import settings
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.utils.translation import gettext_lazy as _

from .models import Profile, Task, User
from .time_fields import FriendlyTimeField


SPACE_CHOICES = [
    ("planning", _("Daily Planning")),
    ("career", _("Career & Jobs")),
    ("fitness", _("Fitness")),
    ("education", _("Education")),
    ("sports", _("Sports")),
]

PRIORITY_CHOICES = [
    ("normal", _("Normal")),
    ("high", _("High")),
]


class SignupForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=150,
        label=_("What should we call you?"),
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "email",
            "password1",
            "password2",
        ]
        labels = {
            "email": _("Email"),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _(
                    "An account with this email already exists. "
                    "Try logging in."
                )
            )

        return email


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label=_("Email"))

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class PreferencesForm(forms.ModelForm):
    spaces = forms.MultipleChoiceField(
        label=_("Your spaces"),
        choices=SPACE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    timezone = forms.ChoiceField(
        label=_("Timezone"),
        choices=[
            (zone, zone.replace("_", " "))
            for zone in sorted(available_timezones())
        ],
    )

    language = forms.ChoiceField(
        label=_("Language"),
        choices=settings.LANGUAGES,
        required=False,
        help_text=_("Choose the language you prefer for PAMOJA."),
    )

    class Meta:
        model = Profile
        fields = [
            "spaces",
            "goal",
            "timezone",
            "language",
            "reminders",
        ]
        labels = {
            "goal": _("Your goal"),
            "reminders": _("Reminders"),
        }
        widgets = {
            "goal": forms.Textarea(attrs={
                "rows": 2,
                "placeholder": _(
                    "One thing you would like to make time for…"
                ),
            }),
        }
    def clean_language(self):
        return (
            self.cleaned_data.get("language")
            or self.instance.language
            or settings.LANGUAGE_CODE
        )

    def clean_spaces(self):
        selected = self.cleaned_data["spaces"]
        previous = self.instance.spaces or []

        return (
            [space for space in previous if space in selected]
            + [space for space in selected if space not in previous]
        )


class TaskForm(forms.ModelForm):
    space = forms.ChoiceField(
        label=_("Space"),
        choices=SPACE_CHOICES,
    )

    priority = forms.ChoiceField(
        label=_("Priority"),
        choices=PRIORITY_CHOICES,
    )

    due_time = FriendlyTimeField(label=_("Due time"))

    class Meta:
        model = Task
        fields = [
            "title",
            "space",
            "due_date",
            "due_time",
            "priority",
        ]
        labels = {
            "title": _("Task"),
            "due_date": _("Due date"),
        }
        widgets = {
            "due_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "title": forms.TextInput(attrs={
                "placeholder": _(
                    "What would you like to get done?"
                ),
            }),
        }
from zoneinfo import available_timezones
from .models import Profile, Task, User, SPACES
from datetime import time

from django import forms
from django.conf import settings
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.utils.translation import gettext_lazy as _

from .models import Profile, Task, User
from .time_fields import FriendlyTimeField


SPACE_CHOICES = SPACES

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

    reminder_hour = forms.ChoiceField(
    label=_("Hour"),
    required=False,
    choices=[
        (str(hour), str(hour).zfill(2))
        for hour in range(1, 13)
    ],
)

    reminder_minute = forms.ChoiceField(
        label=_("Minute"),
        required=False,
        choices=[
            (f"{minute:02d}", f"{minute:02d}")
            for minute in range(0, 60, 10)
        ],
    )

    reminder_period = forms.ChoiceField(
        label=_("AM / PM"),
        required=False,
        choices=[
            ("AM", "AM"),
            ("PM", "PM"),
        ],
    )

    class Meta:
        model = Profile

        fields = [
            "spaces",
            "goal",
            "timezone",
            "language",
            "reminders",
            "daily_planning_notifications",
            "goal_notifications",
            "feedback_notifications",
            "product_update_notifications",
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


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_time = self.instance.daily_planning_time

        if isinstance(current_time, str):
            try:
                current_time = time.fromisoformat(current_time)
            except ValueError:
                current_time = time(8, 0)

        if current_time is None:
            current_time = time(8, 0)

        hour = current_time.hour

        # Preserve submitted values when the form is bound.
        if not self.is_bound:
            self.fields["reminder_hour"].initial = str(
                hour % 12 or 12
            )
            self.fields["reminder_minute"].initial = (
                f"{current_time.minute:02d}"
            )
            self.fields["reminder_period"].initial = (
                "PM" if hour >= 12 else "AM"
            )


    def save(self, commit=True):
        profile = super().save(commit=False)

        hour_value = self.cleaned_data.get("reminder_hour")
        minute_value = self.cleaned_data.get("reminder_minute")
        period = self.cleaned_data.get("reminder_period")

        # Preserve the existing time for older clients that
        # do not submit reminder-time fields.
        if all((hour_value, minute_value, period)):
            hour = int(hour_value)
            minute = int(minute_value)

            hour_24 = hour % 12
            if period == "PM":
                hour_24 += 12

            profile.daily_planning_time = time(hour_24, minute)

        if commit:
            profile.save()
            self.save_m2m()

        return profile

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
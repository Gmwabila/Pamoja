from datetime import time

from django import forms
from django.utils.translation import gettext_lazy as _


HOURS = [("", _("Hour"))] + [
    (str(hour), str(hour))
    for hour in range(1, 13)
]

MINUTES = [("", _("Minute"))] + [
    (f"{minute:02}", f"{minute:02}")
    for minute in range(60)
]

PERIODS = [
    ("", _("AM/PM")),
    ("AM", "AM"),
    ("PM", "PM"),
]


class FriendlyTimeWidget(forms.MultiWidget):
    """Ordinary select menus, without a browser-native time picker."""

    template_name = "core/widgets/friendly_time.html"

    def __init__(self, attrs=None):
        super().__init__(
            [
                forms.Select(choices=HOURS),
                forms.Select(choices=MINUTES),
                forms.Select(choices=PERIODS),
            ],
            attrs,
        )

    def decompress(self, value):
        if isinstance(value, str) and value:
            try:
                value = time.fromisoformat(value)
            except ValueError:
                return [None, None, None]

        if isinstance(value, time):
            return [
                str(value.hour % 12 or 12),
                f"{value.minute:02}",
                "PM" if value.hour >= 12 else "AM",
            ]

        return [None, None, None]

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        labels = [
            _("Hour"),
            _("Minute"),
            _("AM or PM"),
        ]

        for widget, label in zip(
            context["widget"]["subwidgets"],
            labels,
        ):
            widget["component_label"] = label

        return context


class FriendlyTimeField(forms.MultiValueField):
    widget = FriendlyTimeWidget

    def __init__(self, **kwargs):
        error = {
            "incomplete": _(
                "Choose an hour, minute, and AM or PM, "
                "or leave all three blank."
            )
        }

        fields = [
            forms.ChoiceField(
                choices=choices,
                error_messages=error,
            )
            for choices in [HOURS, MINUTES, PERIODS]
        ]

        kwargs.setdefault("required", False)

        kwargs.setdefault(
            "help_text",
            _(
                "Optional. For 6:30 PM, choose 6, 30, and PM. "
                "Leave all three blank for no time."
            ),
        )

        super().__init__(
            fields=fields,
            require_all_fields=False,
            error_messages=error,
            **kwargs,
        )

    def compress(self, values):
        if not values:
            return None

        hour, minute, period = values

        return time(
            int(hour) % 12 + (12 if period == "PM" else 0),
            int(minute),
        )

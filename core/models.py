from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


SPACES = [
    ("planning", _("Daily Planning")),
    ("career", _("Career & Jobs")),
    ("fitness", _("Fitness")),
    ("education", _("Education")),
    ("sports", _("Sports")),
]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")

        user = self.model(
            email=email.strip().lower(),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    spaces = models.JSONField(default=list)
    goal = models.CharField(max_length=300, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    language = models.CharField(
        max_length=10,
        choices=settings.LANGUAGES,
        default="en",
    )
    reminders = models.BooleanField(default=False)
    onboarded = models.BooleanField(default=False)


class Task(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=160)
    space = models.CharField(
        max_length=16,
        choices=SPACES,
        default="planning",
    )
    due_date = models.DateField()
    due_time = models.TimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=8,
        choices=[
            ("normal", _("Normal")),
            ("high", _("High")),
        ],
        default="normal",
    )
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [
            "completed",
            "due_date",
            "due_time",
            "-created_at",
        ]


class Feedback(models.Model):
    KIND_CHOICES = [
        ("suggestion", _("Suggestion")),
        ("bug", _("Bug report")),
        ("feature", _("Feature request")),
    ]

    STATUS_CHOICES = [
        ("new", _("New")),
        ("reviewed", _("Reviewed")),
        ("resolved", _("Resolved")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    kind = models.CharField(
        max_length=16,
        choices=KIND_CHOICES,
        default="suggestion",
    )
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=3000)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="new",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class AdminAudit(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    feedback = models.ForeignKey(
        Feedback,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=64)
    previous_status = models.CharField(max_length=16)
    new_status = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class FeedbackReply(models.Model):
    feedback = models.ForeignKey(
        Feedback,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
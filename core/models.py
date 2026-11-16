from zoneinfo import available_timezones
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

SPACES = [('planning', 'Daily Planning'), ('career', 'Career & Jobs'), ('fitness', 'Fitness'),
          ('education', 'Education'), ('sports', 'Sports')]

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    spaces = models.JSONField(default=list)
    goal = models.CharField(max_length=300, blank=True)
    timezone = models.CharField(max_length=64, default='UTC')
    reminders = models.BooleanField(default=False)
    onboarded = models.BooleanField(default=False)

class Task(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    space = models.CharField(max_length=16, choices=SPACES, default='planning')
    due_date = models.DateField()
    due_time = models.TimeField(null=True, blank=True)
    priority = models.CharField(max_length=8, choices=[('normal', 'Normal'), ('high', 'High')], default='normal')
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['completed', 'due_date', 'due_time', '-created_at']

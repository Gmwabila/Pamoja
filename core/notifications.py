
from datetime import timedelta

from django.utils import timezone
from zoneinfo import ZoneInfo

from .models import Notification, Profile, Task


def generate_notifications(user):
    """Generate in-app notifications for one user."""
    profile, _ = Profile.objects.get_or_create(user=user)

    local_now = timezone.localtime(
        timezone.now(),
        ZoneInfo(profile.timezone),
    )
    today = local_now.date()

    if profile.reminders:
        tasks = Task.objects.filter(
            user=user,
            completed=False,
            due_date__lte=today + timedelta(days=1),
        )

        for task in tasks:
            if task.due_date < today:
                label = "overdue"
                title = "Overdue task"
                message = f'"{task.title}" is overdue.'
            elif task.due_date == today:
                label = "today"
                title = "Task due today"
                message = f'"{task.title}" is due today.'
            else:
                label = "tomorrow"
                title = "Task due tomorrow"
                message = f'"{task.title}" is due tomorrow.'

            Notification.objects.get_or_create(
                user=user,
                event_key=f"task:{task.pk}:{label}:{today}",
                defaults={
                    "kind": "task",
                    "title": title,
                    "message": message,
                },
            )

    # Daily planning is independent of task reminders.
    if profile.daily_planning_notifications:
        reminder_time = profile.daily_planning_time

        if local_now.time().replace(tzinfo=None) >= reminder_time:
            Notification.objects.get_or_create(
                user=user,
                event_key=f"planning:{today}",
                defaults={
                    "kind": "planning",
                    "title": "Plan your day",
                    "message": (
                        "It's time to plan your day with PAMOJA."
                    ),
                },
            )

    if profile.goal_notifications:
        daily_tasks = Task.objects.filter(
            user=user,
            due_date=today,
        )
        total = daily_tasks.count()

        if total:
            completed = daily_tasks.filter(
                completed=True
            ).count()
            percentage = completed * 100 / total

            for milestone in (50, 100):
                if percentage >= milestone:
                    Notification.objects.get_or_create(
                        user=user,
                        event_key=f"milestone:{today}:{milestone}",
                        defaults={
                            "kind": "milestone",
                            "title": f"{milestone}% daily progress!",
                            "message": (
                                f"You've completed {completed} of "
                                f"{total} tasks scheduled for today."
                            ),
                        },
                    )

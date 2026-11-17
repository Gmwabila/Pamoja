import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Profile


@never_cache
@login_required
@require_safe
def owner_dashboard(request):
    owner_id = os.environ.get("PAMOJA_OWNER_USER_ID", "").strip()

    if not owner_id or str(request.user.pk) != owner_id:
        return HttpResponseForbidden(
            "This page is restricted to the owner."
        )

    zone_name = (
        Profile.objects.filter(user=request.user)
        .values_list("timezone", flat=True)
        .first()
    ) or "UTC"

    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")

    now = timezone.now()
    today = timezone.localtime(now, zone).date()
    start = datetime.combine(today, time.min, tzinfo=zone)
    end = start + timedelta(days=1)
    week_start = start - timedelta(days=6)

    users = get_user_model().objects.all()

    metrics = users.aggregate(
        total=Count("pk"),
        today=Count(
            "pk",
            filter=Q(
                date_joined__gte=start,
                date_joined__lt=end,
            ),
        ),
        week=Count(
            "pk",
            filter=Q(
                date_joined__gte=week_start,
                date_joined__lt=end,
            ),
        ),
    )

    # Group registrations into local calendar days.
    daily_counts = (
        users.filter(
            date_joined__gte=week_start,
            date_joined__lt=end,
        )
        .order_by()
        .annotate(day=TruncDate("date_joined", tzinfo=zone))
        .values("day")
        .annotate(total=Count("pk"))
        .order_by("day")
    )

    counts_by_day = {
        row["day"]: row["total"]
        for row in daily_counts
    }

    # Include days with no registrations.
    registration_days = []
    for offset in range(7):
        day = week_start.date() + timedelta(days=offset)
        registration_days.append({
            "date": day,
            "count": counts_by_day.get(day, 0),
        })

    largest_count = max(
        (day["count"] for day in registration_days),
        default=0,
    )

    for day in registration_days:
        day["width"] = (
            round(day["count"] / largest_count * 100)
            if largest_count else 0
        )

    # Fetch only fields needed for the recent-signups list.
    newest_users = (
        users.only("first_name", "last_name", "date_joined")
        .order_by("-date_joined", "-pk")[:10]
    )

    recent_users = [
        {
            "name": user.get_full_name().strip()
            or "Name not provided",
            "joined_at": timezone.localtime(
                user.date_joined, zone
            ),
        }
        for user in newest_users
    ]

    return render(request, "core/owner_stats.html", {
        "metrics": metrics,
        "registration_days": registration_days,
        "recent_users": recent_users,
        "report_timezone": str(zone),
        "checked_at": timezone.localtime(now, zone),
    })
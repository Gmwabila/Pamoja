import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
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
        return HttpResponseForbidden("This page is restricted to the owner.")

    zone_name = (
        Profile.objects.filter(user=request.user)
        .values_list("timezone", flat=True).first()
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

    metrics = get_user_model().objects.aggregate(
        total=Count("pk"),
        today=Count("pk", filter=Q(
            date_joined__gte=start, date_joined__lt=end
        )),
        week=Count("pk", filter=Q(
            date_joined__gte=week_start, date_joined__lt=end
        )),
    )

    return render(request, "core/owner_stats.html", {
        "metrics": metrics,
        "checked_at": timezone.localtime(now, zone),
    })

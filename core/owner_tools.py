
import os
from datetime import timedelta
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, connection, transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from .models import AdminAudit, Feedback


# ============================================================
# OWNER ACCESS PROTECTION
# ============================================================

def owner_required(view):
    @never_cache
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        owner_id = os.environ.get(
            "PAMOJA_OWNER_USER_ID", ""
        ).strip()

        if not owner_id or str(request.user.pk) != owner_id:
            return HttpResponseForbidden(
                "This page is restricted to the owner."
            )

        return view(request, *args, **kwargs)

    return wrapped


# ============================================================
# USER FEEDBACK FORM
# ============================================================

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["kind", "title", "body"]

        labels = {
            "kind": "Feedback type",
            "title": "Subject",
            "body": "Your feedback",
        }

        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 6}
            ),
        }


# ============================================================
# SUBMIT USER FEEDBACK
# ============================================================

@never_cache
@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def submit_feedback(request):
    form = FeedbackForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        since = timezone.now() - timedelta(hours=1)

        # Limit each account to five submissions per hour.
        with transaction.atomic():
            user_model = request.user._meta.model

            user_model.objects.select_for_update().get(
                pk=request.user.pk
            )

            recent_count = Feedback.objects.filter(
                user=request.user,
                created_at__gte=since,
            ).count()

            if recent_count >= 5:
                form.add_error(
                    None,
                    "You can send up to five submissions per hour. "
                    "Please try again later.",
                )
            else:
                feedback = form.save(commit=False)
                feedback.user = request.user
                feedback.save()

                messages.success(
                    request,
                    "Thank you! Your feedback has been sent.",
                )

                return redirect("feedback")

    return render(
        request,
        "core/feedback.html",
        {"form": form},
    )


# ============================================================
# ADMIN FEEDBACK INBOX
# ============================================================

@owner_required
@require_GET
def owner_feedback(request):
    active_status = request.GET.get("status", "")
    valid_statuses = dict(Feedback.STATUS_CHOICES)

    if active_status and active_status not in valid_statuses:
        return HttpResponseBadRequest(
            "Invalid feedback status."
        )

    feedback = Feedback.objects.select_related("user")

    if active_status:
        feedback = feedback.filter(
            status=active_status
        )

    page = Paginator(feedback, 20).get_page(
        request.GET.get("page")
    )

    new_count = Feedback.objects.filter(
        status="new"
    ).count()

    audit_entries = AdminAudit.objects.all()[:20]

    context = {
        "page_obj": page,
        "active_status": active_status,
        "status_choices": Feedback.STATUS_CHOICES,
        "new_count": new_count,
        "audit_entries": audit_entries,
    }

    return render(
        request,
        "core/owner_feedback.html",
        context,
    )


# ============================================================
# UPDATE FEEDBACK STATUS AND RECORD ADMIN ACTION
# ============================================================

@owner_required
@csrf_protect
@require_POST
def owner_feedback_status(request, pk):
    new_status = request.POST.get("status", "")

    if new_status not in dict(Feedback.STATUS_CHOICES):
        return HttpResponseBadRequest(
            "Invalid feedback status."
        )

    with transaction.atomic():
        feedback = get_object_or_404(
            Feedback.objects.select_for_update(),
            pk=pk,
        )

        previous_status = feedback.status

        if previous_status != new_status:
            feedback.status = new_status

            feedback.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            AdminAudit.objects.create(
                actor=request.user,
                feedback=feedback,
                action="feedback.status_changed",
                previous_status=previous_status,
                new_status=new_status,
            )

    messages.success(
        request,
        "Feedback status saved.",
    )

    return redirect("owner_feedback")


# ============================================================
# ADMIN PLATFORM HEALTH CHECK
# ============================================================

@owner_required
@require_GET
def owner_health(request):
    database_ok = False

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database_ok = cursor.fetchone() == (1,)

    except DatabaseError:
        # Never expose internal database errors to users.
        database_ok = False

    context = {
        "database_ok": database_ok,
        "checked_at": timezone.now(),
    }

    return render(
        request,
        "core/owner_health.html",
        context,
        status=200 if database_ok else 503,
    )

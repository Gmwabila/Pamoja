from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
)

from .models import AdminAudit, Feedback, FeedbackReply
from .owner_tools import owner_required


class FeedbackReplyForm(forms.ModelForm):
    class Meta:
        model = FeedbackReply
        fields = ["body"]
        labels = {
            "body": "Your reply",
        }
        widgets = {
            "body": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "Write a response to this user...",
            }),
        }


@owner_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def owner_reply(request, pk):
    feedback = get_object_or_404(
        Feedback.objects.select_related("user"),
        pk=pk,
    )

    form = FeedbackReplyForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_feedback = get_object_or_404(
                Feedback.objects.select_for_update(),
                pk=feedback.pk,
            )

            reply = form.save(commit=False)
            reply.feedback = locked_feedback
            reply.author = request.user
            reply.save()

            AdminAudit.objects.create(
                actor=request.user,
                feedback=locked_feedback,
                action="feedback.reply_sent",
                previous_status=locked_feedback.status,
                new_status=locked_feedback.status,
            )

        messages.success(
            request,
            "Reply sent. The user can read it under My feedback.",
        )
        return redirect("owner_reply", pk=feedback.pk)

    return render(
        request,
        "core/owner_reply.html",
        {
            "feedback": feedback,
            "replies": feedback.replies.all(),
            "form": form,
        },
    )


@never_cache
@login_required
@require_GET
def my_feedback(request):
    # Only retrieve submissions belonging to this account.
    submissions = (
        Feedback.objects.filter(user=request.user)
        .prefetch_related("replies")
    )

    page = Paginator(submissions, 10).get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "core/my_feedback.html",
        {"page_obj": page},
    )

import json
import time
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_GET, require_POST
from .models import AIConversation, AIMessage, AIUsageLimit, AIUsageGlobal


SYSTEM_INSTRUCTIONS = """
You are PAMOJA AI, a helpful personal assistant.

You support users with:
- Daily planning, routines, and personal goals.
- Emotional support and everyday challenges.
- Education, studying, and career development.
- General questions and thoughtful conversations.

Be warm, respectful, practical, and conversational.
Adapt to what the user needs rather than always suggesting a plan.

When someone is struggling emotionally, listen empathetically.
Do not claim to be a therapist or provide diagnoses.
For immediate danger or self-harm concerns, encourage urgent
human support, including local emergency or crisis services.

Never claim to have created, updated, or deleted a planner task.
You cannot currently access or change the user's planner.

Do not request passwords or sensitive account credentials.
Respond in the user's language when possible.
"""

GLOBAL_DAILY_LIMIT = 300
GLOBAL_MINUTE_LIMIT = 10


def rate_limit_exceeded(user_id):
    now = int(time.time())

    minute_window = now // 60
    day_window = now // 86400

    with transaction.atomic():

        # Lock the shared global usage counter.
        global_usage, _ = (
            AIUsageGlobal.objects
            .select_for_update()
            .get_or_create(
                day_window=day_window,
                defaults={"request_count": 0},
            )
        )

        # Global daily limit.
        if global_usage.request_count >= GLOBAL_DAILY_LIMIT:
            return True

        
        # Rolling global limit: count requests in the
        # preceding 60 seconds, including all users.
        recent_request_times = [
            timestamp
            for timestamp in global_usage.recent_request_times
            if now - 60 < timestamp <= now
        ]

        if len(recent_request_times) >= GLOBAL_MINUTE_LIMIT:
            return True

        # Lock the individual user's counter.
        usage, _ = (
            AIUsageLimit.objects
            .select_for_update()
            .get_or_create(user_id=user_id)
        )

        minute_count = (
            usage.minute_count
            if usage.minute_window == minute_window
            else 0
        )

        day_count = (
            usage.day_count
            if usage.day_window == day_window
            else 0
        )

        # Individual user limits.
        if minute_count >= 10 or day_count >= 40:
            return True

        # Update individual usage.
        usage.minute_window = minute_window
        usage.minute_count = minute_count + 1
        usage.day_window = day_window
        usage.day_count = day_count + 1

        usage.save(update_fields=[
            "minute_window",
            "minute_count",
            "day_window",
            "day_count",
        ])

        
        # Record the accepted request in the rolling window.
        global_usage.minute_window = minute_window
        global_usage.minute_count = len(recent_request_times) + 1
        global_usage.recent_request_times = recent_request_times + [now]
        global_usage.request_count += 1

        global_usage.save(update_fields=[
            "minute_window",
            "minute_count",
            "recent_request_times",
            "request_count",
        ])


    return False


@login_required
@require_POST
def send_message(request):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return JsonResponse(
            {"error": _("AI chat is not configured yet.")},
            status=503,
        )

    if len(request.body) > 20000:
        return JsonResponse(
            {"error": _("Message request is too large.")},
            status=400,
        )

    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"error": _("Invalid message format.")},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": _("Invalid message format.")},
            status=400,
        )

    message = payload.get("message")

    if not isinstance(message, str) or not message.strip():
        return JsonResponse(
            {"error": _("Please enter a message.")},
            status=400,
        )

    message = message.strip()

    if len(message) > 2000:
        return JsonResponse(
            {"error": _("Please keep messages under 2000 characters.")},
            status=400,
        )

    # Identify the conversation, if one was supplied.
    conversation_id = payload.get("conversation_id")

    if conversation_id is not None:
        if (
            isinstance(conversation_id, bool)
            or not isinstance(conversation_id, int)
            or conversation_id <= 0
        ):
            return JsonResponse(
                {"error": _("Invalid conversation ID.")},
                status=400,
            )

        # A user can access only their own conversations.
        conversation = AIConversation.objects.filter(
            pk=conversation_id,
            user=request.user,
        ).first()

        if conversation is None:
            return JsonResponse(
                {"error": _("Conversation not found.")},
                status=404,
            )
    else:
        conversation = None

    # Read recent history from our database, not the browser.
    history = []

    if conversation is not None:
        recent_messages = list(
            conversation.messages.order_by(
                "-created_at", "-pk"
            )[:12]
        )

        for saved_message in reversed(recent_messages):
            history.append({
                "role": saved_message.role,
                "parts": [{
                    "text": saved_message.content
                }],
            })

    if rate_limit_exceeded(request.user.pk):
        return JsonResponse(
            {
                "error": _("Message limit reached. Please try again later.")
            },
            status=429,
        )

    model = os.environ.get(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )

    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        return JsonResponse(
            {"error": _("AI model configuration is invalid.")},
            status=503,
        )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent"
    )

    language = get_language() or "en"

    data = {
        "system_instruction": {
            "parts": [{
                "text": (
                    SYSTEM_INSTRUCTIONS
                    + f"\nPreferred interface language: {language}."
                )
            }]
        },
        "contents": history + [{
            "role": "user",
            "parts": [{"text": message}],
        }],
        "generationConfig": {
            "maxOutputTokens": 700,
            "temperature": 0.7,
        },
    }

    http_request = Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(http_request, timeout=25) as response:
            result = json.load(response)

        candidates = result.get("candidates", [])
        parts = (
            candidates[0].get("content", {}).get("parts", [])
            if candidates else []
        )

        reply = "\n".join(
            part["text"]
            for part in parts
            if isinstance(part, dict)
            and isinstance(part.get("text"), str)
        ).strip()

        if not reply:
            return JsonResponse(
                {
                    "error": _("The assistant could not generate a reply.")
                },
                status=502,
            )

    except HTTPError as error:
        if error.code in (429, 503):
            return JsonResponse(
                {
                    "error": _("AI is busy. Please try again shortly.")
                },
                status=503,
            )

        return JsonResponse(
            {"error": _("AI service is temporarily unavailable.")},
            status=502,
        )

    except (URLError, TimeoutError, ValueError, OSError):
        return JsonResponse(
            {"error": _("Could not connect to the AI service.")},
            status=502,
        )

    # Save only after Gemini has successfully replied.
    # Keep conversation creation and both messages together.
    with transaction.atomic():
        if conversation is None:
            conversation = AIConversation.objects.create(
                user=request.user,
                title=message[:120],
            )

        AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=message,
        )

        AIMessage.objects.create(
            conversation=conversation,
            role="model",
            content=reply[:6000],
        )

        # Move this conversation to the top of recent chats.
        conversation.save(update_fields=["updated_at"])

    return JsonResponse({
        "reply": reply,
        "conversation_id": conversation.pk,
    })


@login_required
@require_GET
def list_conversations(request):
    conversations = AIConversation.objects.filter(
        user=request.user
    ).order_by("-updated_at", "-pk")[:30]

    return JsonResponse({
        "conversations": [
            {
                "id": conversation.pk,
                "title": conversation.title,
                "updated_at": conversation.updated_at.isoformat(),
            }
            for conversation in conversations
        ]
    })


@login_required
@require_GET
def get_conversation(request, conversation_id):
    conversation = AIConversation.objects.filter(
        pk=conversation_id,
        user=request.user,
    ).first()

    if conversation is None:
        return JsonResponse(
            {"error": _("Conversation not found.")},
            status=404,
        )

    recent_messages = list(
        conversation.messages.order_by(
            "-created_at", "-pk"
        )[:100]
    )

    return JsonResponse({
        "id": conversation.pk,
        "title": conversation.title,
        "messages": [
            {
                "role": message.role,
                "text": message.content,
            }
            for message in reversed(recent_messages)
        ],
    })


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = AIConversation.objects.filter(
        pk=conversation_id,
        user=request.user,
    ).first()

    if conversation is None:
        return JsonResponse(
            {"error": _("Conversation not found.")},
            status=404,
        )

    conversation.delete()

    return JsonResponse({
        "success": True,
    })




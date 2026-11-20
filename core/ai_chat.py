
import json
import time
import os
import re
from datetime import date, time as datetime_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_GET, require_POST
from .models import AIConversation, AIMessage, AIUsageLimit, AIUsageGlobal, AITaskProposal, Task, SPACES, Profile
from .forms import TaskForm
from .app_knowledge import PAMOJA_APP_GUIDE


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

When a user wants to create a Planner task, use the propose_task tool
when you have a clear title and due date. A proposal is NOT a saved task.
Never claim a task has been saved until the application confirms it.
If the user has not specified a due date, ask when the task is due.
If a Space is unclear, use planning. If priority is unclear, use normal.
Do not invent a due time. Do not call the tool for unrelated questions.
You can propose a task for review, but cannot edit or delete existing tasks.

Do not request passwords or sensitive account credentials.
Respond in the user's language when possible.
"""

TASK_TOOL = {
    "functionDeclarations": [{
        "name": "propose_task",
        "description": (
            "Prepare a task proposal for user review when the user explicitly "
            "wants to add a Planner task. Never save it. Ask for a due date "
            "in ordinary chat if the due date is missing."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Short task title, maximum 160 characters"},
                "due_date": {"type": "STRING", "description": "ISO date YYYY-MM-DD in user's local timezone"},
                "space": {"type": "STRING", "description": "One of the supplied PAMOJA Space keys"},
                "priority": {"type": "STRING", "description": "normal or high"},
                "due_time": {"type": "STRING", "description": "Optional local 24-hour time HH:MM; omit unless user gives a time"},
            },
            "required": ["title", "due_date"],
        },
    }]
}


def _local_today(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    try:
        zone = ZoneInfo(profile.timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = ZoneInfo("UTC")
    return timezone.localdate(timezone=zone), profile


def _proposal_from_tool(args):
    """Reject malformed model output before it ever reaches the database."""
    if not isinstance(args, dict):
        return None
    title = args.get("title")
    due_date = args.get("due_date")
    if not isinstance(title, str) or not 0 < len(title.strip()) <= 160:
        return None
    if not isinstance(due_date, str):
        return None
    try:
        day = date.fromisoformat(due_date)
    except ValueError:
        return None
    if day.isoformat() != due_date:
        return None
    space = args.get("space", "planning")
    if space not in dict(SPACES):
        space = "planning"
    priority = args.get("priority", "normal")
    if priority not in ("normal", "high"):
        priority = "normal"
    raw_time = args.get("due_time")
    parsed_time = None
    if raw_time not in (None, ""):
        if not isinstance(raw_time, str) or not re.fullmatch(r"\d{2}:\d{2}", raw_time):
            return None
        try:
            parsed_time = datetime_time.fromisoformat(raw_time)
        except ValueError:
            return None
    return {"title": title.strip(), "due_date": day,
            "due_time": parsed_time, "space": space, "priority": priority}


def _proposal_json(proposal):
    return {
        "id": proposal.pk,
        "title": proposal.title,
        "space": proposal.space,
        "due_date": proposal.due_date.isoformat(),
        "due_time": proposal.due_time.strftime("%H:%M") if proposal.due_time else "",
        "priority": proposal.priority,
        "saved": proposal.saved_at is not None,
        "planner_url": reverse("planner") if proposal.saved_at else None,
    }


def _testing_restricted(user):
    testing_only = os.environ.get("PAMOJA_AI_TESTING_ONLY", "").lower() in ("true", "1", "yes")
    return testing_only and not user.is_staff


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

    # Restrict production AI Chat to staff during Free-tier testing.
    if _testing_restricted(request.user):
        return JsonResponse(
            {"error": _("AI Chat is currently in private testing.")},
            status=403,
        )
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
    today, profile = _local_today(request.user)
    available_spaces = ", ".join(key for key, _ in SPACES)

    data = {
        "system_instruction": {
            "parts": [{
                "text": (
                    SYSTEM_INSTRUCTIONS
                    + "\n" + PAMOJA_APP_GUIDE
                    + f"\nPreferred interface language: {language}."
                    + f"\nUser's current local date: {today.isoformat()}."
                    + f"\nUser's timezone: {profile.timezone}."
                    + f"\nValid task Space keys: {available_spaces}."
                    + "\nFor relative dates like tomorrow, calculate from the user's local date."
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
        "tools": [TASK_TOOL],
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

        tool_args = None
        for part in parts:
            if not isinstance(part, dict):
                continue
            function_call = part.get("functionCall")
            if isinstance(function_call, dict) and function_call.get("name") == "propose_task":
                tool_args = function_call.get("args")
                break

        proposed_fields = _proposal_from_tool(tool_args) if tool_args is not None else None
        reply = "\n".join(
            part["text"]
            for part in parts
            if isinstance(part, dict)
            and isinstance(part.get("text"), str)
        ).strip()

        if proposed_fields:
            reply = _("I've prepared a task for you. Review the details below, then choose Save to Planner. Nothing has been saved yet.")
        elif tool_args is not None:
            reply = _("I couldn't prepare that task yet. Please tell me the task title and due date.")

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

        assistant_message = AIMessage.objects.create(
            conversation=conversation,
            role="model",
            content=reply[:6000],
        )
        proposal = (
            AITaskProposal.objects.create(message=assistant_message, **proposed_fields)
            if proposed_fields else None
        )

        # Move this conversation to the top of recent chats.
        conversation.save(update_fields=["updated_at"])

    return JsonResponse({
        "reply": reply,
        "conversation_id": conversation.pk,
        "task_proposal": _proposal_json(proposal) if proposal else None,
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
        conversation.messages.select_related("task_proposal").order_by(
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
                "task_proposal": (
                    _proposal_json(message.task_proposal)
                    if hasattr(message, "task_proposal") else None
                ),
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




@login_required
@require_POST
def save_task_proposal(request, proposal_id):
    """The user's explicit, CSRF-protected approval is the only write path."""
    if _testing_restricted(request.user):
        return JsonResponse({"error": _("AI Chat is currently in private testing.")}, status=403)
    if len(request.body) > 4000:
        return JsonResponse({"error": _("Task details are too large.")}, status=400)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": _("Invalid task details.")}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": _("Invalid task details.")}, status=400)

    with transaction.atomic():
        proposal = (
            AITaskProposal.objects.select_for_update()
            .filter(pk=proposal_id, message__conversation__user=request.user)
            .first()
        )
        if proposal is None:
            return JsonResponse({"error": _("Task proposal not found.")}, status=404)
        if proposal.saved_at is not None:
            return JsonResponse({"success": True, "task_proposal": _proposal_json(proposal)})

        title = data.get("title")
        due_date = data.get("due_date")
        space = data.get("space")
        priority = data.get("priority")
        raw_time = data.get("due_time", "")
        if not all(isinstance(x, str) for x in (title, due_date, space, priority, raw_time)):
            return JsonResponse({"error": _("Invalid task details.")}, status=400)
        if len(title) > 160 or len(raw_time) > 5:
            return JsonResponse({"error": _("Invalid task details.")}, status=400)

        form_data = {
            "title": title, "space": space,
            "due_date": due_date, "priority": priority,
            "due_time_0": "", "due_time_1": "", "due_time_2": "",
        }
        if raw_time:
            if not re.fullmatch(r"\d{2}:\d{2}", raw_time):
                return JsonResponse({"error": _("Invalid time format.")}, status=400)
            try:
                due_time = datetime_time.fromisoformat(raw_time)
            except ValueError:
                return JsonResponse({"error": _("Invalid time format.")}, status=400)
            form_data.update({
                "due_time_0": str(due_time.hour % 12 or 12),
                "due_time_1": f"{due_time.minute:02d}",
                "due_time_2": "PM" if due_time.hour >= 12 else "AM",
            })

        form = TaskForm(form_data)
        if not form.is_valid():
            return JsonResponse({"error": _("Please correct the task details."), "fields": form.errors.get_json_data()}, status=400)

        task = form.save(commit=False)
        task.user = request.user
        task.save()
        proposal.task = task
        proposal.saved_at = timezone.now()
        proposal.save(update_fields=["task", "saved_at"])

    return JsonResponse({"success": True, "task_proposal": _proposal_json(proposal)})

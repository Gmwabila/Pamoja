import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import PushSubscription
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_GET

@require_GET
def health(request):
    return HttpResponse('ok', content_type='text/plain', headers={'Cache-Control': 'no-store'})

from .forms import SignupForm, LoginForm, PreferencesForm, TaskForm
from .models import Profile, Task, SPACES, Notification
from .notifications import generate_notifications

def get_profile(user):
    return Profile.objects.get_or_create(user=user)[0]

def today_for(profile):
    return timezone.localdate(timezone=ZoneInfo(profile.timezone))

def welcome(request):
    return render(request, 'core/welcome.html')

class PamojaLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'registration/login.html'

def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        Profile.objects.create(
            user=user,
            language=get_language() or "en",
        )
        login(request, user)
        return redirect('onboarding')
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def onboarding(request):
    profile = get_profile(request.user)
    form = PreferencesForm(request.POST or None, instance=profile,
                           initial={'spaces': ['planning', 'career', 'fitness']} if not profile.onboarded else None)
    if request.method == 'POST' and form.is_valid():
        profile = form.save(commit=False)
        profile.onboarded = True
        profile.save()
        messages.success(request, _('Your space is ready. Let’s take the next step together.'))
        return redirect('dashboard')
    return render(request, 'core/onboarding.html', {'form': form, 'editing': profile.onboarded})

@login_required
def dashboard(request):
    profile = get_profile(request.user)
    if not profile.onboarded:
        return redirect('onboarding')

    generate_notifications(request.user)

    today = today_for(profile)
    tasks = Task.objects.filter(user=request.user, due_date=today)
    done = tasks.filter(completed=True).count()
    total = tasks.count()
    upcoming = Task.objects.filter(user=request.user, completed=False,
        due_date__gt=today, due_date__lte=today + timedelta(days=7)).order_by(
        'due_date', F('due_time').asc(nulls_last=True), 'pk')
    upcoming_count = upcoming.count()
    labels = dict(SPACES)
    spaces = [{'key': key, 'label': labels[key]} for key in profile.spaces if key in labels]
    now = timezone.localtime(timezone.now(), ZoneInfo(profile.timezone))

    if now.hour < 12:
        greeting = _("Good morning")
    elif now.hour < 18:
        greeting = _("Good afternoon")
    else:
        greeting = _("Good evening")

    return render(request, 'core/dashboard.html', {
        'tasks': tasks,
        'today': today,
        'done': done,
        'total': total,
        'progress': round(done / total * 100) if total else 0,
        'spaces': spaces,
        'greeting': greeting,
        'profile': profile,
        'upcoming_tasks': upcoming[:5],
        'upcoming_count': upcoming_count,
        'tomorrow': today + timedelta(days=1),
        'overdue': Task.objects.filter(
            user=request.user,
            due_date__lt=today,
            completed=False
        ).count()
    })
@login_required
def planner(request):
    profile = get_profile(request.user)
    tasks = Task.objects.filter(user=request.user)
    selected = request.GET.get('space', '')
    if selected in dict(SPACES):
        tasks = tasks.filter(space=selected)
    if request.GET.get('show') != 'all':
        tasks = tasks.filter(completed=False)
    return render(request, 'core/planner.html', {'tasks': tasks, 'spaces': SPACES, 'selected': selected,
                    'show_all': request.GET.get('show') == 'all', 'today': today_for(profile)})

@login_required
def task_edit(request, pk=None):
    task = get_object_or_404(Task, user=request.user, pk=pk) if pk else None
    initial = None
    if task is None:
        initial = {
            'due_date': today_for(get_profile(request.user)),
            'space': 'planning',
            'priority': 'normal',
        }
        # The AI guide only pre-fills this form. A separate POST and
        # explicit Save task action are still required to create data.
        if request.method == 'GET':
            title = request.GET.get('title', '').strip()
            if 0 < len(title) <= 160:
                initial['title'] = title
            space = request.GET.get('space', '')
            if space in dict(SPACES):
                initial['space'] = space
            if request.GET.get('priority') in ('normal', 'high'):
                initial['priority'] = request.GET['priority']
            try:
                initial['due_date'] = date.fromisoformat(request.GET['due_date'])
            except (KeyError, ValueError):
                pass
            try:
                due_time = time.fromisoformat(request.GET['due_time'])
                if due_time.tzinfo is None:
                    initial['due_time'] = due_time
            except (KeyError, ValueError):
                pass
    form = TaskForm(request.POST or None, instance=task, initial=initial)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.save()
        messages.success(request, 'Task saved.')
        return redirect('dashboard')
    return render(request, 'core/task_form.html', {'form': form, 'editing': task is not None})

@login_required
@require_POST
def task_toggle(request, pk):
    task = get_object_or_404(Task, user=request.user, pk=pk)
    task.completed = not task.completed
    task.save(update_fields=['completed'])
    return redirect('planner' if request.POST.get('origin') == 'planner' else 'dashboard')

@login_required
@require_POST
def task_delete(request, pk):
    get_object_or_404(Task, user=request.user, pk=pk).delete()
    messages.success(request, 'Task deleted.')
    return redirect('planner')

@login_required
@require_POST
def move_space(request, key):
    profile = get_profile(request.user)
    if key in profile.spaces:
        spaces = list(profile.spaces)
        index = spaces.index(key)
        target = index - 1 if request.POST.get('direction') == 'up' else index + 1
        if 0 <= target < len(spaces):
            spaces[index], spaces[target] = spaces[target], spaces[index]
            profile.spaces = spaces
            profile.save(update_fields=['spaces'])
    return redirect('dashboard')


@login_required
def profile(request):
    user_profile = get_profile(request.user)
    labels = dict(SPACES)

    selected_spaces = [
        labels[key]
        for key in user_profile.spaces
        if key in labels
    ]

    return render(request, "core/profile.html", {
        "profile": user_profile,
        "selected_spaces": selected_spaces,
    })


@login_required
def chat(request):
    return render(request, 'core/chat.html', {
        'task_spaces': SPACES,
        'task_today': today_for(get_profile(request.user)),
    })

def service_worker(request):
    script = """
self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', event => {
    if (!event.data) return;

    let data;

    try {
        data = event.data.json();
    } catch (error) {
        return;
    }

    const title = data.title || 'PAMOJA';
    const options = {
        body: data.message || 'You have a new notification.',
        icon: '/static/core/icons/icon-192.png',
        badge: '/static/core/icons/icon-192.png',
        tag: data.tag || 'pamoja-notification',
        data: {
            url: '/notifications/'
        }
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();

    event.waitUntil(
        clients.openWindow('/notifications/')
    );
});
"""
    return HttpResponse(
        script,
        content_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )

@login_required
def notification_center(request):
    generate_notifications(request.user)

    notifications = Notification.objects.filter(
        user=request.user
    )[:50]

    return render(
        request,
        "core/notifications.html",
        {"notifications": notifications},
    )


@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        user=request.user,
    )
    notification.is_read = True
    notification.save(update_fields=["is_read"])

    return redirect("notifications")


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(
        user=request.user,
        is_read=False,
    ).update(is_read=True)

    return redirect("notifications")
@login_required
@require_GET
def push_public_key(request):
    if not settings.VAPID_PUBLIC_KEY:
        return JsonResponse(
            {"error": "Push notifications are not configured."},
            status=503,
        )

    return JsonResponse({
        "publicKey": settings.VAPID_PUBLIC_KEY,
    })


@login_required
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body)
        subscription = data["subscription"]
        endpoint = subscription["endpoint"]
        keys = subscription["keys"]
        p256dh = keys["p256dh"]
        auth = keys["auth"]

        if not all(
            isinstance(value, str) and value.strip()
            for value in (endpoint, p256dh, auth)
        ):
            raise ValueError("Invalid subscription")

        if not endpoint.startswith("https://"):
            raise ValueError("Invalid endpoint")

    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse(
            {"error": "Invalid subscription data."},
            status=400,
        )

    existing = PushSubscription.objects.filter(
        endpoint=endpoint,
    ).first()

    if existing and existing.user_id != request.user.pk:
        return JsonResponse(
            {"error": "Subscription already registered."},
            status=409,
        )

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
        },
    )

    return JsonResponse({"success": True})


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]

        if not isinstance(endpoint, str) or not endpoint:
            raise ValueError("Invalid endpoint")

    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse(
            {"error": "Invalid endpoint."},
            status=400,
        )

    PushSubscription.objects.filter(
        user=request.user,
        endpoint=endpoint,
    ).delete()

    return JsonResponse({"success": True})

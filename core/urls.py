from django.contrib.auth.views import LogoutView
from .languages import change_language
from django.urls import path

from . import ai_chat, feedback_replies, owner_tools, views
from .owner_stats import owner_dashboard


urlpatterns = [
    # Owner dashboard
    path(
        "language/",
        change_language,
        name="change_language",
    ),
    path(
        "owner/",
        owner_dashboard,
        name="owner_dashboard",
    ),
    path(
        "owner/feedback/",
        owner_tools.owner_feedback,
        name="owner_feedback",
    ),
    path(
        "owner/feedback/<int:pk>/status/",
        owner_tools.owner_feedback_status,
        name="owner_feedback_status",
    ),
    path(
        "owner/feedback/<int:pk>/reply/",
        feedback_replies.owner_reply,
        name="owner_reply",
    ),
    path(
        "owner/health/",
        owner_tools.owner_health,
        name="owner_health",
    ),

    # Main pages
    path("", views.welcome, name="welcome"),
    path("signup/", views.signup, name="signup"),
    path(
        "login/",
        views.PamojaLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "onboarding/",
        views.onboarding,
        name="onboarding",
    ),
    path(
        "dashboard/",
        views.dashboard,
        name="dashboard",
    ),
    path("planner/", views.planner, name="planner"),
    path("profile/", views.profile, name="profile"),
    path("chat/", views.chat, name="chat"),
    path("chat/message/", ai_chat.send_message, name="chat_message"),


    path(
        "chat/conversations/",
        ai_chat.list_conversations,
        name="chat_conversations",
    ),
    path(
        "chat/conversations/<int:conversation_id>/",
    ai_chat.get_conversation,
    name="chat_conversation_detail",
    ),
    path(
        "chat/conversations/<int:conversation_id>/delete/",
        ai_chat.delete_conversation,
        name="chat_conversation_delete",
    ),

    # User feedback
    path(
        "feedback/",
        owner_tools.submit_feedback,
        name="feedback",
    ),
    path(
        "feedback/mine/",
        feedback_replies.my_feedback,
        name="my_feedback",
    ),

    # Notifications
    path(
        "notifications/",
        views.notification_center,
        name="notifications",
    ),
    path(
        "notifications/<int:pk>/read/",
        views.notification_mark_read,
        name="notification_mark_read",
    ),
    path(
        "notifications/read-all/",
        views.notifications_mark_all_read,
        name="notifications_mark_all_read",
    ),

    # Tasks
    path(
        "tasks/new/",
        views.task_edit,
        name="task_add",
    ),
    path(
        "tasks/<int:pk>/edit/",
        views.task_edit,
        name="task_edit",
    ),
    path(
        "tasks/<int:pk>/toggle/",
        views.task_toggle,
        name="task_toggle",
    ),
    path(
        "tasks/<int:pk>/delete/",
        views.task_delete,
        name="task_delete",
    ),

    # Spaces
    path(
        "spaces/<str:key>/move/",
        views.move_space,
        name="move_space",
    ),

    # Health and PWA
    path("healthz/", views.health, name="health"),
    path(
        "sw.js",
        views.service_worker,
        name="service_worker",
    ),
        # Web Push Notifications
    path(
        "notifications/push/public-key/",
        views.push_public_key,
        name="push_public_key",
    ),
    path(
        "notifications/push/subscribe/",
        views.push_subscribe,
        name="push_subscribe",
    ),
    path(
        "notifications/push/unsubscribe/",
        views.push_unsubscribe,
        name="push_unsubscribe",
    ),
] # comment: End of urlpatterns
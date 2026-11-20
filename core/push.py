import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)


def send_push_to_user(user, title, message, tag="pamoja"):
    """Send a Web Push message to a user's registered devices."""
    if not settings.VAPID_PUBLIC_KEY or not settings.VAPID_PRIVATE_KEY:
        return 0

    sent = 0

    subscriptions = PushSubscription.objects.filter(user=user)

    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps({
                    "title": title,
                    "message": message,
                    "tag": tag,
                }),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": settings.VAPID_SUBJECT,
                },
                ttl=3600,
            )
            sent += 1

        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)

            if status in (404, 410):
                subscription.delete()
            else:
                logger.warning(
                    "Web Push delivery failed: HTTP %s",
                    status,
                )

    return sent
def send_push_to_subscription(subscription, title, message, tag="pamoja"):
    """Send one push message to one registered device."""
    if not settings.VAPID_PUBLIC_KEY or not settings.VAPID_PRIVATE_KEY:
        logger.warning("VAPID configuration is missing.")
        return False

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({
                "title": title,
                "message": message,
                "tag": tag,
            }),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=3600,
        )
        return True

    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)

        if status in (404, 410):
            subscription.delete()
        else:
            logger.warning(
                "Push delivery failed for subscription %s: HTTP %s",
                subscription.pk,
                status,
            )

        return False
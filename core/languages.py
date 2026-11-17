from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .models import Profile


def set_language_cookie(response, language):
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )


class ProfileLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = None

        if request.user.is_authenticated:
            saved_language = (
                Profile.objects.filter(user_id=request.user.pk)
                .values_list("language", flat=True)
                .first()
            )

            if saved_language in dict(settings.LANGUAGES):
                language = saved_language
                translation.activate(language)
                request.LANGUAGE_CODE = language

        response = self.get_response(request)

        # Keep the browser preference aligned with the account.
        # A language-change response can set its own newer cookie.
        if (
            language
            and settings.LANGUAGE_COOKIE_NAME not in response.cookies
            and request.COOKIES.get(
                settings.LANGUAGE_COOKIE_NAME
            ) != language
        ):
            set_language_cookie(response, language)

        return response


@never_cache
@csrf_protect
@require_POST
def change_language(request):
    language = request.POST.get("language", "")

    if language not in dict(settings.LANGUAGES):
        return HttpResponseBadRequest("Unsupported language.")

    if request.user.is_authenticated:
        Profile.objects.update_or_create(
            user=request.user,
            defaults={"language": language},
        )

    next_url = request.POST.get("next", "/")

    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/"

    translation.activate(language)
    request.LANGUAGE_CODE = language

    response = redirect(next_url)
    set_language_cookie(response, language)
    return response
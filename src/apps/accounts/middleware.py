"""Force every signed-in user to enroll an authenticator app before using the system."""

from collections.abc import Callable

from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

# Paths a user may visit before MFA is set up.
ALLOWED_PREFIXES = (
    "/accounts/logout/",
    "/accounts/2fa/",  # allauth MFA pages (activation, recovery codes)
    "/health/",
    "/static/",
)


class RequireMFAMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            getattr(settings, "MFA_ENABLED", True)
            and getattr(settings, "MFA_REQUIRED", True)
            and user is not None
            and user.is_authenticated
            and not request.path.startswith(ALLOWED_PREFIXES)
            and not is_mfa_enabled(user)
        ):
            return redirect("mfa_activate_totp")
        return self.get_response(request)

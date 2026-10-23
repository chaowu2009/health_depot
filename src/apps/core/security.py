from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
    "interest-cohort=(), browsing-topics=()"
)


class SecurityHeadersMiddleware:
    """Headers Django doesn't set by default."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.user.is_authenticated if hasattr(request, "user") else False:
            # Pages with client data must not be cached by browsers or proxies.
            response.setdefault("Cache-Control", "no-store")
        return response

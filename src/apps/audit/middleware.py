from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .context import AuditContext, reset_context, set_context


def client_ip(request: HttpRequest) -> str | None:
    if getattr(settings, "AUDIT_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


class AuditContextMiddleware:
    """Makes the current user/IP/request ID available to audit signal handlers."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        ctx = AuditContext(
            user=user if user is not None and user.is_authenticated else None,
            ip=client_ip(request),
            user_agent=request.headers.get("User-Agent", "")[:255],
            request_id=getattr(request, "request_id", ""),
        )
        token = set_context(ctx)
        try:
            return self.get_response(request)
        finally:
            reset_context(token)

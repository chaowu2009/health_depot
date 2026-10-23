import uuid
from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse


class RequestIdMiddleware:
    """Attach a request ID to every request, response header and log line."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _is_valid_id(incoming) else uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


def _is_valid_id(value: str) -> bool:
    return 8 <= len(value) <= 64 and value.replace("-", "").isalnum()

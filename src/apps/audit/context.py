"""Per-request audit context (who, from where), available to signal handlers."""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuditContext:
    user: Any = None
    ip: str | None = None
    user_agent: str = ""
    request_id: str = ""


_EMPTY = AuditContext()
_current: ContextVar[AuditContext | None] = ContextVar("audit_context", default=None)


def get_context() -> AuditContext:
    return _current.get() or _EMPTY


def set_context(ctx: AuditContext):
    return _current.set(ctx)


def reset_context(token) -> None:
    _current.reset(token)

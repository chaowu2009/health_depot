"""Write audit entries: a database row plus a structured JSON log line.

Never pass PHI here. ``changes`` holds field *names* only, never values.
"""

from typing import Any

import structlog
from django.db import models
from django.http import HttpRequest

from .context import get_context
from .middleware import client_ip
from .models import AuditLog

log = structlog.get_logger("audit")


def _program_id_for(obj: Any) -> Any:
    """Best-effort program of a record, for filtering the audit log by program."""
    for path in ("program_id", "case.program_id", "referral.program_id"):
        target = obj
        try:
            for part in path.split("."):
                target = getattr(target, part)
        except AttributeError:
            continue
        if target is not None:
            return target
    return None


def log_event(
    action: str,
    *,
    entity: models.Model | None = None,
    entity_type: str = "",
    entity_id: str = "",
    changes: dict[str, Any] | None = None,
    actor: Any = None,
    request: HttpRequest | None = None,
) -> AuditLog:
    ctx = get_context()
    if entity is not None:
        entity_type = entity_type or entity.__class__.__name__
        entity_id = entity_id or str(entity.pk)
    if actor is None:
        req_user = getattr(request, "user", None) if request is not None else None
        actor = req_user if req_user is not None and req_user.is_authenticated else ctx.user
    ip = client_ip(request) if request is not None else ctx.ip
    user_agent = (
        request.headers.get("User-Agent", "")[:255] if request is not None else ctx.user_agent
    )
    request_id = getattr(request, "request_id", "") if request is not None else ctx.request_id

    entry = AuditLog.objects.create(
        actor=actor,
        actor_ip=ip,
        user_agent=user_agent,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        program_id=_program_id_for(entity) if entity is not None else None,
        changes=changes or {},
        request_id=request_id,
    )
    log.info(
        "audit",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=getattr(actor, "pk", None),
        ip=ip,
        changes=changes or {},
    )
    return entry


def log_read(request: HttpRequest, obj: models.Model) -> AuditLog:
    return log_event(AuditLog.Action.READ, entity=obj, request=request)


def log_export(
    request: HttpRequest, *, entity_type: str, row_count: int, filters: dict[str, Any] | None = None
) -> AuditLog:
    return log_event(
        AuditLog.Action.EXPORT,
        entity_type=entity_type,
        changes={"rows": row_count, "filters": sorted((filters or {}).keys())},
        request=request,
    )

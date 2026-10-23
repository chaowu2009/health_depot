"""Worker job: send queued emails (retry up to 5 times)."""

import structlog
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.core.scheduler import register_job

from .models import EmailOutbox

log = structlog.get_logger(__name__)
MAX_ATTEMPTS = 5


def send_pending(limit: int = 50) -> int:
    sent = 0
    batch = EmailOutbox.objects.filter(
        status=EmailOutbox.Status.PENDING, attempts__lt=MAX_ATTEMPTS
    ).order_by("created_at")[:limit]
    for item in batch:
        item.attempts += 1
        try:
            EmailMessage(
                item.subject, item.body_text, settings.DEFAULT_FROM_EMAIL, [item.to_email]
            ).send(fail_silently=False)
            item.status, item.sent_at, item.last_error = EmailOutbox.Status.SENT, timezone.now(), ""
            sent += 1
        except Exception as exc:  # noqa: BLE001 - keep the worker alive, retry later
            item.last_error = str(exc)[:500]
            if item.attempts >= MAX_ATTEMPTS:
                item.status = EmailOutbox.Status.FAILED
            log.warning("email.send_failed", outbox_id=str(item.pk), attempts=item.attempts)
        item.save(update_fields=["attempts", "status", "sent_at", "last_error", "updated_at"])
    if sent:
        log.info("email.sent", count=sent)
    return sent


@register_job("send-email-outbox", seconds=20, lock_seconds=60)
def send_email_outbox() -> None:
    send_pending()

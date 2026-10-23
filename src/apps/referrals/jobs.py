import structlog

from apps.core.scheduler import register_job

from .services import send_overdue_reminders

log = structlog.get_logger(__name__)


@register_job("overdue-reminders", seconds=3600, lock_seconds=600)
def overdue_reminders() -> None:
    count = send_overdue_reminders()
    log.info("reminders.sent", count=count)

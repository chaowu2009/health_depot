"""Scheduled-job registry and a database lock so only one worker runs each job.

Later build steps register jobs here (email outbox, overdue reminders). The worker container
runs them with APScheduler — no cloud-specific scheduler, so this works locally and in AWS.
"""

import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from pathlib import Path

import structlog
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import SchedulerLock

log = structlog.get_logger(__name__)

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
# Container tmpfs; holds only a timestamp (not sensitive).
HEARTBEAT_FILE = Path(os.environ.get("WORKER_HEARTBEAT_FILE", "/tmp/hd-heartbeat"))  # noqa: S108  # nosec


@dataclass(frozen=True)
class Job:
    name: str
    func: Callable[[], None]
    seconds: int  # run interval
    lock_seconds: int  # how long the lock is held (should exceed the job's run time)


JOBS: dict[str, Job] = {}


def acquire_lock(job_name: str, lock_seconds: int, owner: str = WORKER_ID) -> bool:
    """Take (or renew) the lock for ``job_name``. Returns False if another worker holds it."""
    now = timezone.now()
    until = now + timedelta(seconds=lock_seconds)
    try:
        with transaction.atomic():
            lock = SchedulerLock.objects.select_for_update().filter(job_name=job_name).first()
            if lock is None:
                SchedulerLock.objects.create(job_name=job_name, locked_until=until, locked_by=owner)
                return True
            if lock.locked_until > now and lock.locked_by != owner:
                return False
            lock.locked_until = until
            lock.locked_by = owner
            lock.save(update_fields=["locked_until", "locked_by"])
            return True
    except IntegrityError:  # another worker created the row at the same moment
        return False


def release_lock(job_name: str, owner: str = WORKER_ID) -> None:
    SchedulerLock.objects.filter(job_name=job_name, locked_by=owner).update(
        locked_until=timezone.now()
    )


def register_job(name: str, *, seconds: int, lock_seconds: int | None = None):
    """Decorator: register a function as a locked, recurring worker job."""

    def decorator(func: Callable[[], None]) -> Callable[[], None]:
        @wraps(func)
        def locked() -> None:
            if not acquire_lock(name, lock_seconds or seconds):
                log.debug("job.skipped_locked", job=name)
                return
            try:
                func()
            except Exception:
                log.exception("job.failed", job=name)
            finally:
                release_lock(name)

        JOBS[name] = Job(
            name=name, func=locked, seconds=seconds, lock_seconds=lock_seconds or seconds
        )
        return func

    return decorator


def write_heartbeat() -> None:
    """Touched by the worker loop; the container HEALTHCHECK checks its age."""
    HEARTBEAT_FILE.write_text(timezone.now().isoformat())


@register_job("heartbeat", seconds=60)
def heartbeat() -> None:
    log.info("worker.heartbeat", worker=WORKER_ID)

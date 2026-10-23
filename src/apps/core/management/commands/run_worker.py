import signal

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from django.core.management.base import BaseCommand

from apps.core import scheduler as registry

log = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Run the background worker: scheduled jobs (APScheduler) with database locks."

    def handle(self, *args, **options):
        # Importing app job modules registers their jobs (later build steps add these).
        from django.apps import apps as django_apps

        for config in django_apps.get_app_configs():
            if config.name.startswith("apps."):
                try:
                    __import__(f"{config.name}.jobs")
                except ModuleNotFoundError as exc:
                    if exc.name != f"{config.name}.jobs":
                        raise

        sched = BlockingScheduler(timezone="UTC")
        for job in registry.JOBS.values():
            sched.add_job(
                job.func,
                "interval",
                seconds=job.seconds,
                id=job.name,
                max_instances=1,
                coalesce=True,
            )
        sched.add_job(registry.write_heartbeat, "interval", seconds=15, id="_heartbeat_file")
        registry.write_heartbeat()

        def stop(signum, frame):
            log.info("worker.stopping", signal=signum)
            sched.shutdown(wait=False)

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        log.info("worker.started", jobs=sorted(registry.JOBS), worker=registry.WORKER_ID)
        sched.start()

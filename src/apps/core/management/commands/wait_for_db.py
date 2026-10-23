import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait until the database accepts connections."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=60)

    def handle(self, *args, **options):
        deadline = time.monotonic() + options["timeout"]
        while True:
            try:
                connection.ensure_connection()
                self.stdout.write("Database is ready.")
                return
            except OperationalError as exc:
                if time.monotonic() > deadline:
                    raise CommandError("Database not reachable before timeout.") from exc
                time.sleep(1)

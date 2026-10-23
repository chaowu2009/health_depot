"""Startup check for demos: database, storage, demo data, email delivery, logins."""

import json
import time
import urllib.request
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import connection

from apps.accounts.models import User
from apps.referrals.models import Referral


class Command(BaseCommand):
    help = "Check that the demo stack is ready and print the demo logins."

    def add_arguments(self, parser):
        parser.add_argument("--mailpit-url", default="http://mailpit:8025")

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))

    def bad(self, msg):
        self.failed = True
        self.stdout.write(self.style.ERROR(f"  ✗ {msg}"))

    def handle(self, *args, **opts):
        self.failed = False
        self.stdout.write("Health Depot stack check")
        try:
            with connection.cursor() as c:
                c.execute("SELECT version()")
                self.ok(f"Database reachable ({c.fetchone()[0].split(',')[0]})")
        except Exception as exc:  # noqa: BLE001
            self.bad(f"Database: {exc}")
        try:
            name = default_storage.save(f"healthcheck/{uuid.uuid4().hex}.txt", ContentFile(b"ok"))
            default_storage.delete(name)
            self.ok("File storage reachable (write + delete)")
        except Exception as exc:  # noqa: BLE001
            self.bad(f"File storage: {exc}")
        refs = Referral.objects.count()
        demo = User.objects.filter(email__endswith="@demo.healthdepot.local").count()
        (self.ok if refs and demo else self.bad)(
            f"Demo data loaded: {refs} referrals, {demo} demo users"
        )
        token = uuid.uuid4().hex[:8]
        try:
            send_mail(
                f"Health Depot stack check {token}",
                "Email delivery works.",
                settings.DEFAULT_FROM_EMAIL,
                ["stack-check@healthdepot.local"],
            )
            time.sleep(1)
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 - fixed local Mailpit URL
                f"{opts['mailpit_url']}/api/v1/search?query={token}",
                timeout=5,
            ) as resp:
                found = json.load(resp).get("messages_count", 0)
            (self.ok if found else self.bad)("Email reaches Mailpit (http://localhost:8025)")
        except Exception as exc:  # noqa: BLE001
            self.bad(f"Email: {exc}")
        self.stdout.write(
            "\nDemo logins (password: HealthDepot-Demo-2026!, authenticator key: "
            "HEALTHDEPOTDEMOKEYCALVERTCOUNTYM)"
        )
        for email, label in [
            ("staff", "Community Health Worker"),
            ("manager", "Program manager"),
            ("leader", "Leadership (read-only)"),
            ("admin", "System admin"),
            ("partner", "Partner — food bank"),
        ]:
            self.stdout.write(f"  {label:<26} {email}@demo.healthdepot.local")
        self.stdout.write("\nOpen https://localhost" if not self.failed else "")
        if self.failed:
            raise SystemExit(1)

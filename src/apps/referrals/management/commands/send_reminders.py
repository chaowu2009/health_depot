from django.core.management.base import BaseCommand

from apps.referrals.services import send_overdue_reminders


class Command(BaseCommand):
    help = "Send reminders for overdue referrals now (also runs hourly in the worker)."

    def handle(self, *args, **options):
        count = send_overdue_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent reminders for {count} overdue referral(s)."))

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from .backup_storage import s3_client


class Command(BaseCommand):
    help = "Upload every file in a local backup folder back into the storage bucket."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Folder created by backup_storage")

    def handle(self, *args, **options):
        src = Path(options["source"])
        if not src.is_dir():
            raise CommandError(f"{src} is not a folder")
        client = s3_client()
        count = 0
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            key = path.relative_to(src).as_posix()
            client.upload_file(str(path), settings.AWS_STORAGE_BUCKET_NAME, key)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Restored {count} file(s) from {src}"))

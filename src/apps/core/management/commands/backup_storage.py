from pathlib import Path

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand


def s3_client():
    return boto3.client(
        "s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, region_name=settings.AWS_S3_REGION_NAME
    )


class Command(BaseCommand):
    help = "Copy every object in the storage bucket into a local folder (local backups only)."

    def add_arguments(self, parser):
        parser.add_argument("destination", help="Folder to write files into")

    def handle(self, *args, **options):
        dest = Path(options["destination"])
        dest.mkdir(parents=True, exist_ok=True)
        client = s3_client()
        count = 0
        for page in client.get_paginator("list_objects_v2").paginate(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                target = (dest / key).resolve()
                if dest.resolve() not in target.parents:
                    continue  # never write outside the destination folder
                target.parent.mkdir(parents=True, exist_ok=True)
                client.download_file(settings.AWS_STORAGE_BUCKET_NAME, key, str(target))
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Backed up {count} file(s) to {dest}"))

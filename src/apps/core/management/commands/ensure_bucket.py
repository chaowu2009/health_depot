import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create the S3 bucket if it does not exist. Used locally (SeaweedFS); in AWS the bucket "
        "is created by infrastructure code and this command only verifies access."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-create", action="store_true", help="Only verify access; never create."
        )

    def handle(self, *args, **options):
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        # Credentials and FIPS endpoint selection come from the standard AWS environment.
        client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        try:
            client.head_bucket(Bucket=bucket)
            self.stdout.write(f"Bucket '{bucket}' is reachable.")
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in {"404", "NoSuchBucket", "NotFound"} or options["no_create"]:
                raise
        client.create_bucket(Bucket=bucket)
        self.stdout.write(self.style.SUCCESS(f"Created bucket '{bucket}'."))

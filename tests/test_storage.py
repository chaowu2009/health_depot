from urllib.parse import urlparse

from apps.core.storage import PrivateS3Storage


def test_presigned_url_uses_public_endpoint(settings):
    settings.AWS_S3_PUBLIC_ENDPOINT_URL = "https://localhost:9443"
    url = PrivateS3Storage().url("case-documents/example.pdf")
    parsed = urlparse(url)
    assert parsed.scheme == "https" and parsed.netloc == "localhost:9443"
    assert "X-Amz-Signature" in url
    assert "X-Amz-Expires=300" in url


def test_presigned_url_without_public_endpoint_uses_internal(settings):
    settings.AWS_S3_PUBLIC_ENDPOINT_URL = ""
    url = PrivateS3Storage().url("x.txt")
    assert "X-Amz-Signature" in url
    assert "localhost:9443" not in url


def test_no_hardcoded_aws_identifiers_in_code():
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src"
    for path in src.rglob("*.py"):
        text = path.read_text()
        for banned in ("arn:aws:", "amazonaws.com", "us-gov-west-1", "AKIA"):
            assert banned not in text, f"{banned} found in {path}"

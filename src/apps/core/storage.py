"""Private S3 storage (SeaweedFS locally, Amazon S3 in AWS) with presigned URLs.

Inside Docker the app talks to storage at an internal address (e.g., http://s3:8333), but
browsers must use a public address (e.g., https://localhost:9443 through the proxy). When
AWS_S3_PUBLIC_ENDPOINT_URL is set, presigned URLs are signed for that public address.
In AWS it is left empty and the regular S3 endpoint is used.
"""

from typing import Any

from django.conf import settings
from storages.backends.s3 import S3Storage


class PrivateS3Storage(S3Storage):
    default_acl = None
    querystring_auth = True
    file_overwrite = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._public_storage: S3Storage | None = None

    def url(
        self, name: str, parameters: Any = None, expire: Any = None, http_method: Any = None
    ) -> str:
        public_endpoint = getattr(settings, "AWS_S3_PUBLIC_ENDPOINT_URL", "")
        if not public_endpoint:
            return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
        if self._public_storage is None:
            self._public_storage = S3Storage(endpoint_url=public_endpoint)
        return self._public_storage.url(
            name, parameters=parameters, expire=expire, http_method=http_method
        )

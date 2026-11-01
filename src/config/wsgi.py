import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
_django = get_wsgi_application()


def application(environ, start_response):
    """Answer the liveness probe before Django's host checks.

    Platform health checkers (AWS ALB, DigitalOcean App Platform) call the container by IP
    address, which ALLOWED_HOSTS would reject with HTTP 400. /health/live only proves the
    process is up and reveals nothing, so it is safe to answer here. /health/ready still goes
    through Django and checks the database.
    """
    if environ.get("PATH_INFO") == "/health/live":
        start_response("200 OK", [("Content-Type", "text/plain"), ("Cache-Control", "no-store")])
        return [b"ok"]
    return _django(environ, start_response)

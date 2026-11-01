from unittest import mock

import pytest
from django.db.utils import OperationalError


def test_live_ok(client):
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.django_db
def test_ready_ok(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["database"] == "up"


@pytest.mark.django_db
def test_ready_reports_database_down_without_details(client):
    with mock.patch("apps.core.health.connection.cursor", side_effect=OperationalError("secret")):
        resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert "secret" not in resp.content.decode()


def test_health_not_redirected_to_https(client, settings):
    settings.SECURE_SSL_REDIRECT = True
    assert client.get("/health/live").status_code == 200


def test_request_id_header(client):
    resp = client.get("/health/live")
    assert len(resp["X-Request-ID"]) >= 8


def test_wsgi_liveness_answers_any_host():
    """Platform health checkers call the container by IP; /health/live must still answer."""
    from config.wsgi import application

    seen = {}

    def start_response(status, headers):
        seen["status"] = status

    body = application(
        {"PATH_INFO": "/health/live", "REQUEST_METHOD": "GET", "HTTP_HOST": "10.244.0.7:8080"},
        start_response,
    )
    assert seen["status"] == "200 OK" and b"".join(body) == b"ok"


@pytest.mark.django_db
def test_prepare_database_passes_when_tables_can_be_created(capsys):
    from django.core.management import call_command

    call_command("prepare_database")
    assert "can create tables in schema 'public'" in capsys.readouterr().out


def test_prepare_database_warns_about_locked_public_schema(capsys):
    """Locked "public" schema: a clear warning, not a crash (an already-migrated DB is fine)."""
    from django.core.management import call_command

    fake = mock.MagicMock()
    fake.cursor.return_value.__enter__.return_value.fetchone.return_value = (False,)
    with mock.patch("apps.core.management.commands.prepare_database.connection", fake):
        call_command("prepare_database")
    assert "can't create tables in schema 'public'" in capsys.readouterr().err

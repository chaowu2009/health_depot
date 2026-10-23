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

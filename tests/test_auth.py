"""Login, MFA enforcement, lockout, sessions (RFP 3.9)."""

import pytest
from django.conf import settings
from django.urls import reverse

from apps.audit.models import AuditLog
from tests.conftest import enroll_mfa
from tests.factories import UserFactory

PASSWORD = "a-long-test-password-123"


@pytest.mark.django_db
def test_login_page_renders_with_sso_placeholder(client):
    resp = client.get(reverse("account_login"), secure=True)
    html = resp.content.decode()
    assert resp.status_code == 200
    assert "Sign in with Google" in html and "SSO — configured at implementation" in html


@pytest.mark.django_db
def test_public_signup_is_closed(client):
    resp = client.post(
        reverse("account_signup"),
        {"email": "new@example.test", "password1": PASSWORD, "password2": PASSWORD},
        secure=True,
    )
    from apps.accounts.models import User

    assert not User.objects.filter(email="new@example.test").exists()
    assert resp.status_code in (200, 302)


@pytest.mark.django_db
def test_login_with_email_then_forced_mfa_enrollment(client):
    user = UserFactory(email="nomfa@example.test")
    resp = client.post(
        reverse("account_login"), {"login": user.email, "password": PASSWORD}, secure=True
    )
    assert resp.status_code == 302
    # Any app page now redirects to the authenticator setup page.
    page = client.get("/dashboard/", secure=True)
    assert page.status_code == 302 and page["Location"] == reverse("mfa_activate_totp")
    setup = client.get(reverse("mfa_activate_totp"), secure=True)
    assert setup.status_code == 200
    assert b"data:image/svg+xml" in setup.content  # QR code rendered inline (no external URL)
    assert AuditLog.objects.filter(action="LOGIN", actor=user).exists()


@pytest.mark.django_db
def test_user_with_mfa_must_enter_code_at_login(client):
    user = UserFactory()
    enroll_mfa(user)
    resp = client.post(
        reverse("account_login"), {"login": user.email, "password": PASSWORD}, secure=True
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("mfa_authenticate")
    assert client.get("/dashboard/", secure=True).status_code == 302  # not signed in yet


@pytest.mark.django_db
def test_correct_totp_code_completes_login(client):
    from allauth.mfa.totp.internal.auth import (
        format_hotp_value,
        hotp_value,
        yield_hotp_counters_from_time,
    )

    user = UserFactory()
    secret = enroll_mfa(user)
    client.post(reverse("account_login"), {"login": user.email, "password": PASSWORD}, secure=True)
    code = format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))
    resp = client.post(reverse("mfa_authenticate"), {"code": code}, secure=True)
    assert resp.status_code == 302
    assert client.get("/dashboard/", secure=True).status_code == 200


@pytest.mark.django_db
def test_mfa_requirement_exempts_health_and_logout(client):
    user = UserFactory()
    client.force_login(user)
    assert client.get("/health/live", secure=True).status_code == 200
    assert client.get(reverse("account_logout"), secure=True).status_code == 200


@pytest.mark.django_db
def test_failed_logins_are_audited_without_password(client):
    UserFactory(email="target@example.test")
    client.post(
        reverse("account_login"),
        {"login": "target@example.test", "password": "wrong-password-xyz"},
        secure=True,
    )
    entry = AuditLog.objects.get(action="LOGIN_FAILED")
    assert entry.changes == {"attempted_email": "target@example.test"}
    assert "wrong-password" not in str(entry.changes)


@pytest.mark.django_db
def test_account_locks_after_repeated_failures(client):
    user = UserFactory(email="lock@example.test")
    for _ in range(5):
        client.post(
            reverse("account_login"),
            {"login": user.email, "password": "nope-nope-nope"},
            secure=True,
        )
    # Even the correct password is refused while locked.
    resp = client.post(
        reverse("account_login"), {"login": user.email, "password": PASSWORD}, secure=True
    )
    assert resp.status_code in (200, 429)
    assert "_auth_user_id" not in client.session


def test_session_idle_timeout_is_15_minutes():
    assert settings.SESSION_COOKIE_AGE == 900
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True


def test_password_policy_minimum_12_characters():
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        validate_password("short-pass1")


@pytest.mark.django_db
def test_admin_login_goes_through_main_login(client):
    resp = client.get("/admin/login/", secure=True)
    assert resp.status_code == 302 and reverse("account_login") in resp["Location"]

import pytest
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret

from apps.accounts.models import User
from tests.factories import UserFactory


def enroll_mfa(user):
    """Give a test user an authenticator app so the MFA requirement is satisfied."""
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    return secret


@pytest.fixture(autouse=True)
def _test_settings(settings):
    """Tests don't run collectstatic or createcachetable."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    from django.core.cache import cache

    cache.clear()  # rate-limit counters must not leak between tests


@pytest.fixture
def staff_user(db):
    user = UserFactory()
    enroll_mfa(user)
    return user


@pytest.fixture
def system_admin(db):
    user = UserFactory(role=User.Role.SYSTEM_ADMIN)
    enroll_mfa(user)
    return user

"""Synthetic demo data loader."""

import pytest
from allauth.mfa.models import Authenticator
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.cases.models import Case
from apps.clients.models import Client
from apps.referrals.models import Referral, ReferralEvent

pytestmark = pytest.mark.django_db


def test_requires_demo_mode(settings):
    settings.DEMO_MODE = False
    with pytest.raises(CommandError):
        call_command("seed_demo", clients=5, referrals=5, verbosity=0)


def test_seed_and_reset(settings):
    settings.DEMO_MODE = True
    keep = User.objects.create_user(
        "owner@example.test", "a-long-test-password-123", role=User.Role.SYSTEM_ADMIN
    )
    call_command("seed_demo", clients=30, referrals=60, verbosity=0)
    assert Client.objects.count() >= 30 and Referral.objects.count() == 60
    assert ReferralEvent.objects.filter(event_type="STATUS_CHANGE").count() >= 60
    assert Case.objects.exists()
    demo = User.objects.filter(email__endswith="@demo.healthdepot.local")
    assert demo.count() == 26  # 25 demo users + the short "test" admin login
    assert Authenticator.objects.filter(user__in=demo).count() == 26  # MFA pre-enrolled
    assert set(demo.values_list("role", flat=True)) == set(User.Role.values)
    assert not AuditLog.objects.exists()  # seeding is not audited activity
    statuses = set(Referral.objects.values_list("status", flat=True))
    assert {"COMPLETED", "DECLINED"} <= statuses
    staff = User.objects.get(email="staff@demo.healthdepot.local")
    assert staff.check_password("HealthDepot-Demo-2026!")
    # Running again without --reset leaves data alone; --reset rebuilds it.
    call_command("seed_demo", clients=30, referrals=60, verbosity=0)
    assert Referral.objects.count() == 60
    call_command("seed_demo", reset=True, clients=10, referrals=20, verbosity=0)
    assert Referral.objects.count() == 20 and User.objects.filter(pk=keep.pk).exists()


def test_all_names_are_fictional_markers(settings):
    settings.DEMO_MODE = True
    call_command("seed_demo", clients=10, referrals=10, verbosity=0)
    from apps.organizations.models import Organization

    partners = Organization.objects.filter(org_type="COMMUNITY_PARTNER")
    assert partners.count() == 10 and all("(fictional)" in p.name for p in partners)


@pytest.mark.django_db
def test_test_login_is_system_admin_with_short_password(settings):
    from apps.core.management.commands.seed_demo import Command

    from .factories import HealthDepartmentFactory

    settings.DEMO_MODE = True
    HealthDepartmentFactory(slug="cchd")
    user = Command().ensure_test_user()
    assert user.email == "test@demo.healthdepot.local"
    assert user.role == "SYSTEM_ADMIN"
    assert user.check_password("test2026")
    # Running it again doesn't duplicate, and keeps a password an admin changed.
    user.set_password("a-new-longer-password-2026")
    user.save()
    Command().ensure_test_user()
    user.refresh_from_db()
    assert user.check_password("a-new-longer-password-2026")
    from apps.accounts.models import User

    assert User.objects.filter(email="test@demo.healthdepot.local").count() == 1


def test_bare_demo_username_signs_in_to_the_2fa_step(client, settings):
    from apps.core.management.commands.seed_demo import Command

    from .factories import HealthDepartmentFactory

    settings.DEMO_MODE = True
    HealthDepartmentFactory(slug="cchd")
    Command().ensure_test_user()
    resp = client.post("/accounts/login/", {"login": "test", "password": "test2026"}, secure=True)
    assert resp.status_code == 302 and "2fa" in resp["Location"]


def test_login_form_keeps_email_only_outside_demo(settings):
    from apps.accounts.forms import LoginForm

    settings.DEMO_MODE = False
    form = LoginForm(data={"login": "test", "password": "x"})
    assert not form.is_valid()
    assert "login" in form.errors

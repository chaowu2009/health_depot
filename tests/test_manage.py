"""In-app administration: users, roles, program access, MFA reset, audit log."""

import pytest
from allauth.mfa.models import Authenticator

from apps.accounts.models import User, UserProgramAccess
from apps.audit.models import AuditLog
from tests.factories import DivisionFactory, OrganizationFactory, ProgramFactory, UserFactory


def _post_user(client, url, **data):
    payload = {
        "email": "new.staff@example.test",
        "first_name": "New",
        "last_name": "Staff",
        "title": "",
        "phone": "",
        "role": User.Role.STAFF,
        "is_active": "on",
        "new_password1": "a-long-test-password-123",
        "new_password2": "a-long-test-password-123",
        "program_access-TOTAL_FORMS": "1",
        "program_access-INITIAL_FORMS": "0",
        "program_access-MIN_NUM_FORMS": "0",
        "program_access-MAX_NUM_FORMS": "1000",
    }
    payload.update(data)
    return client.post(url, payload, secure=True)


@pytest.mark.django_db
def test_staff_cannot_open_administration(client, staff_user):
    client.force_login(staff_user)
    assert client.get("/manage/users/", secure=True).status_code == 403
    assert client.get("/manage/audit/", secure=True).status_code == 403


@pytest.mark.django_db
def test_admin_creates_staff_user_with_program_access(client, system_admin):
    division = DivisionFactory()
    program = ProgramFactory(division=division)
    client.force_login(system_admin)
    resp = _post_user(
        client,
        "/manage/users/new/",
        organization=str(division.organization.pk),
        **{"program_access-0-program": str(program.pk), "program_access-0-access_level": "EDIT"},
    )
    assert resp.status_code == 302, resp.content.decode()[:2000]
    user = User.objects.get(email="new.staff@example.test")
    assert user.check_password("a-long-test-password-123")
    assert UserProgramAccess.objects.filter(user=user, program=program).exists()
    assert AuditLog.objects.filter(action="PERMISSION_CHANGE", entity_id=str(user.pk)).exists()


@pytest.mark.django_db
def test_partner_role_requires_partner_organization(client, system_admin):
    division = DivisionFactory()
    client.force_login(system_admin)
    resp = _post_user(
        client,
        "/manage/users/new/",
        role=User.Role.PARTNER_USER,
        organization=str(division.organization.pk),
    )
    assert resp.status_code == 200
    assert b"Partner users must belong to a partner organization" in resp.content


@pytest.mark.django_db
def test_weak_password_rejected(client, system_admin):
    partner = OrganizationFactory()
    client.force_login(system_admin)
    resp = _post_user(
        client,
        "/manage/users/new/",
        role=User.Role.PARTNER_USER,
        organization=str(partner.pk),
        new_password1="short",
        new_password2="short",
    )
    assert resp.status_code == 200
    assert not User.objects.filter(email="new.staff@example.test").exists()


@pytest.mark.django_db
def test_admin_cannot_demote_themselves(client, system_admin):
    org = DivisionFactory().organization
    system_admin.organization = org
    system_admin.save()
    client.force_login(system_admin)
    resp = _post_user(
        client,
        f"/manage/users/{system_admin.pk}/",
        email=system_admin.email,
        role=User.Role.STAFF,
        organization=str(org.pk),
        new_password1="",
        new_password2="",
    )
    assert resp.status_code == 200
    system_admin.refresh_from_db()
    assert system_admin.role == User.Role.SYSTEM_ADMIN


@pytest.mark.django_db
def test_admin_can_reset_a_users_mfa(client, system_admin, staff_user):
    client.force_login(system_admin)
    resp = client.post(f"/manage/users/{staff_user.pk}/reset-mfa/", secure=True)
    assert resp.status_code == 302
    assert not Authenticator.objects.filter(user=staff_user).exists()


@pytest.mark.django_db
def test_audit_log_page_filters_by_action(client, system_admin):
    AuditLog.objects.create(action="EXPORT", entity_type="Referral")
    AuditLog.objects.create(action="READ", entity_type="Client")
    client.force_login(system_admin)
    resp = client.get("/manage/audit/?action=EXPORT", secure=True)
    assert resp.status_code == 200
    entries = list(resp.context["entries"])
    assert entries and all(e.action == "EXPORT" for e in entries)


@pytest.mark.django_db
def test_user_list_shows_mfa_status(client, system_admin):
    UserFactory(email="pending@example.test")
    client.force_login(system_admin)
    html = client.get("/manage/users/", secure=True).content.decode()
    assert "pending@example.test" in html and "Not set up" in html and "Enrolled" in html

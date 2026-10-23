import pytest


@pytest.mark.django_db
def test_staff_cannot_use_admin(client, staff_user):
    client.force_login(staff_user)
    resp = client.get("/admin/", secure=True)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"] or "/admin/login/" in resp["Location"]


@pytest.mark.django_db
def test_system_admin_can_use_admin(client, system_admin):
    client.force_login(system_admin)
    assert client.get("/admin/", secure=True).status_code == 200


@pytest.mark.django_db
def test_audit_log_admin_is_read_only(client, system_admin):
    client.force_login(system_admin)
    assert client.get("/admin/audit/auditlog/add/", secure=True).status_code == 403

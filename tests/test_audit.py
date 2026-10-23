"""Audit log: automatic entries, no PHI values, append-only (RFP 3.9)."""

import pytest

from apps.accounts.models import User, UserProgramAccess
from apps.audit.context import AuditContext, reset_context, set_context
from apps.audit.models import AuditLog
from tests.factories import ClientFactory, ProgramFactory, UserFactory


@pytest.mark.django_db
def test_client_create_and_update_logged_with_field_names_only():
    actor = UserFactory()
    token = set_context(AuditContext(user=actor, ip="10.0.0.5", request_id="req-123"))
    try:
        client = ClientFactory(first_name="Synthetic", phone="410-555-0100")
        client.phone = "410-555-0199"
        client.save()
    finally:
        reset_context(token)

    created = AuditLog.objects.get(action="CREATE", entity_type="Client")
    assert created.actor == actor and created.actor_ip == "10.0.0.5"
    updated = AuditLog.objects.get(action="UPDATE", entity_type="Client")
    assert updated.changes == {"fields": ["phone"]}
    assert "410-555" not in str(updated.changes)


@pytest.mark.django_db
def test_saving_without_changes_does_not_log_update():
    client = ClientFactory()
    client.save()
    assert not AuditLog.objects.filter(action="UPDATE", entity_type="Client").exists()


@pytest.mark.django_db
def test_role_change_and_program_access_are_permission_changes():
    user = UserFactory(role=User.Role.STAFF)
    user.role = User.Role.READ_ONLY
    user.save()
    UserProgramAccess.objects.create(user=user, program=ProgramFactory())
    changes = list(AuditLog.objects.filter(action="PERMISSION_CHANGE", entity_id=str(user.pk)))
    assert len(changes) == 2
    assert changes[-1].changes["fields"] == ["role"] or changes[0].changes["fields"] == ["role"]


@pytest.mark.django_db
def test_audit_entries_cannot_be_changed_or_deleted():
    entry = AuditLog.objects.create(action="READ", entity_type="Client")
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()


@pytest.mark.django_db
def test_audit_log_also_written_as_json_log_line(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="audit")
    ClientFactory()
    assert any("audit" in r.getMessage() or r.name == "audit" for r in caplog.records)

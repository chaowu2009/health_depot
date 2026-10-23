import pytest
from django.contrib.auth.hashers import identify_hasher

from apps.audit.models import AuditLog
from tests.factories import ReferralFactory, UserFactory


@pytest.mark.django_db
def test_referral_chain_and_uuid_ids():
    referral = ReferralFactory()
    assert referral.status == "SUBMITTED"
    assert len(str(referral.id)) == 36  # UUID, not a guessable integer
    assert referral.receiving_organization.org_type == "HEALTH_DEPARTMENT"


@pytest.mark.django_db
def test_passwords_use_fips_friendly_pbkdf2():
    user = UserFactory()
    assert identify_hasher(user.password).algorithm == "pbkdf2_sha256"


@pytest.mark.django_db
def test_email_is_login_and_normalized():
    from apps.accounts.models import User

    user = User.objects.create_user("Someone@Example.TEST", "a-long-test-password-123")
    assert user.email == "someone@example.test"
    assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_audit_log_is_append_only():
    entry = AuditLog.objects.create(action=AuditLog.Action.READ, entity_type="Client")
    entry.entity_type = "Changed"
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()

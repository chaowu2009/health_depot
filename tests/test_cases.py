"""Case management, client profiles, My Work (RFP 3.5)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User, UserProgramAccess
from apps.audit.models import AuditLog
from apps.cases import services
from apps.cases.models import Case
from apps.notifications.models import Notification
from apps.referrals.services import change_status
from tests.conftest import enroll_mfa
from tests.factories import (
    ClientFactory,
    OrganizationFactory,
    ProgramFactory,
    ReferralFactory,
    UserFactory,
)


@pytest.fixture
def ctx(db, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    }
    call_command("bootstrap", verbosity=0)
    from apps.organizations.models import Organization

    cchd = Organization.objects.get(slug="cchd")
    program = ProgramFactory()
    staff = UserFactory(role=User.Role.STAFF, organization=cchd)
    UserProgramAccess.objects.create(user=staff, program=program)
    enroll_mfa(staff)
    now = timezone.now()
    referral = ReferralFactory(
        program=program,
        sending_organization=OrganizationFactory(),
        receiving_organization=cchd,
        submitted_at=now,
        last_status_change_at=now,
    )
    return {"program": program, "staff": staff, "referral": referral, "cchd": cchd}


def test_open_case_from_accepted_referral(client, ctx):
    client.force_login(ctx["staff"])
    resp = client.post(f"/cases/from-referral/{ctx['referral'].pk}/", secure=True)
    assert resp.status_code == 302 and Case.objects.count() == 0  # not accepted yet
    change_status(ctx["referral"], "ACCEPTED", user=ctx["staff"])
    resp = client.post(f"/cases/from-referral/{ctx['referral'].pk}/", secure=True)
    case = Case.objects.get()
    assert resp["Location"] == f"/cases/{case.pk}/"
    ctx["referral"].refresh_from_db()
    assert ctx["referral"].case == case and case.client == ctx["referral"].client


def test_case_page_actions_end_to_end(client, ctx):
    case = services.create_case(
        client=ctx["referral"].client,
        program=ctx["program"],
        manager=ctx["staff"],
        user=ctx["staff"],
    )
    other = UserFactory(role=User.Role.STAFF)
    UserProgramAccess.objects.create(user=other, program=ctx["program"])
    client.force_login(ctx["staff"])
    base = f"/cases/{case.pk}/do/"
    client.post(
        base + "goal/", {"description": "Stable housing", "target_date": "2026-12-31"}, secure=True
    )
    client.post(
        base + "task/",
        {
            "title": "Call landlord",
            "assigned_to": other.pk,
            "due_date": "2026-11-01",
            "priority": "HIGH",
        },
        secure=True,
    )
    client.post(
        base + "note/",
        {"note_type": "PHONE", "contact_date": "2026-10-18", "body": "Spoke with client."},
        secure=True,
    )
    pdf = SimpleUploadedFile("consent.pdf", b"%PDF-1.4 synthetic", content_type="application/pdf")
    client.post(base + "document/", {"file": pdf, "document_type": "CONSENT"}, secure=True)
    case.refresh_from_db()
    assert case.goals.count() == 1 and case.tasks.count() == 1 and case.documents.count() == 1
    assert case.notes.filter(body="Spoke with client.").exists()
    assert Notification.objects.filter(recipient=other, verb="CASE_TASK").exists()
    doc = case.documents.get()
    assert doc.filename == "consent.pdf" and "consent" not in doc.file.name
    task = case.tasks.get()
    client.post(base + "task-toggle/", {"task": task.pk}, secure=True)
    task.refresh_from_db()
    assert task.completed_at is not None
    html = client.get(f"/cases/{case.pk}/", secure=True).content.decode()
    assert "Stable housing" in html and "Save to Google Drive" in html
    client.post(
        base + "discharge/",
        {"reason": "GOALS_MET", "outcome": "IMPROVED", "notes": "Housed."},
        secure=True,
    )
    case.refresh_from_db()
    assert case.status == "DISCHARGED" and case.discharged_at
    assert AuditLog.objects.filter(entity_type="Case", action="UPDATE").exists()


def test_bad_document_rejected(client, ctx):
    case = services.create_case(
        client=ctx["referral"].client,
        program=ctx["program"],
        manager=ctx["staff"],
        user=ctx["staff"],
    )
    client.force_login(ctx["staff"])
    exe = SimpleUploadedFile("x.exe", b"MZ\x90\x00", content_type="application/octet-stream")
    client.post(
        f"/cases/{case.pk}/do/document/", {"file": exe, "document_type": "OTHER"}, secure=True
    )
    assert case.documents.count() == 0


def test_document_download_checks_scope_and_audits(client, ctx):
    case = services.create_case(
        client=ctx["referral"].client,
        program=ctx["program"],
        manager=ctx["staff"],
        user=ctx["staff"],
    )
    doc = services.add_document(
        case,
        upload=SimpleUploadedFile("a.pdf", b"%PDF-1.4"),
        document_type="OTHER",
        user=ctx["staff"],
    )
    outsider = UserFactory(role=User.Role.STAFF)
    UserProgramAccess.objects.create(user=outsider, program=ProgramFactory())
    enroll_mfa(outsider)
    client.force_login(outsider)
    assert client.get(f"/cases/documents/{doc.pk}/", secure=True).status_code == 404
    assert client.get(f"/cases/{case.pk}/", secure=True).status_code == 404
    client.force_login(ctx["staff"])
    assert client.get(f"/cases/documents/{doc.pk}/", secure=True).status_code == 302
    assert AuditLog.objects.filter(action="READ", entity_type="CaseDocument").exists()


def test_partner_users_cannot_reach_cases_or_clients(client, ctx):
    partner = UserFactory(role=User.Role.PARTNER_USER, organization=OrganizationFactory())
    enroll_mfa(partner)
    client.force_login(partner)
    assert client.get("/cases/", secure=True).status_code == 403
    assert client.get("/clients/", secure=True).status_code == 403
    assert client.get("/my-work/", secure=True).status_code == 403


def test_client_profile_and_duplicate_review(client, ctx):
    original = ctx["referral"].client
    dup = ClientFactory(date_of_birth=original.date_of_birth, possible_duplicate_of=original)
    from apps.clients.models import ClientProgram

    ClientProgram.objects.create(client=dup, program=ctx["program"])
    client.force_login(ctx["staff"])
    html = client.get(f"/clients/{dup.pk}/", secure=True).content.decode()
    assert "may be the same person" in html
    client.post(f"/clients/{dup.pk}/not-duplicate/", secure=True)
    dup.refresh_from_db()
    assert dup.possible_duplicate_of is None
    page = client.get(f"/clients/{original.pk}/", secure=True).content.decode()
    assert ctx["referral"].reference_number in page


def test_my_work_lists_tasks_and_cases(client, ctx):
    case = services.create_case(
        client=ctx["referral"].client,
        program=ctx["program"],
        manager=ctx["staff"],
        user=ctx["staff"],
    )
    services.add_task(
        case,
        title="Follow up call",
        assigned_to=ctx["staff"],
        due_date=None,
        priority="NORMAL",
        user=ctx["staff"],
    )
    client.force_login(ctx["staff"])
    html = client.get("/my-work/", secure=True).content.decode()
    assert "Follow up call" in html and case.case_number in html

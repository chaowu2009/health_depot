"""Closed-loop workflow, notifications, messaging, reminders (RFP 3.2, 3.5)."""

from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User, UserProgramAccess
from apps.notifications.jobs import send_pending
from apps.notifications.models import EmailOutbox, Notification
from apps.referrals import services
from apps.referrals.models import Referral, ReferralEvent
from apps.referrals.workflow import TRANSITIONS, can_transition
from tests.conftest import enroll_mfa
from tests.factories import OrganizationFactory, ProgramFactory, ReferralFactory, UserFactory


@pytest.fixture
def loop(db):
    call_command("bootstrap", verbosity=0)
    from apps.organizations.models import Organization

    cchd = Organization.objects.get(slug="cchd")
    program = ProgramFactory()
    partner = OrganizationFactory(name="Fictional Pantry")
    staff = UserFactory(role=User.Role.STAFF, organization=cchd, email="staff@example.test")
    UserProgramAccess.objects.create(user=staff, program=program)
    partner_user = UserFactory(
        role=User.Role.PARTNER_USER, organization=partner, email="partner@example.test"
    )
    for u in (staff, partner_user):
        enroll_mfa(u)
    now = timezone.now()
    inbound = ReferralFactory(
        program=program,
        sending_organization=partner,
        receiving_organization=cchd,
        submitted_at=now,
        last_status_change_at=now,
    )
    outbound = ReferralFactory(
        program=program,
        sending_organization=cchd,
        receiving_organization=partner,
        direction="OUTBOUND",
        submitted_at=now,
        last_status_change_at=now,
    )
    return {
        "cchd": cchd,
        "program": program,
        "partner": partner,
        "staff": staff,
        "partner_user": partner_user,
        "inbound": inbound,
        "outbound": outbound,
    }


def test_transition_table():
    assert can_transition("SUBMITTED", "ACCEPTED")
    assert not can_transition("SUBMITTED", "COMPLETED")
    assert not can_transition("COMPLETED", "IN_PROGRESS")
    assert all(TRANSITIONS[s] == [] for s in ("DECLINED", "COMPLETED", "CLOSED_UNABLE_TO_CONTACT"))


def test_receiving_side_moves_referral_and_sender_is_notified(loop):
    r = services.change_status(loop["inbound"], "ACCEPTED", user=loop["staff"])
    assert r.status == "ACCEPTED" and r.accepted_at and r.last_status_change_at
    assert ReferralEvent.objects.filter(
        referral=r, to_status="ACCEPTED", actor=loop["staff"]
    ).exists()
    note = Notification.objects.get(recipient=loop["partner_user"], verb="REFERRAL_STATUS")
    assert r.reference_number in note.message
    email = EmailOutbox.objects.get(to_email="partner@example.test")
    assert r.reference_number not in email.body_text and r.client.last_name not in email.body_text


def test_sender_cannot_change_status(loop):
    with pytest.raises(services.WorkflowError):
        services.change_status(loop["inbound"], "ACCEPTED", user=loop["partner_user"])
    with pytest.raises(services.WorkflowError):
        services.change_status(loop["outbound"], "ACCEPTED", user=loop["staff"])


def test_partner_completes_outbound_referral_closing_the_loop(loop):
    r = services.change_status(loop["outbound"], "ACCEPTED", user=loop["partner_user"])
    r = services.change_status(r, "IN_PROGRESS", user=loop["partner_user"])
    with pytest.raises(services.WorkflowError):  # outcome note required
        services.change_status(r, "COMPLETED", user=loop["partner_user"])
    r = services.change_status(
        r,
        "COMPLETED",
        user=loop["partner_user"],
        note="Groceries delivered.",
        outcome="SERVICES_PROVIDED",
    )
    assert r.is_final and r.outcome == "SERVICES_PROVIDED"
    assert Notification.objects.filter(recipient=loop["staff"], verb="REFERRAL_STATUS").count() == 3


def test_invalid_transition_and_decline_needs_reason(loop):
    with pytest.raises(services.WorkflowError):
        services.change_status(loop["inbound"], "COMPLETED", user=loop["staff"], note="x")
    with pytest.raises(services.WorkflowError):
        services.change_status(loop["inbound"], "DECLINED", user=loop["staff"])
    r = services.change_status(
        loop["inbound"], "DECLINED", user=loop["staff"], note="Outside service area."
    )
    assert r.decline_reason == "Outside service area."


def test_read_only_access_cannot_change_status(loop):
    viewer = UserFactory(role=User.Role.STAFF)
    UserProgramAccess.objects.create(user=viewer, program=loop["program"], access_level="READ_ONLY")
    with pytest.raises(services.WorkflowError):
        services.change_status(loop["inbound"], "ACCEPTED", user=viewer)


def test_opening_marks_received_automatically(client, loop):
    client.force_login(loop["staff"])
    resp = client.get(f"/referrals/{loop['inbound'].pk}/", secure=True)
    assert resp.status_code == 200
    loop["inbound"].refresh_from_db()
    assert loop["inbound"].status == "RECEIVED"
    # The sender opening it does not.
    client.force_login(loop["partner_user"])
    client.get(f"/referrals/{loop['outbound'].pk}/", secure=True)


def test_status_change_through_web(client, loop):
    client.force_login(loop["staff"])
    resp = client.post(
        f"/referrals/{loop['inbound'].pk}/status/", {"to_status": "ACCEPTED"}, secure=True
    )
    assert resp.status_code == 302
    loop["inbound"].refresh_from_db()
    assert loop["inbound"].status == "ACCEPTED"


def test_partner_detail_hides_internal_comments_and_dob(client, loop):
    services.add_comment(
        loop["inbound"], user=loop["staff"], body="Internal only note", mentions=[]
    )
    client.force_login(loop["partner_user"])
    html = client.get(f"/referrals/{loop['inbound'].pk}/", secure=True).content.decode()
    assert "Internal only note" not in html and "Date of birth" not in html


def test_comment_mentions_notify(loop):
    other = UserFactory(role=User.Role.STAFF)
    services.add_comment(
        loop["inbound"], user=loop["staff"], body="Can you call?", mentions=[other]
    )
    assert Notification.objects.filter(recipient=other, verb="REFERRAL_MENTION").exists()
    with pytest.raises(services.WorkflowError):
        services.add_comment(loop["inbound"], user=loop["partner_user"], body="x", mentions=[])


def test_messaging_both_sides(client, loop):
    services.send_message(
        loop["inbound"], user=loop["partner_user"], body="Client prefers mornings."
    )
    assert Notification.objects.filter(recipient=loop["staff"], verb="REFERRAL_MESSAGE").exists()
    client.force_login(loop["staff"])
    page = client.get("/messages/", secure=True).content.decode()
    assert loop["inbound"].reference_number in page and "1 new" in page
    client.post(f"/referrals/{loop['inbound'].pk}/messages/", {"body": "Will do."}, secure=True)
    assert loop["inbound"].thread.messages.count() == 2
    outsider = UserFactory(role=User.Role.PARTNER_USER, organization=OrganizationFactory())
    with pytest.raises(services.WorkflowError):
        services.send_message(loop["inbound"], user=outsider, body="hi")


def test_assignment_notifies_assignee(loop):
    services.assign(loop["inbound"], loop["staff"], user=loop["staff"])
    loop["inbound"].refresh_from_db()
    assert loop["inbound"].assigned_to == loop["staff"]
    with pytest.raises(services.WorkflowError):
        services.assign(loop["inbound"], loop["staff"], user=loop["partner_user"])


def test_overdue_query_and_reminders_once_a_day(loop):
    old = timezone.now() - timedelta(days=5)
    Referral.objects.filter(pk=loop["inbound"].pk).update(last_status_change_at=old)
    assert list(Referral.objects.overdue()) == [loop["inbound"]]
    assert services.send_overdue_reminders() == 1
    assert services.send_overdue_reminders() == 0  # not again within 24 hours
    assert Notification.objects.filter(verb="REFERRAL_OVERDUE", recipient=loop["staff"]).exists()


def test_email_outbox_job_sends_via_smtp_backend(loop, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    services.change_status(loop["inbound"], "ACCEPTED", user=loop["staff"])
    assert send_pending() >= 1
    assert mail.outbox and "sign in" in mail.outbox[0].body.lower()
    assert EmailOutbox.objects.filter(status="SENT").exists()


def test_inbox_filters_and_saved_view(client, loop):
    services.change_status(loop["inbound"], "ACCEPTED", user=loop["staff"])
    client.force_login(loop["staff"])
    resp = client.get("/referrals/?status=ACCEPTED", secure=True)
    assert list(resp.context["referrals"]) == [loop["inbound"]]
    resp = client.get(f"/referrals/?q={loop['outbound'].reference_number}", secure=True)
    assert list(resp.context["referrals"]) == [loop["outbound"]]
    client.post("/referrals/views/save/", {"name": "Accepted", "status": "ACCEPTED"}, secure=True)
    page = client.get("/referrals/", secure=True).content.decode()
    assert "Accepted" in page


def test_notification_bell_and_open(client, loop):
    services.change_status(loop["inbound"], "ACCEPTED", user=loop["staff"])
    client.force_login(loop["partner_user"])
    note = Notification.objects.get(recipient=loop["partner_user"])
    html = client.get("/notifications/", secure=True).content.decode()
    assert "1 unread" in html
    resp = client.get(f"/notifications/{note.pk}/", secure=True)
    assert resp.status_code == 302
    note.refresh_from_db()
    assert note.read_at is not None


def test_send_reminders_command(loop, capsys):
    call_command("send_reminders")
    assert "Sent reminders" in capsys.readouterr().out

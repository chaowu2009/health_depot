"""Referral business logic: creating referrals, matching clients, status changes."""

import secrets
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.clients.models import Client, ClientProgram
from apps.organizations.models import Organization

from .models import Referral, ReferralEvent, ReferralLink, ReferralStatus

REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I to avoid misreading


def new_reference_number() -> str:
    year = timezone.localdate().year
    return f"CR-{year}-" + "".join(secrets.choice(REF_ALPHABET) for _ in range(6))


def health_department() -> Organization:
    org = Organization.objects.filter(org_type=Organization.OrgType.HEALTH_DEPARTMENT).first()
    if org is None:
        raise RuntimeError("Run `manage.py bootstrap` to create the health department.")
    return org


def _digits(phone: str) -> str:
    return "".join(c for c in phone or "" if c.isdigit())[-10:]


def match_client(identity: dict[str, Any]) -> tuple[Client | None, Client | None]:
    """Return (exact_match, possible_duplicate).

    Exact = same first + last name, date of birth and phone (or email). We reuse that record.
    Possible = same date of birth and (same last name or same phone): staff review it; we
    never auto-merge.
    """
    dob = identity["date_of_birth"]
    first = identity["first_name"].strip()
    last = identity["last_name"].strip()
    phone = _digits(identity.get("phone", ""))
    email = (identity.get("email") or "").strip().lower()
    same_person = Client.objects.filter(
        date_of_birth=dob,
        first_name__iexact=first,
        last_name__iexact=last,
        archived_at__isnull=True,
    )
    for candidate in same_person:
        if (phone and _digits(candidate.phone) == phone) or (
            email and candidate.email.lower() == email
        ):
            return candidate, None
    possible = (
        Client.objects.filter(date_of_birth=dob, archived_at__isnull=True)
        .filter(Q(last_name__iexact=last) | Q(phone__icontains=phone[-7:] if phone else "\u0000"))
        .first()
    )
    return None, possible


@transaction.atomic
def find_or_create_client(identity: dict[str, Any], *, program, user=None) -> Client:
    exact, possible = match_client(identity)
    if exact:
        client = exact
        changed = []
        for field in (
            "phone",
            "email",
            "zip_code",
            "preferred_language",
            "preferred_contact_method",
        ):
            value = identity.get(field)
            if value and getattr(client, field) != value:
                setattr(client, field, value)
                changed.append(field)
        if identity.get("consent_to_contact") or identity.get("consent_to_share"):
            client.consent_to_contact = bool(identity.get("consent_to_contact"))
            client.consent_to_share = bool(identity.get("consent_to_share"))
            client.consent_signed_at = timezone.now()
            client.consent_text_version = "intake-v1"
            changed += [
                "consent_to_contact",
                "consent_to_share",
                "consent_signed_at",
                "consent_text_version",
            ]
        if changed:
            client.updated_by = user
            client.save()
    else:
        client = Client.objects.create(
            first_name=identity["first_name"].strip(),
            last_name=identity["last_name"].strip(),
            date_of_birth=identity["date_of_birth"],
            phone=identity.get("phone", ""),
            email=identity.get("email", ""),
            zip_code=identity.get("zip_code", ""),
            preferred_language=identity.get("preferred_language") or "English",
            preferred_contact_method=identity.get("preferred_contact_method") or "PHONE",
            consent_to_contact=bool(identity.get("consent_to_contact")),
            consent_to_share=bool(identity.get("consent_to_share")),
            consent_signed_at=timezone.now() if identity.get("consent_to_share") else None,
            consent_text_version="intake-v1" if identity.get("consent_to_share") else "",
            possible_duplicate_of=possible,
            created_by=user,
            updated_by=user,
        )
    ClientProgram.objects.get_or_create(client=client, program=program)
    return client


def _create_referral(**kwargs) -> Referral:
    now = timezone.now()
    for _ in range(5):
        try:
            with transaction.atomic():
                return Referral.objects.create(
                    reference_number=new_reference_number(),
                    status=ReferralStatus.SUBMITTED,
                    submitted_at=now,
                    last_status_change_at=now,
                    **kwargs,
                )
        except IntegrityError:
            continue
    raise RuntimeError("Could not allocate a reference number.")


@transaction.atomic
def create_from_link(
    link: ReferralLink, *, identity: dict[str, Any], answers: list[dict], needs: list[str]
) -> Referral:
    """A community member or partner staff submitted the public form on a referral link."""
    client = find_or_create_client(identity, program=link.program)
    referral = _create_referral(
        client=client,
        program=link.program,
        direction=Referral.Direction.INBOUND,
        sending_organization=link.partner,
        receiving_organization=health_department(),
        source_link=link,
        form_template=link.form_template,
        form_version=link.form_template.version,
        answers={"items": answers},
        needs=needs,
        priority=_priority_from_answers(answers),
    )
    ReferralEvent.objects.create(
        referral=referral,
        event_type=ReferralEvent.EventType.STATUS_CHANGE,
        to_status=ReferralStatus.SUBMITTED,
        actor_organization=link.partner,
        note=f"Submitted through referral link “{link.label}”.",
    )
    ReferralLink.objects.filter(pk=link.pk).update(submission_count=F("submission_count") + 1)
    from .notify import notify_new_referral

    notify_new_referral(referral)
    return referral


def _priority_from_answers(answers: list[dict]) -> str:
    for item in answers:
        if item.get("key") == "urgency" and item.get("raw") == "today":
            return Referral.Priority.URGENT
        if item.get("key") == "safety_now" and item.get("raw") == "yes":
            return Referral.Priority.URGENT
    return Referral.Priority.NORMAL


@transaction.atomic
def create_outbound(
    *,
    user,
    client: Client,
    program,
    partner: Organization,
    priority: str,
    reason: str,
    needs: list[str],
) -> Referral:
    """CCHD staff refer a client out to a community partner."""
    ClientProgram.objects.get_or_create(client=client, program=program)
    referral = _create_referral(
        client=client,
        program=program,
        direction=Referral.Direction.OUTBOUND,
        sending_organization=health_department(),
        receiving_organization=partner,
        answers={
            "items": [
                {"key": "reason", "label": "Reason for referral", "value": reason, "raw": reason}
            ]
        },
        needs=needs,
        priority=priority,
        created_by=user,
        updated_by=user,
    )
    ReferralEvent.objects.create(
        referral=referral,
        event_type=ReferralEvent.EventType.STATUS_CHANGE,
        to_status=ReferralStatus.SUBMITTED,
        actor=user,
        actor_organization=user.organization,
        note="Referral sent to partner.",
    )
    from .notify import notify_new_referral

    notify_new_referral(referral)
    return referral


# --- Closed-loop workflow --------------------------------------------------------------------
class WorkflowError(Exception):
    pass


def user_side(user, referral) -> str | None:
    """'receiving', 'sending' or None for the user's relationship to a referral."""
    from apps.accounts.access import sees_everything

    org_id = user.organization_id
    if user.role == user.Role.PARTNER_USER:
        if org_id == referral.receiving_organization_id:
            return "receiving"
        if org_id == referral.sending_organization_id:
            return "sending"
        return None
    # Health-department users act for the health department's side.
    if referral.receiving_organization.org_type == Organization.OrgType.HEALTH_DEPARTMENT:
        return "receiving"
    if referral.sending_organization.org_type == Organization.OrgType.HEALTH_DEPARTMENT:
        return "sending"
    return "receiving" if sees_everything(user) else None


def can_change_status(user, referral) -> bool:
    """Only the receiving side moves a referral through the loop (admins always can)."""
    from apps.accounts.access import can_edit_program, sees_everything

    if not user.is_active:
        return False
    if sees_everything(user):
        return True
    if user_side(user, referral) != "receiving":
        return False
    if user.role == user.Role.PARTNER_USER:
        return True
    return can_edit_program(user, referral.program_id)


def change_status(
    referral: Referral, target: str, *, user, note: str = "", outcome: str = ""
) -> Referral:
    from .notify import notify_status
    from .workflow import ACTION_LABELS, NOTE_REQUIRED, TIMESTAMP_FIELD, can_transition

    if not can_change_status(user, referral):
        raise WorkflowError("You can't change the status of this referral.")
    if target not in ReferralStatus.values:
        raise WorkflowError("Unknown status.")
    if target in NOTE_REQUIRED and not note.strip():
        raise WorkflowError(NOTE_REQUIRED[target])
    with transaction.atomic():
        # Validate against the current database state (another user may have just acted).
        locked = Referral.objects.select_for_update().get(pk=referral.pk)
        if not can_transition(locked.status, target):
            raise WorkflowError(
                f"A {locked.get_status_display().lower()} referral can't move to "
                f"“{ReferralStatus(target).label}”."
            )
        now = timezone.now()
        previous = locked.status
        locked.status = target
        setattr(locked, TIMESTAMP_FIELD[target], now)
        locked.last_status_change_at = now
        locked.updated_by = user
        if target == ReferralStatus.DECLINED:
            locked.decline_reason = note.strip()
        if target in (ReferralStatus.COMPLETED, ReferralStatus.CLOSED_UNABLE_TO_CONTACT):
            locked.outcome = outcome or (
                "UNABLE_TO_CONTACT" if target == ReferralStatus.CLOSED_UNABLE_TO_CONTACT else ""
            )
            locked.outcome_notes = note.strip()
        locked.save()
        ReferralEvent.objects.create(
            referral=locked,
            event_type=ReferralEvent.EventType.STATUS_CHANGE,
            from_status=previous,
            to_status=target,
            actor=user,
            actor_organization=user.organization,
            note=note.strip(),
        )
    notify_status(locked, user, ACTION_LABELS[target].lower().replace("mark ", "marked "))
    ReferralEvent.objects.create(
        referral=locked,
        event_type=ReferralEvent.EventType.NOTIFIED,
        actor_organization=None,
        note=f"{locked.sending_organization} and {locked.receiving_organization} notified.",
    )
    return locked


def auto_mark_received(referral: Referral, user) -> Referral:
    """The first time the receiving side opens a new referral, record that it was received."""
    if (
        referral.status == ReferralStatus.SUBMITTED
        and can_change_status(user, referral)
        and user_side(user, referral) == "receiving"
    ):
        try:
            return change_status(
                referral,
                ReferralStatus.RECEIVED,
                user=user,
                note="Opened by the receiving organization.",
            )
        except WorkflowError:
            return referral
    return referral


def assign(referral: Referral, assignee, *, user) -> Referral:
    from apps.accounts.access import can_edit_program, sees_everything

    from .notify import notify_assigned

    if user.role == user.Role.PARTNER_USER or not (
        sees_everything(user) or can_edit_program(user, referral.program_id)
    ):
        raise WorkflowError("You can't assign this referral.")
    if assignee is not None and not (
        sees_everything(assignee) or can_edit_program(assignee, referral.program_id)
    ):
        raise WorkflowError("That person doesn't work in this referral's program.")
    referral.assigned_to = assignee
    referral.updated_by = user
    referral.save(update_fields=["assigned_to", "updated_by", "updated_at"])
    ReferralEvent.objects.create(
        referral=referral,
        event_type=ReferralEvent.EventType.ASSIGNED,
        actor=user,
        actor_organization=user.organization,
        note=f"Assigned to {assignee}." if assignee else "Unassigned.",
    )
    if assignee is not None:
        notify_assigned(referral, assignee, user)
    return referral


def add_comment(referral: Referral, *, user, body: str, mentions) -> None:
    from .models import ReferralComment
    from .notify import notify_mentions

    if user.role == user.Role.PARTNER_USER:
        raise WorkflowError("Internal comments are for health department staff.")
    if user.role == user.Role.READ_ONLY:
        raise WorkflowError("Read-only accounts can't add comments.")
    comment = ReferralComment.objects.create(referral=referral, author=user, body=body.strip())
    if mentions:
        comment.mentions.set(mentions)
        notify_mentions(referral, mentions, user)


def send_message(referral: Referral, *, user, body: str):
    from apps.messaging.models import Message, MessageReceipt, MessageThread

    from .notify import notify_message

    if user_side(user, referral) is None:
        from apps.accounts.access import sees_everything

        if not sees_everything(user):
            raise WorkflowError("You're not part of this referral.")
    if user.role == user.Role.READ_ONLY:
        raise WorkflowError("Read-only accounts can't send messages.")
    thread, created = MessageThread.objects.get_or_create(referral=referral)
    if created:
        thread.participant_organizations.set(
            [referral.sending_organization, referral.receiving_organization]
        )
    message = Message.objects.create(thread=thread, sender=user, body=body.strip())
    MessageReceipt.objects.get_or_create(message=message, user=user)
    ReferralEvent.objects.create(
        referral=referral,
        event_type=ReferralEvent.EventType.MESSAGE,
        actor=user,
        actor_organization=user.organization,
        note="Sent a secure message.",
    )
    notify_message(referral, user)
    return message


def send_overdue_reminders(now=None) -> int:
    """Remind the receiving side about overdue referrals (at most once a day each)."""
    from datetime import timedelta

    from .notify import notify_overdue

    now = now or timezone.now()
    due = (
        Referral.objects.overdue()
        .filter(
            Q(last_reminder_at__isnull=True) | Q(last_reminder_at__lt=now - timedelta(hours=24))
        )
        .select_related("program", "receiving_organization")
    )
    count = 0
    for referral in due:
        notify_overdue(referral)
        Referral.objects.filter(pk=referral.pk).update(last_reminder_at=now)
        count += 1
    return count

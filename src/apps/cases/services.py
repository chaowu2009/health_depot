"""Case management business logic."""

import secrets
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.notifications.services import notify
from apps.referrals.models import Referral

from .models import CarePlanGoal, Case, CaseDocument, CaseNote, CaseTask

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENTS = {
    b"%PDF": ("pdf", "application/pdf"),
    b"\x89PNG": ("png", "image/png"),
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"PK\x03\x04": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
}
DISCHARGE_REASONS = [
    ("GOALS_MET", "Goals met"),
    ("CLIENT_REQUEST", "Client request"),
    ("LOST_CONTACT", "Lost contact"),
    ("MOVED", "Moved out of area"),
    ("TRANSFERRED", "Transferred to another program"),
    ("OTHER", "Other"),
]
DISCHARGE_OUTCOMES = [
    ("IMPROVED", "Improved"),
    ("STABLE", "Stable"),
    ("NOT_IMPROVED", "Not improved"),
    ("UNKNOWN", "Unknown"),
]


class CaseError(Exception):
    pass


def new_case_number() -> str:
    return f"CASE-{timezone.localdate().year}-" + "".join(
        secrets.choice(ALPHABET) for _ in range(5)
    )


def create_case(*, client, program, manager, user, referral: Referral | None = None) -> Case:
    for _ in range(5):
        try:
            with transaction.atomic():
                case = Case.objects.create(
                    case_number=new_case_number(),
                    client=client,
                    program=program,
                    case_manager=manager,
                    status=Case.Status.OPEN,
                    admitted_at=timezone.now(),
                    created_by=user,
                    updated_by=user,
                )
                if referral is not None:
                    Referral.objects.filter(pk=referral.pk).update(case=case)
                return case
        except IntegrityError:
            continue
    raise CaseError("Could not allocate a case number.")


def open_from_referral(referral: Referral, *, user) -> Case:
    if referral.case_id:
        raise CaseError("This referral already has a case.")
    if referral.status not in ("ACCEPTED", "IN_PROGRESS"):
        raise CaseError("Accept the referral before opening a case.")
    case = create_case(
        client=referral.client,
        program=referral.program,
        manager=referral.assigned_to or user,
        user=user,
        referral=referral,
    )
    CaseNote.objects.create(
        case=case,
        author=user,
        note_type=CaseNote.NoteType.GENERAL,
        body=f"Case opened from referral {referral.reference_number}.",
        created_by=user,
        updated_by=user,
    )
    return case


def _ensure_open(case: Case) -> None:
    if case.status == Case.Status.DISCHARGED:
        raise CaseError("This case is discharged. Reopen it to make changes.")


def set_status(case: Case, status: str, *, user) -> Case:
    if status not in (Case.Status.OPEN, Case.Status.ACTIVE, Case.Status.ON_HOLD):
        raise CaseError("Use the discharge form to discharge a case.")
    case.status = status
    if status != Case.Status.DISCHARGED:
        case.discharged_at = None
    case.updated_by = user
    case.save()
    return case


def add_goal(case: Case, *, description: str, target_date, user) -> CarePlanGoal:
    _ensure_open(case)
    return CarePlanGoal.objects.create(case=case, description=description, target_date=target_date)


def set_goal_status(goal: CarePlanGoal, status: str) -> CarePlanGoal:
    goal.status = status
    goal.save(update_fields=["status", "updated_at"])
    return goal


def add_task(case: Case, *, title: str, assigned_to, due_date, priority: str, user) -> CaseTask:
    _ensure_open(case)
    task = CaseTask.objects.create(
        case=case,
        title=title,
        assigned_to=assigned_to,
        due_date=due_date,
        priority=priority,
        created_by=user,
        updated_by=user,
    )
    if assigned_to is not None:
        notify(
            [assigned_to],
            verb="CASE_TASK",
            message=f"New task on case {case.case_number}: {title[:80]}",
            url=reverse("case-detail", args=[case.pk]) + "#tasks",
            target=case,
            exclude=user,
        )
    return task


def toggle_task(task: CaseTask, *, user) -> CaseTask:
    task.completed_at = None if task.completed_at else timezone.now()
    task.updated_by = user
    task.save()
    return task


def add_note(case: Case, *, body: str, note_type: str, contact_date, user) -> CaseNote:
    return CaseNote.objects.create(
        case=case,
        author=user,
        body=body,
        note_type=note_type,
        contact_date=contact_date,
        created_by=user,
        updated_by=user,
    )


def validate_document(upload) -> tuple[str, str]:
    if upload.size > MAX_DOCUMENT_BYTES:
        raise ValidationError("Documents must be 10 MB or smaller.")
    head = upload.read(8)
    upload.seek(0)
    for sig, (ext, content_type) in ALLOWED_DOCUMENTS.items():
        if head.startswith(sig):
            return ext, content_type
    raise ValidationError("Upload a PDF, Word (.docx), PNG or JPEG file.")


def add_document(case: Case, *, upload, document_type: str, user) -> CaseDocument:
    ext, content_type = validate_document(upload)
    doc = CaseDocument(
        case=case,
        filename=upload.name[:255],
        content_type=content_type,
        size=upload.size,
        uploaded_by=user,
        document_type=document_type,
    )
    # Random object key: the original file name never appears in storage paths or URLs.
    doc.file.save(f"{case.pk}/{uuid.uuid4().hex}.{ext}", upload, save=False)
    doc.save()
    return doc


def discharge(case: Case, *, reason: str, outcome: str, notes: str, user) -> Case:
    _ensure_open(case)
    case.status = Case.Status.DISCHARGED
    case.discharged_at = timezone.now()
    case.discharge_reason = reason
    case.discharge_outcome = outcome
    case.discharge_notes = notes
    case.updated_by = user
    case.save()
    return case

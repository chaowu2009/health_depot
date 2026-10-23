"""Case management from admission to discharge."""

from django.conf import settings
from django.db import models

from apps.accounts.access import CaseChildQuerySet, CaseQuerySet
from apps.core.models import AuditedModel, TimeStampedModel


class Case(AuditedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ACTIVE = "ACTIVE", "Active"
        ON_HOLD = "ON_HOLD", "On hold"
        DISCHARGED = "DISCHARGED", "Discharged"

    case_number = models.CharField(max_length=20, unique=True)
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="cases")
    program = models.ForeignKey(
        "organizations.Program", on_delete=models.PROTECT, related_name="cases"
    )
    case_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_cases",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    admitted_at = models.DateTimeField()
    discharged_at = models.DateTimeField(null=True, blank=True)
    discharge_reason = models.CharField(max_length=100, blank=True)
    discharge_outcome = models.CharField(max_length=100, blank=True)
    discharge_notes = models.TextField(blank=True)

    objects = CaseQuerySet.as_manager()

    class Meta:
        ordering = ["-admitted_at"]

    def __str__(self) -> str:
        return self.case_number


class CarePlanGoal(TimeStampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        MET = "MET", "Met"
        NOT_MET = "NOT_MET", "Not met"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="goals")
    description = models.TextField()
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NOT_STARTED)

    objects = CaseChildQuerySet.as_manager()

    class Meta:
        ordering = ["target_date", "created_at"]

    def __str__(self) -> str:
        return self.description[:60]


class CaseTask(AuditedModel):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="case_tasks",
    )
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)

    objects = CaseChildQuerySet.as_manager()

    class Meta:
        ordering = ["completed_at", "due_date"]

    def __str__(self) -> str:
        return self.title


class CaseNote(AuditedModel):
    class NoteType(models.TextChoices):
        CONTACT = "CONTACT", "Contact"
        VISIT = "VISIT", "Visit"
        PHONE = "PHONE", "Phone call"
        GENERAL = "GENERAL", "General"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    note_type = models.CharField(max_length=10, choices=NoteType.choices, default=NoteType.GENERAL)
    body = models.TextField()
    contact_date = models.DateField(null=True, blank=True)

    objects = CaseChildQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_note_type_display()} note on {self.case}"


class CaseDocument(TimeStampedModel):
    class DocumentType(models.TextChoices):
        CONSENT = "CONSENT", "Consent form"
        ASSESSMENT = "ASSESSMENT", "Assessment"
        OTHER = "OTHER", "Other"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="case-documents/")  # private, via the S3 API
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    document_type = models.CharField(
        max_length=12, choices=DocumentType.choices, default=DocumentType.OTHER
    )

    objects = CaseChildQuerySet.as_manager()

    def __str__(self) -> str:
        return self.filename

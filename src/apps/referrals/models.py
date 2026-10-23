"""Referral links, referrals and the closed-loop timeline."""

import secrets

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.accounts.access import (
    InternalReferralChildQuerySet,
    ReferralChildQuerySet,
    ReferralLinkQuerySet,
    ReferralQuerySet,
)
from apps.core.models import AuditedModel, TimeStampedModel


def new_link_slug() -> str:
    return secrets.token_urlsafe(6)  # ~8 URL-safe characters, unguessable


class ReferralLink(AuditedModel):
    partner = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="referral_links"
    )
    program = models.ForeignKey(
        "organizations.Program", on_delete=models.PROTECT, related_name="referral_links"
    )
    form_template = models.ForeignKey(
        "forms_builder.FormTemplate", on_delete=models.PROTECT, related_name="referral_links"
    )
    slug = models.SlugField(max_length=32, unique=True, default=new_link_slug)
    label = models.CharField(max_length=150, help_text='e.g., "Lusby pantry — front desk"')
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    visit_count = models.PositiveIntegerField(default=0)
    submission_count = models.PositiveIntegerField(default=0)

    objects = ReferralLinkQuerySet.as_manager()

    class Meta:
        ordering = ["partner__name", "label"]

    def __str__(self) -> str:
        return f"{self.partner} — {self.label}"


class ReferralStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    RECEIVED = "RECEIVED", "Received"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"
    CLOSED_UNABLE_TO_CONTACT = "CLOSED_UNABLE_TO_CONTACT", "Closed — unable to contact"


class Referral(AuditedModel):
    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "Inbound (partner → CCHD)"
        OUTBOUND = "OUTBOUND", "Outbound (CCHD → partner)"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    reference_number = models.CharField(max_length=20, unique=True)
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="referrals")
    program = models.ForeignKey(
        "organizations.Program", on_delete=models.PROTECT, related_name="referrals"
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    sending_organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="referrals_sent"
    )
    receiving_organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="referrals_received"
    )
    source_link = models.ForeignKey(
        ReferralLink, null=True, blank=True, on_delete=models.SET_NULL, related_name="referrals"
    )
    form_template = models.ForeignKey(
        "forms_builder.FormTemplate", null=True, blank=True, on_delete=models.PROTECT
    )
    form_version = models.PositiveIntegerField(null=True, blank=True)
    answers = models.JSONField(default=dict, blank=True)
    needs = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    status = models.CharField(
        max_length=30, choices=ReferralStatus.choices, default=ReferralStatus.SUBMITTED
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_referrals",
    )
    decline_reason = models.TextField(blank=True)
    outcome = models.CharField(max_length=100, blank=True)
    outcome_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    in_progress_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_status_change_at = models.DateTimeField(null=True, blank=True)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    case = models.ForeignKey(
        "cases.Case", null=True, blank=True, on_delete=models.SET_NULL, related_name="referrals"
    )

    objects = ReferralQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "last_status_change_at"]),
            models.Index(fields=["program", "status"]),
        ]

    def __str__(self) -> str:
        return self.reference_number

    @property
    def is_final(self) -> bool:
        from .workflow import FINAL_STATUSES

        return self.status in FINAL_STATUSES

    @property
    def is_overdue(self) -> bool:
        from datetime import timedelta

        from django.utils import timezone

        if self.is_final or not self.last_status_change_at:
            return False
        days = self.program.overdue_after_days if self.program_id else 3
        return self.last_status_change_at < timezone.now() - timedelta(days=days)

    @property
    def answer_items(self) -> list[dict]:
        return (self.answers or {}).get("items", [])


class ReferralEvent(models.Model):
    """Append-only closed-loop timeline."""

    class EventType(models.TextChoices):
        STATUS_CHANGE = "STATUS_CHANGE", "Status change"
        ASSIGNED = "ASSIGNED", "Assigned"
        COMMENT = "COMMENT", "Comment"
        NOTIFIED = "NOTIFIED", "Notification sent"
        MESSAGE = "MESSAGE", "Message"

    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    from_status = models.CharField(max_length=30, choices=ReferralStatus.choices, blank=True)
    to_status = models.CharField(max_length=30, choices=ReferralStatus.choices, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    actor_organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ReferralChildQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.referral} {self.event_type} {self.created_at:%Y-%m-%d %H:%M}"


class ReferralComment(TimeStampedModel):
    """Internal CCHD-only comments with @mentions."""

    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body = models.TextField()
    mentions = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="referral_mentions"
    )

    objects = InternalReferralChildQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment on {self.referral} by {self.author}"

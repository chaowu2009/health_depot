"""Shared base models and infrastructure tables."""

import uuid

from django.conf import settings
from django.db import models


class UUIDModel(models.Model):
    """UUID primary key: no guessable sequential IDs in URLs (helps prevent IDOR)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditedModel(TimeStampedModel):
    """Adds who created/last updated a record (staff-edited records)."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class SchedulerLock(models.Model):
    """One row per scheduled job so only one worker runs it at a time."""

    job_name = models.CharField(max_length=100, primary_key=True)
    locked_until = models.DateTimeField()
    locked_by = models.CharField(max_length=200)

    def __str__(self) -> str:
        return f"{self.job_name} (until {self.locked_until:%Y-%m-%d %H:%M:%S})"


class SavedView(TimeStampedModel):
    """Saved referral-inbox filters or report definitions."""

    class ViewType(models.TextChoices):
        REFERRAL_INBOX = "REFERRAL_INBOX", "Referral inbox"
        REPORT = "REPORT", "Report"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_views"
    )
    view_type = models.CharField(max_length=20, choices=ViewType.choices)
    name = models.CharField(max_length=100)
    filters = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

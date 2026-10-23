"""Configurable intake / referral form templates."""

from django.db import models

from apps.core.models import AuditedModel


class FormTemplate(AuditedModel):
    """Field definitions are JSON, e.g.

    {"key": "housing_worry", "label": "...", "label_es": "...", "type": "single_choice",
     "required": true, "options": [...], "help_text": "", "show_if": {"field": "x", "equals": "y"},
     "maps_to": "client.phone"}
    """

    class FieldType(models.TextChoices):
        SHORT_TEXT = "short_text", "Short text"
        LONG_TEXT = "long_text", "Long text"
        SINGLE_CHOICE = "single_choice", "Single choice"
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
        DATE = "date", "Date"
        PHONE = "phone", "Phone"
        EMAIL = "email", "Email"
        YES_NO = "yes_no", "Yes / no"
        CONSENT = "consent", "Consent checkbox"

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    program = models.ForeignKey(
        "organizations.Program",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="form_templates",
        help_text="Leave blank for a template shared across programs.",
    )
    owner_organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="form_templates"
    )
    fields = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)
    is_system_template = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} (v{self.version})"

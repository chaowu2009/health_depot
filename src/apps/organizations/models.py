"""CCHD, its divisions and programs, and community partner organizations."""

from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel


class ServiceType(models.TextChoices):
    FOOD = "FOOD", "Food"
    HOUSING = "HOUSING", "Housing"
    TRANSPORTATION = "TRANSPORTATION", "Transportation"
    UTILITIES = "UTILITIES", "Utilities"
    BEHAVIORAL_HEALTH = "BEHAVIORAL_HEALTH", "Behavioral health"
    MEDICAL = "MEDICAL", "Medical"
    OTHER = "OTHER", "Other"


class Organization(TimeStampedModel):
    class OrgType(models.TextChoices):
        HEALTH_DEPARTMENT = "HEALTH_DEPARTMENT", "Health department"
        COMMUNITY_PARTNER = "COMMUNITY_PARTNER", "Community partner"

    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=20, choices=OrgType.choices)
    slug = models.SlugField(max_length=80, unique=True)
    logo = models.FileField(upload_to="logos/", blank=True)  # stored via the S3 API
    brand_color = models.CharField(
        max_length=7,
        default="#0F4C81",
        help_text="Hex color, e.g. #0F4C81",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a hex color like #0F4C81.")],
    )
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    service_types = ArrayField(
        models.CharField(max_length=30, choices=ServiceType.choices), default=list, blank=True
    )
    service_area_zips = ArrayField(models.CharField(max_length=10), default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def service_type_labels(self) -> list[str]:
        labels = dict(ServiceType.choices)
        return [labels.get(s, s) for s in self.service_types]

    @property
    def logo_url(self) -> str:
        """Short-lived presigned URL for the logo (empty if none or storage is unavailable)."""
        if not self.logo:
            return ""
        try:
            return self.logo.url
        except Exception:  # noqa: BLE001 - never break a page over a logo
            return ""


class Division(TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="divisions"
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="unique_division_code")
        ]

    def __str__(self) -> str:
        return self.name


class Program(TimeStampedModel):
    """The unit of access control."""

    division = models.ForeignKey(Division, on_delete=models.PROTECT, related_name="programs")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    overdue_after_days = models.PositiveSmallIntegerField(default=3)
    is_active = models.BooleanField(default=True)
    partners = models.ManyToManyField(
        Organization, through="PartnerProgram", related_name="partner_programs", blank=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PartnerProgram(TimeStampedModel):
    partner = models.ForeignKey(Organization, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["partner", "program"], name="unique_partner_program")
        ]

    def __str__(self) -> str:
        return f"{self.partner} ↔ {self.program}"

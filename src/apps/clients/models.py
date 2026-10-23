"""Clients (synthetic data only in the MVP)."""

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.accounts.access import ClientQuerySet
from apps.core.models import AuditedModel, TimeStampedModel


class Client(AuditedModel):
    class Sex(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        INTERSEX = "X", "Intersex"
        UNKNOWN = "U", "Unknown / prefer not to say"

    class Race(models.TextChoices):
        AMERICAN_INDIAN = "AIAN", "American Indian or Alaska Native"
        ASIAN = "ASIAN", "Asian"
        BLACK = "BLACK", "Black or African American"
        PACIFIC_ISLANDER = "NHPI", "Native Hawaiian or Other Pacific Islander"
        WHITE = "WHITE", "White"
        OTHER = "OTHER", "Other"
        DECLINED = "DECLINED", "Prefer not to say"

    class Ethnicity(models.TextChoices):
        HISPANIC = "HISPANIC", "Hispanic or Latino"
        NOT_HISPANIC = "NOT_HISPANIC", "Not Hispanic or Latino"
        DECLINED = "DECLINED", "Prefer not to say"

    class ContactMethod(models.TextChoices):
        PHONE = "PHONE", "Phone call"
        TEXT = "TEXT", "Text message"
        EMAIL = "EMAIL", "Email"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    preferred_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=1, choices=Sex.choices, default=Sex.UNKNOWN)
    gender_identity = models.CharField(max_length=100, blank=True)
    race = ArrayField(
        models.CharField(max_length=10, choices=Race.choices), default=list, blank=True
    )
    ethnicity = models.CharField(max_length=15, choices=Ethnicity.choices, blank=True)
    preferred_language = models.CharField(max_length=50, default="English")
    needs_interpreter = models.BooleanField(default=False)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    preferred_contact_method = models.CharField(
        max_length=10, choices=ContactMethod.choices, default=ContactMethod.PHONE
    )
    consent_to_share = models.BooleanField(default=False)
    consent_to_contact = models.BooleanField(default=False)
    consent_signed_at = models.DateTimeField(null=True, blank=True)
    consent_text_version = models.CharField(max_length=20, blank=True)
    external_mrn = models.CharField("external MRN", max_length=50, blank=True)
    possible_duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="possible_duplicates"
    )
    programs = models.ManyToManyField(
        "organizations.Program", through="ClientProgram", related_name="clients", blank=True
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = ClientQuerySet.as_manager()

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["last_name", "first_name", "date_of_birth"])]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ClientProgram(TimeStampedModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    program = models.ForeignKey("organizations.Program", on_delete=models.PROTECT)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client", "program"], name="unique_client_program")
        ]

    def __str__(self) -> str:
        return f"{self.client} in {self.program}"

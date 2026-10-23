"""Users, roles and program-level access."""

from typing import ClassVar

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra) -> "User":
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.SYSTEM_ADMIN)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Email is the login. Role is a fixed list (can become a table later if needed)."""

    class Role(models.TextChoices):
        SYSTEM_ADMIN = "SYSTEM_ADMIN", "System administrator"
        PROGRAM_MANAGER = "PROGRAM_MANAGER", "Program manager"
        STAFF = "STAFF", "Staff"
        READ_ONLY = "READ_ONLY", "Read-only (leadership)"
        PARTNER_USER = "PARTNER_USER", "Community partner user"

    username = None  # type: ignore[assignment]
    email = models.EmailField("email address", unique=True)
    phone = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=100, blank=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()  # type: ignore[assignment,misc]

    class Meta:
        ordering = ["last_name", "first_name", "email"]

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    @property
    def is_system_admin(self) -> bool:
        return self.role == self.Role.SYSTEM_ADMIN

    @property
    def is_partner_user(self) -> bool:
        return self.role == self.Role.PARTNER_USER


class UserProgramAccess(TimeStampedModel):
    """Which programs a CCHD user can see, and whether they can edit there."""

    class AccessLevel(models.TextChoices):
        EDIT = "EDIT", "Edit"
        READ_ONLY = "READ_ONLY", "Read-only"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="program_access")
    program = models.ForeignKey(
        "organizations.Program", on_delete=models.CASCADE, related_name="user_access"
    )
    access_level = models.CharField(
        max_length=10, choices=AccessLevel.choices, default=AccessLevel.EDIT
    )

    class Meta:
        verbose_name_plural = "user program access"
        constraints = [
            models.UniqueConstraint(fields=["user", "program"], name="unique_user_program")
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.program} ({self.access_level})"

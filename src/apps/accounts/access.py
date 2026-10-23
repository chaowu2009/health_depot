"""Program-scoped access rules — the single place that decides who can see and edit what.

Every view and HTMX endpoint must get its records through ``Model.objects.for_user(user)``
(read) or ``Model.objects.editable_by(user)`` (write). Never filter only in templates.

Rules
- SYSTEM_ADMIN: everything.
- PROGRAM_MANAGER / STAFF: records in programs listed in their UserProgramAccess; can edit
  where access_level is EDIT.
- READ_ONLY (leadership): read records in their programs; never edit.
- PARTNER_USER: only referrals sent to or from their own organization, and the clients on
  those referrals. Never cases or case notes.
- Inactive or anonymous users: nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models
from django.db.models import Q

if TYPE_CHECKING:
    from .models import User


def is_active_user(user: Any) -> bool:
    return bool(user and user.is_authenticated and user.is_active)


def sees_everything(user: User) -> bool:
    return bool(user.is_superuser or user.role == user.Role.SYSTEM_ADMIN)


def program_ids(user: User, *, edit: bool = False) -> list[Any]:
    """Program IDs the user can read (or edit, when ``edit=True``)."""
    from .models import User as UserModel
    from .models import UserProgramAccess

    if user.role == UserModel.Role.PARTNER_USER:
        return []
    if edit and user.role == UserModel.Role.READ_ONLY:
        return []
    qs = UserProgramAccess.objects.filter(user=user, program__is_active=True)
    if edit:
        qs = qs.filter(access_level=UserProgramAccess.AccessLevel.EDIT)
    return list(qs.values_list("program_id", flat=True))


def can_edit_program(user: Any, program_id: Any) -> bool:
    if not is_active_user(user):
        return False
    if sees_everything(user):
        return True
    return program_id in program_ids(user, edit=True)


class ScopedQuerySet(models.QuerySet):
    """Base queryset. Subclasses implement the three scope filters."""

    def for_user(self, user: Any) -> ScopedQuerySet:
        return self._scope(user, edit=False)

    def editable_by(self, user: Any) -> ScopedQuerySet:
        return self._scope(user, edit=True)

    def _scope(self, user: Any, *, edit: bool) -> ScopedQuerySet:
        if not is_active_user(user):
            return self.none()
        if sees_everything(user):
            return self.all()
        if user.role == user.Role.PARTNER_USER:
            if user.organization_id is None:
                return self.none()
            return self._partner_filter(user, edit=edit)
        return self._program_filter(program_ids(user, edit=edit))

    # --- implemented by subclasses ---
    def _program_filter(self, ids: list[Any]) -> ScopedQuerySet:
        raise NotImplementedError

    def _partner_filter(self, user: User, *, edit: bool) -> ScopedQuerySet:
        return self.none()


class ReferralQuerySet(ScopedQuerySet):
    def open(self):
        from apps.referrals.workflow import FINAL_STATUSES

        return self.exclude(status__in=FINAL_STATUSES)

    def overdue(self):
        """Open referrals with no status change within the program's overdue window."""
        from datetime import timedelta

        from django.db.models import DurationField, ExpressionWrapper, F
        from django.utils import timezone

        window = ExpressionWrapper(
            F("program__overdue_after_days") * timedelta(days=1), output_field=DurationField()
        )
        return (
            self.open()
            .annotate(_window=window)
            .filter(last_status_change_at__lt=timezone.now() - F("_window"))
        )

    def _program_filter(self, ids):
        return self.filter(program_id__in=ids)

    def _partner_filter(self, user, *, edit):
        org = user.organization_id
        return self.filter(Q(sending_organization_id=org) | Q(receiving_organization_id=org))


class ClientQuerySet(ScopedQuerySet):
    def _program_filter(self, ids):
        return self.filter(Q(programs__in=ids) | Q(referrals__program_id__in=ids)).distinct()

    def _partner_filter(self, user, *, edit):
        if edit:
            return self.none()  # partners never edit client records directly
        org = user.organization_id
        return self.filter(
            Q(referrals__sending_organization_id=org) | Q(referrals__receiving_organization_id=org)
        ).distinct()


class CaseQuerySet(ScopedQuerySet):
    """Cases and case notes are CCHD-only; partners never see them."""

    def _program_filter(self, ids):
        return self.filter(program_id__in=ids)


class CaseChildQuerySet(ScopedQuerySet):
    """Goals, tasks, notes and documents inherit their case's program."""

    def _program_filter(self, ids):
        return self.filter(case__program_id__in=ids)


class ReferralLinkQuerySet(ScopedQuerySet):
    def _program_filter(self, ids):
        return self.filter(program_id__in=ids)

    def _partner_filter(self, user, *, edit):
        return self.none() if edit else self.filter(partner_id=user.organization_id)


class ReferralChildQuerySet(ScopedQuerySet):
    """Events, comments and threads inherit their referral's scope."""

    def _program_filter(self, ids):
        return self.filter(referral__program_id__in=ids)

    def _partner_filter(self, user, *, edit):
        org = user.organization_id
        return self.filter(
            Q(referral__sending_organization_id=org) | Q(referral__receiving_organization_id=org)
        )


class InternalReferralChildQuerySet(ReferralChildQuerySet):
    """Internal CCHD comments: never visible to partners."""

    def _partner_filter(self, user, *, edit):
        return self.none()


class MessageQuerySet(ScopedQuerySet):
    def _program_filter(self, ids):
        return self.filter(thread__referral__program_id__in=ids)

    def _partner_filter(self, user, *, edit):
        org = user.organization_id
        return self.filter(
            Q(thread__referral__sending_organization_id=org)
            | Q(thread__referral__receiving_organization_id=org)
        )


# --- Role helpers used by views and templates ----------------------------------------------
def is_cchd_staff(user: Any) -> bool:
    """Health-department side (any role except partner)."""
    return is_active_user(user) and user.role != user.Role.PARTNER_USER


def can_manage_partners(user: Any) -> bool:
    """Create/edit partner organizations, referral links and form templates."""
    return is_active_user(user) and (
        sees_everything(user) or user.role == user.Role.PROGRAM_MANAGER
    )


def can_edit_anything(user: Any) -> bool:
    return is_active_user(user) and user.role not in (user.Role.READ_ONLY,)

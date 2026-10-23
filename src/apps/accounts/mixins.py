"""View mixins that enforce program scoping and role checks on the server."""

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet

from apps.audit.services import log_read

from .access import sees_everything


class ScopedQuerysetMixin(LoginRequiredMixin):
    """Use with Django generic views. Records come only from the user's scope.

    - ``scope_edit = True`` restricts to records the user may change (else 404).
    - ``audit_read = True`` writes a READ entry to the audit log for detail views.
    """

    model: type[Model]
    scope_edit = False
    audit_read = False

    def get_queryset(self) -> QuerySet[Any]:
        manager = self.model._default_manager  # type: ignore[attr-defined]
        if self.scope_edit:
            return manager.editable_by(self.request.user)  # type: ignore[attr-defined]
        return manager.for_user(self.request.user)  # type: ignore[attr-defined]

    def get_object(self, queryset: QuerySet[Any] | None = None) -> Any:
        obj = super().get_object(queryset)  # type: ignore[misc]
        if self.audit_read:
            log_read(self.request, obj)  # type: ignore[attr-defined]
        return obj


class RoleRequiredMixin(LoginRequiredMixin):
    """Allow only the listed roles (system administrators always allowed)."""

    allowed_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not (sees_everything(user) or user.role in self.allowed_roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class SystemAdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ()


class StaffRequiredMixin(LoginRequiredMixin):
    """Health-department users only (no partner users)."""

    def dispatch(self, request, *args, **kwargs):
        from .access import is_cchd_staff

        if request.user.is_authenticated and not is_cchd_staff(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ManagePartnersRequiredMixin(LoginRequiredMixin):
    """System administrators and program managers."""

    def dispatch(self, request, *args, **kwargs):
        from .access import can_manage_partners

        if request.user.is_authenticated and not can_manage_partners(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

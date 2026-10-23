"""Automatic audit entries for client-data changes, logins and permission changes."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from allauth.mfa.signals import authenticator_added, authenticator_removed
from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import AuditLog
from .services import log_event

_suppressed: ContextVar[bool] = ContextVar("audit_suppressed", default=False)


@contextmanager
def suppress_audit():
    """Used only by the demo-data seeder, which writes thousands of synthetic records."""
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


# Models holding client-related data: every create/update/delete is audited.
AUDITED_MODELS = [
    "clients.Client",
    "clients.ClientProgram",
    "referrals.Referral",
    "referrals.ReferralComment",
    "messaging.Message",
    "cases.Case",
    "cases.CarePlanGoal",
    "cases.CaseTask",
    "cases.CaseNote",
    "cases.CaseDocument",
]
IGNORED_FIELDS = {"updated_at", "created_at", "updated_by", "created_by"}


def _changed_fields(sender: Any, instance: Any) -> list[str]:
    old = sender._base_manager.filter(pk=instance.pk).first()
    if old is None:
        return []
    changed = []
    for field in sender._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        if getattr(old, field.attname) != getattr(instance, field.attname):
            changed.append(field.name)
    return changed


def _before_save(sender, instance, raw=False, **kwargs):
    if raw or instance._state.adding or _suppressed.get():
        instance._audit_changed_fields = None
        return
    instance._audit_changed_fields = _changed_fields(sender, instance)


def _after_save(sender, instance, created, raw=False, **kwargs):
    if raw or _suppressed.get():
        return
    if created:
        log_event(AuditLog.Action.CREATE, entity=instance)
        return
    changed = getattr(instance, "_audit_changed_fields", None)
    if changed:
        log_event(AuditLog.Action.UPDATE, entity=instance, changes={"fields": changed})


def _after_delete(sender, instance, **kwargs):
    if _suppressed.get():
        return
    log_event(AuditLog.Action.DELETE, entity=instance)


def connect_model_signals() -> None:
    for label in AUDITED_MODELS:
        model = apps.get_model(label)
        uid = f"audit-{label}"
        pre_save.connect(_before_save, sender=model, dispatch_uid=f"{uid}-pre")
        post_save.connect(_after_save, sender=model, dispatch_uid=f"{uid}-post")
        post_delete.connect(_after_delete, sender=model, dispatch_uid=f"{uid}-del")


# --- Authentication ------------------------------------------------------------------------
@receiver(user_logged_in, dispatch_uid="audit-login")
def _logged_in(sender, request, user, **kwargs):
    log_event(AuditLog.Action.LOGIN, entity=user, actor=user, request=request)


@receiver(user_logged_out, dispatch_uid="audit-logout")
def _logged_out(sender, request, user, **kwargs):
    if user is not None:
        log_event("LOGOUT", entity=user, actor=user, request=request)


@receiver(user_login_failed, dispatch_uid="audit-login-failed")
def _login_failed(sender, credentials, request=None, **kwargs):
    # Never record the password. The attempted email is staff identity, not client PHI.
    attempted = str(credentials.get("email") or credentials.get("username") or "")[:254]
    log_event(
        AuditLog.Action.LOGIN_FAILED,
        entity_type="User",
        changes={"attempted_email": attempted},
        request=request,
    )


@receiver(authenticator_added, dispatch_uid="audit-mfa-added")
def _mfa_added(sender, request, user, authenticator, **kwargs):
    log_event(
        AuditLog.Action.MFA_ENROLLED,
        entity=user,
        actor=user,
        request=request,
        changes={"type": authenticator.type},
    )


@receiver(authenticator_removed, dispatch_uid="audit-mfa-removed")
def _mfa_removed(sender, request, user, authenticator, **kwargs):
    log_event(
        AuditLog.Action.PERMISSION_CHANGE,
        entity=user,
        request=request,
        changes={"mfa_removed": authenticator.type},
    )


# --- Permission changes --------------------------------------------------------------------
def _user_before_save(sender, instance, raw=False, **kwargs):
    if raw or instance._state.adding:
        instance._audit_perm_changes = None
        return
    changed = [
        f
        for f in _changed_fields(sender, instance)
        if f in {"role", "is_active", "is_superuser", "is_staff", "organization"}
    ]
    instance._audit_perm_changes = changed


def _user_after_save(sender, instance, created, raw=False, **kwargs):
    if raw or _suppressed.get():
        return
    if created:
        log_event(AuditLog.Action.CREATE, entity=instance, changes={"role": instance.role})
    elif getattr(instance, "_audit_perm_changes", None):
        log_event(
            AuditLog.Action.PERMISSION_CHANGE,
            entity=instance,
            changes={"fields": instance._audit_perm_changes, "role": instance.role},
        )


def _access_changed(sender, instance, **kwargs):
    if _suppressed.get():
        return
    log_event(
        AuditLog.Action.PERMISSION_CHANGE,
        entity=instance.user,
        changes={
            "program_access": str(instance.program_id),
            "access_level": instance.access_level,
            "removed": kwargs.get("signal") is post_delete,
        },
    )


def connect_permission_signals() -> None:
    user_model = apps.get_model("accounts.User")
    access_model = apps.get_model("accounts.UserProgramAccess")
    pre_save.connect(_user_before_save, sender=user_model, dispatch_uid="audit-user-pre")
    post_save.connect(_user_after_save, sender=user_model, dispatch_uid="audit-user-post")
    post_save.connect(_access_changed, sender=access_model, dispatch_uid="audit-access-save")
    post_delete.connect(_access_changed, sender=access_model, dispatch_uid="audit-access-del")

"""In-app administration: users, roles, program access, MFA reset and the audit log.

System administrators only.
"""

from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.audit.models import AuditLog
from apps.audit.services import log_event

from .forms import AuditFilterForm, ProgramAccessFormSet, UserForm
from .mixins import SystemAdminRequiredMixin
from .models import User


class UserListView(SystemAdminRequiredMixin, ListView):
    template_name = "accounts/manage/user_list.html"
    paginate_by = 25
    context_object_name = "users"

    def get_queryset(self):
        qs = User.objects.select_related("organization").order_by("last_name", "email")
        q = self.request.GET.get("q", "").strip()
        role = self.request.GET.get("role", "")
        if q:
            qs = qs.filter(
                Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )
        if role in User.Role.values:
            qs = qs.filter(role=role)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        mfa_users = set(
            Authenticator.objects.filter(type=Authenticator.Type.TOTP).values_list(
                "user_id", flat=True
            )
        )
        for u in ctx["users"]:
            u.has_mfa = u.pk in mfa_users
        ctx.update(
            active="manage",
            roles=User.Role.choices,
            q=self.request.GET.get("q", ""),
            role=self.request.GET.get("role", ""),
        )
        return ctx


class UserEditView(SystemAdminRequiredMixin, View):
    template_name = "accounts/manage/user_form.html"

    def _get_user(self, pk):
        return get_object_or_404(User, pk=pk) if pk else User()

    def get(self, request, pk=None):
        user = self._get_user(pk)
        return self._render(
            request,
            user,
            UserForm(instance=user, acting_user=request.user),
            ProgramAccessFormSet(instance=user),
        )

    def post(self, request, pk=None):
        user = self._get_user(pk)
        form = UserForm(request.POST, instance=user, acting_user=request.user)
        formset = ProgramAccessFormSet(request.POST, instance=user)
        if form.is_valid() and formset.is_valid():
            role = form.cleaned_data["role"]
            if role == User.Role.PARTNER_USER and any(
                f.cleaned_data and not f.cleaned_data.get("DELETE") for f in formset.forms
            ):
                form.add_error(
                    None,
                    "Partner users get access through their organization, "
                    "not through program assignments. Remove the programs.",
                )
                return self._render(request, user, form, formset)
            with transaction.atomic():
                saved = form.save()
                formset.instance = saved
                formset.save()
            messages.success(request, f"Saved {saved.email}.")
            return redirect("manage-user-list")
        return self._render(request, user, form, formset)

    def _render(self, request, user, form, formset):
        has_mfa = (
            bool(user.pk)
            and Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "formset": formset,
                "edited_user": user,
                "has_mfa": has_mfa,
                "active": "manage",
            },
        )


class ResetMFAView(SystemAdminRequiredMixin, View):
    """Remove a user's authenticator so they must enroll again (e.g., lost phone)."""

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        deleted, _ = Authenticator.objects.filter(user=user).delete()
        log_event(
            AuditLog.Action.PERMISSION_CHANGE,
            entity=user,
            request=request,
            changes={"mfa_reset": True},
        )
        messages.success(
            request,
            f"Two-factor authentication reset for {user.email}. "
            "They will set it up again at their next sign-in.",
        )
        return redirect("manage-user-edit", pk=pk)


class AuditLogListView(SystemAdminRequiredMixin, ListView):
    template_name = "accounts/manage/audit_list.html"
    paginate_by = 50
    context_object_name = "entries"

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor", "program")
        self.filter_form = AuditFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            d = self.filter_form.cleaned_data
            if d["action"]:
                qs = qs.filter(action=d["action"])
            if d["entity_type"]:
                qs = qs.filter(entity_type__iexact=d["entity_type"].strip())
            if d["actor"]:
                qs = qs.filter(actor__email__icontains=d["actor"].strip())
            if d["date_from"]:
                qs = qs.filter(occurred_at__date__gte=d["date_from"])
            if d["date_to"]:
                qs = qs.filter(occurred_at__date__lte=d["date_to"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(active="audit", filter_form=self.filter_form, querystring=params.urlencode())
        return ctx


class ToolsView(SystemAdminRequiredMixin, View):
    """Operational tools: run overdue reminders now; reset demo data (demo mode only)."""

    template_name = "accounts/manage/tools.html"

    def get(self, request):
        from django.conf import settings

        return render(
            request, self.template_name, {"active": "tools", "demo_mode": settings.DEMO_MODE}
        )

    def post(self, request):
        from django.conf import settings
        from django.core.management import call_command

        from apps.referrals.services import send_overdue_reminders

        action = request.POST.get("action")
        if action == "reminders":
            count = send_overdue_reminders()
            messages.success(request, f"Sent reminders for {count} overdue referral(s).")
        elif action == "reset-demo" and settings.DEMO_MODE:
            log_event(
                AuditLog.Action.DELETE,
                entity_type="DemoData",
                request=request,
                changes={"reset": True},
            )
            call_command("seed_demo", reset=True, verbosity=0)
            messages.success(request, "Demo data was reset. Demo accounts were recreated.")
            if request.user.email.endswith("@demo.healthdepot.local"):
                return redirect("account_login")  # your demo account was recreated
        return redirect("manage-tools")

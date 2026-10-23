from typing import Any

from allauth.account.forms import LoginForm as LoginFormBase
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.core.forms import StyledFormMixin, style_form
from apps.organizations.models import Organization

from .models import User, UserProgramAccess


class UserForm(StyledFormMixin, forms.ModelForm):
    new_password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        required=False,
        help_text="At least 12 characters. Leave blank to keep the current password.",
    )
    new_password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "title",
            "phone",
            "organization",
            "role",
            "is_active",
        ]
        help_texts = {
            "role": "Partner users only see referrals involving their organization.",
            "is_active": "Inactive users cannot sign in.",
        }

    def __init__(self, *args, acting_user: User | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        org_field = self.fields["organization"]
        assert isinstance(org_field, forms.ModelChoiceField)
        org_field.queryset = Organization.objects.filter(is_active=True)
        self.fields["organization"].required = True
        if self.instance.pk is None:
            self.fields["new_password1"].required = True
            self.fields["new_password2"].required = True
            self.fields["new_password1"].help_text = "At least 12 characters."

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        role, org = data.get("role"), data.get("organization")
        if role and org:
            is_partner_org = org.org_type == Organization.OrgType.COMMUNITY_PARTNER
            if role == User.Role.PARTNER_USER and not is_partner_org:
                self.add_error(
                    "organization", "Partner users must belong to a partner organization."
                )
            if role != User.Role.PARTNER_USER and is_partner_org:
                self.add_error("role", "Staff at partner organizations must have the Partner role.")
        if self.acting_user and self.instance.pk == self.acting_user.pk:
            if role != User.Role.SYSTEM_ADMIN and not self.acting_user.is_superuser:
                self.add_error("role", "You cannot remove your own administrator role.")
            if data.get("is_active") is False:
                self.add_error("is_active", "You cannot deactivate your own account.")
        p1, p2 = data.get("new_password1"), data.get("new_password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("new_password2", "The two passwords do not match.")
            else:
                try:
                    validate_password(str(p1), self.instance)
                except ValidationError as exc:
                    self.add_error("new_password1", exc)
        return data

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        if self.cleaned_data.get("new_password1"):
            user.set_password(self.cleaned_data["new_password1"])
        if commit:
            user.save()
        return user


class ProgramAccessForm(forms.ModelForm):
    class Meta:
        model = UserProgramAccess
        fields = ["program", "access_level"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


ProgramAccessFormSet = inlineformset_factory(
    User, UserProgramAccess, form=ProgramAccessForm, extra=2, can_delete=True
)


class AuditFilterForm(StyledFormMixin, forms.Form):
    from apps.audit.models import AuditLog

    action = forms.ChoiceField(
        required=False, choices=[("", "All actions"), *AuditLog.Action.choices]
    )
    entity_type = forms.CharField(required=False, label="Record type")
    actor = forms.CharField(required=False, label="User email contains")
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))


class LoginForm(LoginFormBase):
    """allauth login form without the 'Forgot your password?' email link —
    administrators reset passwords for staff and partner accounts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].help_text = ""

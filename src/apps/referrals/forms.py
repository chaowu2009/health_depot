from typing import Any

from django import forms

from apps.clients.models import Client
from apps.core.forms import StyledFormMixin
from apps.forms_builder.dynamic import PHONE_VALIDATOR
from apps.forms_builder.schema import NEED_TAGS
from apps.organizations.models import Organization, Program

from .models import Referral


class OutboundReferralForm(StyledFormMixin, forms.Form):
    client = forms.ModelChoiceField(
        queryset=Client.objects.none(),
        required=False,
        label="Existing client",
        help_text="Or leave blank and enter a new client below.",
    )
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    phone = forms.CharField(max_length=20, required=False, validators=[PHONE_VALIDATOR])
    program = forms.ModelChoiceField(queryset=Program.objects.none())
    partner = forms.ModelChoiceField(
        queryset=Organization.objects.filter(
            org_type=Organization.OrgType.COMMUNITY_PARTNER, is_active=True
        ),
        label="Refer to partner",
    )
    priority = forms.ChoiceField(choices=Referral.Priority.choices, initial="NORMAL")
    needs = forms.MultipleChoiceField(
        choices=list(NEED_TAGS.items()), required=False, widget=forms.CheckboxSelectMultiple
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=2000,
        label="Reason for referral",
        help_text="Share only what the partner needs to help.",
    )

    def __init__(self, *args, clients=None, programs=None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        client_field = self.fields["client"]
        program_field = self.fields["program"]
        assert isinstance(client_field, forms.ModelChoiceField)
        assert isinstance(program_field, forms.ModelChoiceField)
        client_field.queryset = clients if clients is not None else Client.objects.none()
        program_field.queryset = programs if programs is not None else Program.objects.none()

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if not data.get("client"):
            for name in ("first_name", "last_name", "date_of_birth"):
                if not data.get(name):
                    self.add_error(name, "Required for a new client.")
        return data


class InboxFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"placeholder": "Reference or client name"}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Any status"),
            ("OPEN", "All open"),
            *Referral._meta.get_field("status").choices,
        ],
    )
    direction = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Incoming & outgoing"),
            ("incoming", "Incoming to us"),
            ("outgoing", "Sent by us"),
        ],
    )
    program = forms.ModelChoiceField(
        queryset=Program.objects.filter(is_active=True), required=False, empty_label="Any program"
    )
    partner = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type=Organization.OrgType.COMMUNITY_PARTNER),
        required=False,
        empty_label="Any partner",
    )
    priority = forms.ChoiceField(
        required=False, choices=[("", "Any priority"), *Referral.Priority.choices]
    )
    date_from = forms.DateField(
        required=False, label="Submitted from", widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        required=False, label="Submitted to", widget=forms.DateInput(attrs={"type": "date"})
    )
    overdue = forms.BooleanField(required=False, label="Overdue only")
    mine = forms.BooleanField(required=False, label="Assigned to me")


class StatusChangeForm(forms.Form):
    to_status = forms.ChoiceField(choices=Referral._meta.get_field("status").choices)
    note = forms.CharField(required=False, max_length=2000, widget=forms.Textarea)
    outcome = forms.CharField(required=False, max_length=100)


class CommentForm(StyledFormMixin, forms.Form):
    body = forms.CharField(
        max_length=4000, label="Internal comment", widget=forms.Textarea(attrs={"rows": 2})
    )
    mentions = forms.ModelMultipleChoiceField(
        queryset=None, required=False, label="Mention (they'll be notified)"
    )

    def __init__(self, *args, mention_users=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mentions"].queryset = mention_users  # type: ignore[attr-defined]


class MessageForm(StyledFormMixin, forms.Form):
    body = forms.CharField(
        max_length=4000,
        label="Message",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Visible to both organizations on this referral.",
    )

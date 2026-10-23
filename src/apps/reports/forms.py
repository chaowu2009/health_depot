from datetime import timedelta

from django import forms
from django.utils import timezone

from apps.core.forms import StyledFormMixin
from apps.organizations.models import Organization, Program
from apps.referrals.models import Referral

from .services import DEFAULT_FIELDS, REPORT_FIELDS


def default_start():
    return timezone.localdate() - timedelta(days=182)


class DashboardFilterForm(StyledFormMixin, forms.Form):
    start = forms.DateField(
        required=False, label="From", widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        required=False, label="To", widget=forms.DateInput(attrs={"type": "date"})
    )
    program = forms.ModelChoiceField(
        queryset=Program.objects.filter(is_active=True), required=False, empty_label="All programs"
    )
    partner = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type=Organization.OrgType.COMMUNITY_PARTNER),
        required=False,
        empty_label="All partners",
    )

    def range(self):
        d = self.cleaned_data if self.is_valid() else {}
        start = d.get("start") or default_start()
        end = d.get("end") or timezone.localdate()
        if start > end:
            start, end = end, start
        return start, end, d.get("program"), d.get("partner")


class ReportForm(DashboardFilterForm):
    status = forms.ChoiceField(
        required=False, choices=[("", "Any status"), *Referral._meta.get_field("status").choices]
    )
    columns = forms.MultipleChoiceField(
        choices=[(k, v[0]) for k, v in REPORT_FIELDS.items()],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        initial=DEFAULT_FIELDS,
        label="Columns",
    )

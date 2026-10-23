from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import StyledFormMixin
from apps.forms_builder.models import FormTemplate
from apps.referrals.models import ReferralLink

from .models import Organization, Program, ServiceType

MAX_LOGO_BYTES = 1024 * 1024
LOGO_SIGNATURES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}


def validate_logo(upload) -> None:
    """PNG or JPEG only (no SVG — it can carry scripts), max 1 MB, checked by content."""
    if upload.size > MAX_LOGO_BYTES:
        raise ValidationError("Logo must be 1 MB or smaller.")
    head = upload.read(8)
    upload.seek(0)
    if not any(head.startswith(sig) for sig in LOGO_SIGNATURES):
        raise ValidationError("Logo must be a PNG or JPEG image.")


class PartnerForm(StyledFormMixin, forms.ModelForm):
    service_types = forms.MultipleChoiceField(
        choices=ServiceType.choices, required=False, widget=forms.CheckboxSelectMultiple
    )
    service_area_zips = forms.CharField(
        required=False,
        label="Service area ZIP codes",
        help_text="Separate with commas, e.g. 20678, 20657",
    )
    logo = forms.FileField(
        required=False, validators=[validate_logo], help_text="PNG or JPEG, up to 1 MB."
    )
    programs = forms.ModelMultipleChoiceField(
        queryset=Program.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Programs this partner works with.",
    )

    class Meta:
        model = Organization
        fields = [
            "name",
            "contact_name",
            "contact_email",
            "contact_phone",
            "address",
            "website",
            "brand_color",
            "service_types",
            "service_area_zips",
            "logo",
            "is_active",
        ]
        widgets = {"brand_color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["service_area_zips"] = ", ".join(self.instance.service_area_zips)
            self.initial["programs"] = list(
                self.instance.partner_programs.values_list("pk", flat=True)
            )

    def clean_service_area_zips(self) -> list[str]:
        raw = self.cleaned_data.get("service_area_zips") or ""
        zips = [z.strip() for z in raw.split(",") if z.strip()]
        for z in zips:
            if not (z.isdigit() and len(z) == 5):
                raise ValidationError(f"'{z}' is not a 5-digit ZIP code.")
        return zips

    def clean_brand_color(self) -> str:
        color = self.cleaned_data["brand_color"]
        if not (
            len(color) == 7
            and color.startswith("#")
            and all(c in "0123456789abcdefABCDEF" for c in color[1:])
        ):
            raise ValidationError("Use a hex color like #0F4C81.")
        return color


class ReferralLinkForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ReferralLink
        fields = ["label", "program", "form_template", "expires_at"]
        widgets = {"expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}
        labels = {"form_template": "Form", "expires_at": "Expires (optional)"}

    def __init__(self, *args, programs=None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        program_field = self.fields["program"]
        template_field = self.fields["form_template"]
        assert isinstance(program_field, forms.ModelChoiceField)
        assert isinstance(template_field, forms.ModelChoiceField)
        program_field.queryset = (
            programs if programs is not None else Program.objects.filter(is_active=True)
        )
        template_field.queryset = FormTemplate.objects.filter(is_published=True)

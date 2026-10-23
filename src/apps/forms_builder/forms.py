from typing import Any

from django import forms

from apps.core.forms import StyledFormMixin
from apps.organizations.models import Program

from .models import FormTemplate
from .schema import CHOICE_TYPES, FIELD_TYPES, NEED_TAGS


class TemplateMetaForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FormTemplate
        fields = ["name", "description", "program", "is_published"]
        labels = {"is_published": "Published (can be used on referral links)"}
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        program = self.fields["program"]
        assert isinstance(program, forms.ModelChoiceField)
        program.queryset = Program.objects.filter(is_active=True)
        program.empty_label = "All programs (shared)"


class NewTemplateForm(TemplateMetaForm):
    start_from = forms.ModelChoiceField(
        queryset=FormTemplate.objects.filter(is_system_template=True),
        required=False,
        empty_label="Blank form",
        help_text="Copy the questions from a prebuilt template.",
    )

    class Meta(TemplateMetaForm.Meta):
        fields = ["name", "description", "program"]


class FieldForm(StyledFormMixin, forms.Form):
    type = forms.ChoiceField(choices=list(FIELD_TYPES.items()), label="Question type")
    label = forms.CharField(max_length=300, label="Question (English)")
    label_es = forms.CharField(max_length=300, required=False, label="Question (Spanish)")
    help_text = forms.CharField(max_length=300, required=False, label="Help text (English)")
    help_es = forms.CharField(max_length=300, required=False, label="Help text (Spanish)")
    required = forms.BooleanField(required=False)
    options_text = forms.CharField(
        required=False,
        label="Options",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="One per line: English | Spanish. Only for choice questions.",
    )
    show_if_field = forms.ChoiceField(required=False, label="Only show if question…")
    show_if_equals = forms.CharField(required=False, max_length=100, label="…has the answer")
    need_tag = forms.ChoiceField(
        required=False,
        label="Counts as a need",
        choices=[("", "— not a need —"), *NEED_TAGS.items()],
        help_text="Flags the referral with this need for reporting.",
    )
    need_values = forms.CharField(
        required=False,
        max_length=200,
        label="…when the answer is",
        help_text="Answer value(s) separated by commas, e.g. yes",
    )

    def __init__(self, *args, other_fields: list[dict[str, Any]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "— always show —")]
        choices += [(f["key"], f["label"][:60]) for f in other_fields or []]
        self.fields["show_if_field"].choices = choices  # type: ignore[attr-defined]

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("type") in CHOICE_TYPES and not (data.get("options_text") or "").strip():
            self.add_error("options_text", "Add at least one option.")
        if data.get("show_if_field") and not data.get("show_if_equals"):
            self.add_error("show_if_equals", "Enter the answer that shows this question.")
        return data

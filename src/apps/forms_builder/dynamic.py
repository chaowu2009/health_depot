"""Turn a form template's JSON field list into a real, validated Django form."""

from typing import Any

from django import forms
from django.core.validators import RegexValidator

from .schema import NEED_TAGS, field_options, label

PHONE_VALIDATOR = RegexValidator(
    r"^[0-9()+\-.\s]{7,20}$", "Enter a valid phone number. / Ingrese un número válido."
)
REQUIRED_MSG = {"en": "This question is required.", "es": "Esta pregunta es obligatoria."}


def _django_field(f: dict[str, Any], lang: str) -> forms.Field:
    kind = f["type"]
    common: dict[str, Any] = {
        "label": label(f, lang),
        "help_text": label(f, lang, "help_text"),
        "required": False,  # enforced in clean() so show/hide logic works
    }
    choices = [(o["value"], label(o, lang)) for o in field_options(f)]
    if kind == "short_text":
        return forms.CharField(max_length=200, **common)
    if kind == "long_text":
        return forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}), **common)
    if kind in ("single_choice", "yes_no"):
        return forms.ChoiceField(choices=choices, widget=forms.RadioSelect, **common)
    if kind == "multiple_choice":
        return forms.MultipleChoiceField(
            choices=choices, widget=forms.CheckboxSelectMultiple, **common
        )
    if kind == "date":
        return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **common)
    if kind == "phone":
        return forms.CharField(
            max_length=20,
            validators=[PHONE_VALIDATOR],
            widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
            **common,
        )
    if kind == "email":
        return forms.EmailField(max_length=254, **common)
    if kind == "consent":
        return forms.BooleanField(**common)
    raise ValueError(f"Unknown field type {kind}")


class DynamicForm(forms.Form):
    """Form built from template fields. Use ``build_form``."""

    template_fields: list[dict[str, Any]] = []
    lang = "en"

    def is_visible(self, f: dict[str, Any], data: dict[str, Any]) -> bool:
        cond = f.get("show_if")
        if not cond:
            return True
        value = data.get(cond["field"])
        if isinstance(value, list):
            return cond.get("equals") in value
        if isinstance(value, bool):
            return str(value).lower() == str(cond.get("equals")).lower()
        return value == cond.get("equals")

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        for f in self.template_fields:
            key = f["key"]
            if not self.is_visible(f, data):
                data.pop(key, None)
                self.errors.pop(key, None)
                continue
            if f.get("required") and data.get(key) in (None, "", [], False):
                self.add_error(key, REQUIRED_MSG.get(self.lang, REQUIRED_MSG["en"]))
        return data


def build_form(
    fields: list[dict[str, Any]], *, lang: str = "en", data=None, prefix: str = "q"
) -> DynamicForm:
    form_fields = {f["key"]: _django_field(f, lang) for f in fields}
    for f in fields:
        field = form_fields[f["key"]]
        field.widget.attrs["data-required"] = "true" if f.get("required") else "false"
        if f.get("show_if"):
            field.widget.attrs["data-show-if-field"] = f["show_if"]["field"]
            field.widget.attrs["data-show-if-equals"] = str(f["show_if"].get("equals", ""))
    cls = type(
        "TemplateForm", (DynamicForm,), {**form_fields, "template_fields": fields, "lang": lang}
    )
    return cls(data=data, prefix=prefix)


def _display(f: dict[str, Any], value: Any) -> str:
    opts = {o["value"]: o["label"] for o in field_options(f)}
    if isinstance(value, list):
        return ", ".join(opts.get(v, v) for v in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return opts.get(value, str(value))


def answers_snapshot(fields: list[dict[str, Any]], cleaned: dict[str, Any]) -> list[dict]:
    """Store answers with the English question text, so old referrals still read correctly
    after a template is edited."""
    snapshot = []
    for f in fields:
        if f["key"] in cleaned and cleaned[f["key"]] not in (None, "", []):
            value = cleaned[f["key"]]
            snapshot.append(
                {
                    "key": f["key"],
                    "label": f.get("label", f["key"]),
                    "value": _display(f, value),
                    "raw": value.isoformat() if hasattr(value, "isoformat") else value,
                }
            )
    return snapshot


def derive_needs(fields: list[dict[str, Any]], cleaned: dict[str, Any]) -> list[str]:
    needs: list[str] = []
    for f in fields:
        tag = f.get("need_tag")
        if not tag or tag not in NEED_TAGS:
            continue
        value = cleaned.get(f["key"])
        trigger = set(f.get("need_values") or ["yes"])
        values = set(value) if isinstance(value, list) else {value}
        if values & trigger and tag not in needs:
            needs.append(tag)
    return needs

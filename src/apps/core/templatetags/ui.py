from django import forms, template
from django.utils.safestring import SafeString

from apps.core.forms import CHECKBOX_CLASSES, INPUT_CLASSES

register = template.Library()


@register.filter
def styled(bound_field: forms.BoundField) -> SafeString:
    """Render a form field's widget with the shared Tailwind classes."""
    widget = bound_field.field.widget
    css = (
        CHECKBOX_CLASSES
        if isinstance(widget, forms.CheckboxInput | forms.CheckboxSelectMultiple)
        else INPUT_CLASSES
    )
    existing = widget.attrs.get("class", "")
    attrs = {"class": existing or css}
    if bound_field.errors:
        attrs["aria-invalid"] = "true"
        attrs["aria-describedby"] = f"{bound_field.auto_id}_error"
    elif bound_field.help_text:
        attrs["aria-describedby"] = f"{bound_field.auto_id}_help"
    return bound_field.as_widget(attrs=attrs)


@register.filter
def is_checkbox(bound_field: forms.BoundField) -> bool:
    return isinstance(bound_field.field.widget, forms.CheckboxInput)


@register.filter
def details(value: object) -> str:
    """Show audit 'changes' JSON as readable 'key: value' text."""
    if not isinstance(value, dict) or not value:
        return ""
    parts = []
    for key, val in value.items():
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        parts.append(f"{key.replace('_', ' ')}: {val}")
    return " · ".join(parts)


@register.filter
def get(mapping: object, key: str) -> object:
    try:
        return mapping.get(key, "")  # type: ignore[attr-defined]
    except AttributeError:
        return ""


@register.filter
def is_multi(bound_field: forms.BoundField) -> bool:
    return isinstance(bound_field.field.widget, forms.RadioSelect | forms.CheckboxSelectMultiple)


@register.filter
def get_index(sequence: object, index: int) -> object:
    try:
        return sequence[index]  # type: ignore[index]
    except (IndexError, TypeError, KeyError):
        return ""


@register.filter
def split_pairs(value: str) -> list[tuple[str, str]]:
    """'a:Label A,b:Label B' -> [('a', 'Label A'), ('b', 'Label B')]."""
    return [tuple(item.split(":", 1)) for item in value.split(",")]  # type: ignore[misc]


@register.filter
def code_label(value: object) -> str:
    """Turn a stored code like 'SERVICES_PROVIDED' into 'Services provided'."""
    text = str(value or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:].lower()

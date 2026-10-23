"""Shared form styling so every input gets the same accessible Tailwind classes."""

from django import forms

INPUT_CLASSES = (
    "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 "
    "shadow-sm focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-500/30 "
    "disabled:bg-slate-100"
)
CHECKBOX_CLASSES = "h-4 w-4 rounded border-slate-300 text-accent-600 focus:ring-accent-500"


def style_form(form: forms.BaseForm) -> None:
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput | forms.CheckboxSelectMultiple):
            widget.attrs.setdefault("class", CHECKBOX_CLASSES)
        else:
            widget.attrs.setdefault("class", INPUT_CLASSES)


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)  # type: ignore[arg-type]

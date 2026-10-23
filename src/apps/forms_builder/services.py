"""Business logic for editing form templates (kept out of views)."""

from typing import Any

from django.db import transaction

from .models import FormTemplate
from .schema import options_as_text, parse_options, slugify_key, validate_fields


class TemplateLocked(Exception):
    pass


def _check_editable(template: FormTemplate) -> None:
    if template.is_system_template:
        raise TemplateLocked("Prebuilt templates can't be edited. Make a copy to customize it.")


def field_from_form(data: dict[str, Any], key: str) -> dict[str, Any]:
    field: dict[str, Any] = {
        "key": key,
        "type": data["type"],
        "label": data["label"].strip(),
        "label_es": (data.get("label_es") or "").strip(),
        "help_text": (data.get("help_text") or "").strip(),
        "help_es": (data.get("help_es") or "").strip(),
        "required": bool(data.get("required")),
    }
    if data["type"] in ("single_choice", "multiple_choice"):
        field["options"] = parse_options(data.get("options_text") or "")
    if data.get("show_if_field"):
        field["show_if"] = {"field": data["show_if_field"], "equals": data["show_if_equals"]}
    if data.get("need_tag"):
        field["need_tag"] = data["need_tag"]
        values = [v.strip() for v in (data.get("need_values") or "yes").split(",") if v.strip()]
        field["need_values"] = values
    return field


def form_initial(field: dict[str, Any]) -> dict[str, Any]:
    return {
        **{k: field.get(k, "") for k in ("type", "label", "label_es", "help_text", "help_es")},
        "required": field.get("required", False),
        "options_text": options_as_text(field.get("options", [])),
        "show_if_field": (field.get("show_if") or {}).get("field", ""),
        "show_if_equals": (field.get("show_if") or {}).get("equals", ""),
        "need_tag": field.get("need_tag", ""),
        "need_values": ", ".join(field.get("need_values", [])),
    }


@transaction.atomic
def save_fields(template: FormTemplate, fields: list[dict[str, Any]], user) -> FormTemplate:
    _check_editable(template)
    problems = validate_fields(fields)
    if problems:
        raise ValueError(" ".join(problems))
    template.fields = fields
    template.version += 1  # answers keep a snapshot, so old referrals still read correctly
    template.updated_by = user
    template.save(update_fields=["fields", "version", "updated_by", "updated_at"])
    return template


def add_field(template: FormTemplate, data: dict[str, Any], user) -> FormTemplate:
    keys = {f["key"] for f in template.fields}
    field = field_from_form(data, slugify_key(data["label"], keys))
    return save_fields(template, [*template.fields, field], user)


def update_field(template: FormTemplate, key: str, data: dict[str, Any], user) -> FormTemplate:
    fields = [field_from_form(data, key) if f["key"] == key else f for f in template.fields]
    return save_fields(template, fields, user)


def delete_field(template: FormTemplate, key: str, user) -> FormTemplate:
    fields = [f for f in template.fields if f["key"] != key]
    # Drop show-if rules that pointed at the deleted question.
    for f in fields:
        if (f.get("show_if") or {}).get("field") == key:
            f.pop("show_if")
    return save_fields(template, fields, user)


def reorder_fields(template: FormTemplate, order: list[str], user) -> FormTemplate:
    by_key = {f["key"]: f for f in template.fields}
    if set(order) != set(by_key):
        raise ValueError("The new order must include every question exactly once.")
    return save_fields(template, [by_key[k] for k in order], user)


def copy_template(source: FormTemplate, *, name: str, owner, program, user) -> FormTemplate:
    return FormTemplate.objects.create(
        name=name,
        description=source.description,
        program=program,
        owner_organization=owner,
        fields=[dict(f) for f in source.fields],
        is_published=False,
        created_by=user,
        updated_by=user,
    )

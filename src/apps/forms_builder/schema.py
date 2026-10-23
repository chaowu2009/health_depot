"""Form-template field definitions (stored as JSON on FormTemplate.fields).

A field looks like::

    {
      "key": "housing_worry",            # unique within the template
      "type": "yes_no",                  # see FIELD_TYPES
      "label": "...", "label_es": "...",
      "help_text": "", "help_es": "",
      "required": true,
      "options": [{"value": "a", "label": "...", "label_es": "..."}],   # choice types
      "show_if": {"field": "other_key", "equals": "yes"},              # optional
      "need_tag": "HOUSING", "need_values": ["yes"]                    # optional
    }
"""

import re
from typing import Any

FIELD_TYPES = {
    "short_text": "Short text",
    "long_text": "Long text",
    "single_choice": "Single choice",
    "multiple_choice": "Multiple choice",
    "date": "Date",
    "phone": "Phone",
    "email": "Email",
    "yes_no": "Yes / no",
    "consent": "Consent checkbox",
}
CHOICE_TYPES = {"single_choice", "multiple_choice"}
NEED_TAGS = {
    "FOOD": "Food",
    "HOUSING": "Housing",
    "TRANSPORTATION": "Transportation",
    "UTILITIES": "Utilities",
    "SAFETY": "Safety",
    "BEHAVIORAL_HEALTH": "Behavioral health",
    "MEDICAL": "Medical care",
    "OTHER": "Other",
}
YES_NO_OPTIONS = [
    {"value": "yes", "label": "Yes", "label_es": "Sí"},
    {"value": "no", "label": "No", "label_es": "No"},
]


def slugify_key(label: str, existing: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or "question"
    key, n = base, 2
    while key in existing:
        key, n = f"{base}_{n}", n + 1
    return key


def parse_options(text: str) -> list[dict[str, str]]:
    """One option per line: "English label | Spanish label"."""
    options = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        en, _, es = (part.strip() for part in line.partition("|"))
        value = slugify_key(en, seen)
        seen.add(value)
        options.append({"value": value, "label": en, "label_es": es or en})
    return options


def options_as_text(options: list[dict[str, str]]) -> str:
    return "\n".join(f"{o['label']} | {o.get('label_es', '')}".rstrip(" |") for o in options or [])


def field_options(field: dict[str, Any]) -> list[dict[str, str]]:
    if field.get("type") == "yes_no":
        return YES_NO_OPTIONS
    return field.get("options") or []


def label(field_or_option: dict[str, Any], lang: str, key: str = "label") -> str:
    if lang == "es":
        return field_or_option.get(f"{key}_es") or field_or_option.get(key, "")
    return field_or_option.get(key, "")


def validate_fields(fields: list[dict[str, Any]]) -> list[str]:
    """Return problems with a field list (used before saving)."""
    problems = []
    keys = [f.get("key") for f in fields]
    if len(keys) != len(set(keys)):
        problems.append("Two questions have the same key.")
    for f in fields:
        if f.get("type") not in FIELD_TYPES:
            problems.append(f"Unknown field type for '{f.get('label')}'.")
        if f.get("type") in CHOICE_TYPES and not f.get("options"):
            problems.append(f"'{f.get('label')}' needs at least one option.")
        cond = f.get("show_if")
        if cond and cond.get("field") not in keys:
            problems.append(f"'{f.get('label')}' depends on a question that doesn't exist.")
    return problems

"""Form builder, dynamic forms, prebuilt templates (RFP 3.1)."""

import json

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.forms_builder.dynamic import answers_snapshot, build_form, derive_needs
from apps.forms_builder.models import FormTemplate
from tests.conftest import enroll_mfa
from tests.factories import FormTemplateFactory, UserFactory


@pytest.fixture
def manager(db):
    call_command("bootstrap", verbosity=0)
    user = UserFactory(role=User.Role.PROGRAM_MANAGER)
    enroll_mfa(user)
    return user


def test_bootstrap_creates_prebuilt_templates_idempotently(manager):
    call_command("bootstrap", verbosity=0)
    names = set(FormTemplate.objects.filter(is_system_template=True).values_list("name", flat=True))
    assert names == {"General Intake", "SDoH Screening"}
    sdoh = FormTemplate.objects.get(name="SDoH Screening")
    assert all(f.get("label_es") for f in sdoh.fields)  # every question has Spanish text


def test_dynamic_form_required_and_show_if(manager):
    fields = FormTemplate.objects.get(name="SDoH Screening").fields
    base = {
        f"q-{k}": "no"
        for k in ("housing_worry", "food_worry", "transportation", "utilities", "safety")
    }
    assert build_form(fields, data=base).is_valid()
    missing = dict(base)
    missing.pop("q-food_worry")
    form = build_form(fields, data=missing)
    assert not form.is_valid() and "food_worry" in form.errors
    # Hidden follow-up answers are dropped when the condition isn't met.
    hidden = {**base, "q-safety_now": "yes"}
    form = build_form(fields, data=hidden)
    assert form.is_valid() and "safety_now" not in form.cleaned_data


def test_needs_and_snapshot(manager):
    fields = FormTemplate.objects.get(name="SDoH Screening").fields
    data = {
        "q-housing_worry": "yes",
        "q-food_worry": "yes",
        "q-transportation": "no",
        "q-utilities": "no",
        "q-safety": "no",
    }
    form = build_form(fields, data=data)
    assert form.is_valid()
    assert derive_needs(fields, form.cleaned_data) == ["HOUSING", "FOOD"]
    snap = answers_snapshot(fields, form.cleaned_data)
    assert snap[0]["value"] == "Yes" and snap[0]["label"].startswith("Are you worried")


def test_spanish_labels(manager):
    fields = FormTemplate.objects.get(name="General Intake").fields
    form = build_form(fields, lang="es")
    assert form.fields["urgency"].label == "¿Qué tan pronto necesita ayuda?"


def _field_post(prefix, **kw):
    data = {
        "type": "short_text",
        "label": "Household size",
        "label_es": "Tamaño del hogar",
        "help_text": "",
        "help_es": "",
        "options_text": "",
        "show_if_field": "",
        "show_if_equals": "",
        "need_tag": "",
        "need_values": "",
    }
    data.update(kw)
    return {f"{prefix}-{k}": v for k, v in data.items()}


def test_builder_add_update_reorder_delete(client, manager):
    template = FormTemplateFactory(fields=[])
    client.force_login(manager)
    url = f"/forms/{template.pk}/"
    assert client.get(url, secure=True).status_code == 200
    client.post(url + "questions/add/", _field_post("add", required="on"), secure=True)
    client.post(
        url + "questions/add/",
        _field_post(
            "add", type="single_choice", label="Has children?", options_text="Yes | Sí\nNo | No"
        ),
        secure=True,
    )
    template.refresh_from_db()
    assert [f["key"] for f in template.fields] == ["household_size", "has_children"]
    assert template.fields[1]["options"][0] == {"value": "yes", "label": "Yes", "label_es": "Sí"}
    v = template.version
    client.post(
        url + "questions/household_size/",
        _field_post("edit-household_size", label="People in household"),
        secure=True,
    )
    template.refresh_from_db()
    assert template.fields[0]["label"] == "People in household" and template.version == v + 1
    resp = client.post(
        url + "questions/reorder/",
        json.dumps({"order": ["has_children", "household_size"]}),
        content_type="application/json",
        secure=True,
    )
    assert resp.status_code == 204
    template.refresh_from_db()
    assert template.fields[0]["key"] == "has_children"
    client.post(url + "questions/has_children/delete/", secure=True)
    template.refresh_from_db()
    assert [f["key"] for f in template.fields] == ["household_size"]


def test_choice_question_needs_options(client, manager):
    template = FormTemplateFactory(fields=[])
    client.force_login(manager)
    resp = client.post(
        f"/forms/{template.pk}/questions/add/",
        _field_post("add", type="single_choice"),
        secure=True,
    )
    assert resp.status_code == 200 and b"Add at least one option" in resp.content


def test_prebuilt_templates_are_locked_but_copyable(client, manager):
    sdoh = FormTemplate.objects.get(name="SDoH Screening")
    client.force_login(manager)
    resp = client.post(f"/forms/{sdoh.pk}/questions/add/", _field_post("add"), secure=True)
    assert resp.status_code == 404
    resp = client.post(
        "/forms/new/",
        {"name": "SDoH — Lusby", "description": "", "program": "", "start_from": str(sdoh.pk)},
        secure=True,
    )
    copy = FormTemplate.objects.get(name="SDoH — Lusby")
    assert resp.status_code == 302 and copy.fields == sdoh.fields and not copy.is_system_template


def test_staff_can_view_but_not_edit_forms(client, staff_user, manager):
    template = FormTemplateFactory(fields=[])
    client.force_login(staff_user)
    assert client.get(f"/forms/{template.pk}/", secure=True).status_code == 200
    assert (
        client.post(
            f"/forms/{template.pk}/questions/add/", _field_post("add"), secure=True
        ).status_code
        == 403
    )


def test_builder_preview_renders_partner_branding(client, manager):
    from tests.factories import OrganizationFactory

    partner = OrganizationFactory(name="Fictional Lusby Food Shelf", brand_color="#123456")
    sdoh = FormTemplate.objects.get(name="SDoH Screening")
    client.force_login(manager)
    html = client.get(f"/forms/{sdoh.pk}/?partner={partner.pk}&lang=es", secure=True)
    text = html.content.decode()
    assert "Fictional Lusby Food Shelf" in text and "#123456" in text
    assert "Información de la persona referida" in text

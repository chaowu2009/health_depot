"""Partners, referral links and QR codes (RFP 3.1)."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.accounts.models import User, UserProgramAccess
from apps.forms_builder.models import FormTemplate
from apps.organizations.models import Organization
from apps.referrals.models import ReferralLink
from tests.conftest import enroll_mfa
from tests.factories import OrganizationFactory, ProgramFactory, UserFactory

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def setup(db, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    }
    call_command("bootstrap", verbosity=0)
    program = ProgramFactory()
    manager = UserFactory(role=User.Role.PROGRAM_MANAGER)
    UserProgramAccess.objects.create(user=manager, program=program)
    enroll_mfa(manager)
    return {
        "program": program,
        "manager": manager,
        "template": FormTemplate.objects.get(name="SDoH Screening"),
    }


def _partner_post(**extra):
    data = {
        "name": "Fictional Bayside Pantry",
        "contact_name": "Alex Doe",
        "contact_email": "alex@example.test",
        "contact_phone": "410-555-0100",
        "address": "1 Main St",
        "website": "",
        "brand_color": "#12827A",
        "service_types": ["FOOD"],
        "service_area_zips": "20678, 20657",
        "is_active": "on",
    }
    data.update(extra)
    return data


def test_manager_creates_partner_with_logo(client, setup):
    client.force_login(setup["manager"])
    data = _partner_post(
        programs=[str(setup["program"].pk)],
        logo=SimpleUploadedFile("logo.png", PNG, content_type="image/png"),
    )
    resp = client.post("/partners/new/", data, secure=True)
    assert resp.status_code == 302, resp.content.decode()[:1500]
    partner = Organization.objects.get(name="Fictional Bayside Pantry")
    assert partner.service_area_zips == ["20678", "20657"]
    assert partner.logo.name.endswith(".png")
    assert partner.partner_programs.filter(pk=setup["program"].pk).exists()


def test_svg_or_fake_logo_rejected(client, setup):
    client.force_login(setup["manager"])
    data = _partner_post(
        logo=SimpleUploadedFile("x.svg", b"<svg onload=alert(1)>", content_type="image/svg+xml")
    )
    resp = client.post("/partners/new/", data, secure=True)
    assert resp.status_code == 200 and b"PNG or JPEG" in resp.content


def test_bad_zip_rejected(client, setup):
    client.force_login(setup["manager"])
    resp = client.post("/partners/new/", _partner_post(service_area_zips="2067"), secure=True)
    assert resp.status_code == 200 and b"5-digit ZIP" in resp.content


def test_staff_cannot_create_partners(client, staff_user, setup):
    client.force_login(staff_user)
    assert client.get("/partners/new/", secure=True).status_code == 403
    assert client.get("/partners/", secure=True).status_code == 200


def test_link_create_qr_and_toggle(client, setup):
    partner = OrganizationFactory()
    client.force_login(setup["manager"])
    resp = client.post(
        f"/partners/{partner.pk}/links/new/",
        {
            "label": "Front desk",
            "program": str(setup["program"].pk),
            "form_template": str(setup["template"].pk),
        },
        secure=True,
    )
    assert resp.status_code == 302
    link = ReferralLink.objects.get(partner=partner)
    assert len(link.slug) >= 8
    qr = client.get(f"/partners/links/{link.pk}/qr.svg?download=1", secure=True)
    assert qr.status_code == 200 and qr["Content-Type"] == "image/svg+xml"
    assert b"<svg" in qr.content and "attachment" in qr["Content-Disposition"]
    page = client.get(f"/partners/{partner.pk}/", secure=True).content.decode()
    assert f"/r/{link.slug}/" in page
    client.post(f"/partners/links/{link.pk}/toggle/", secure=True)
    link.refresh_from_db()
    assert link.is_active is False


def test_manager_cannot_create_link_for_program_without_access(client, setup):
    partner = OrganizationFactory()
    other = ProgramFactory()
    client.force_login(setup["manager"])
    client.post(
        f"/partners/{partner.pk}/links/new/",
        {"label": "X", "program": str(other.pk), "form_template": str(setup["template"].pk)},
        secure=True,
    )
    assert not ReferralLink.objects.filter(partner=partner).exists()


def test_partner_user_sees_only_own_organization(client, setup):
    mine, theirs = OrganizationFactory(), OrganizationFactory()
    user = UserFactory(role=User.Role.PARTNER_USER, organization=mine)
    enroll_mfa(user)
    client.force_login(user)
    resp = client.get("/partners/", secure=True)
    assert resp.status_code == 302 and str(mine.pk) in resp["Location"]
    assert client.get(f"/partners/{theirs.pk}/", secure=True).status_code == 404
    assert client.get("/forms/", secure=True).status_code == 403
    nav = client.get(f"/partners/{mine.pk}/", secure=True).content.decode()
    assert "My organization" in nav and "/cases/" not in nav


def test_qr_for_other_partners_link_is_404_for_partner_user(client, setup):
    mine, theirs = OrganizationFactory(), OrganizationFactory()
    link = ReferralLink.objects.create(
        partner=theirs, program=setup["program"], form_template=setup["template"], label="x"
    )
    user = UserFactory(role=User.Role.PARTNER_USER, organization=mine)
    enroll_mfa(user)
    client.force_login(user)
    assert client.get(f"/partners/links/{link.pk}/qr.svg", secure=True).status_code == 404


def _unused():
    return io

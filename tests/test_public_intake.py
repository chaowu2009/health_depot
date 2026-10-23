"""Public intake via referral links (RFP 3.1) and staff-created referrals."""

import pytest
from django.core.management import call_command

from apps.accounts.models import User, UserProgramAccess
from apps.clients.models import Client
from apps.forms_builder.models import FormTemplate
from apps.referrals.models import Referral, ReferralEvent, ReferralLink
from tests.conftest import enroll_mfa
from tests.factories import ClientFactory, OrganizationFactory, ProgramFactory, UserFactory


@pytest.fixture
def link(db):
    call_command("bootstrap", verbosity=0)
    partner = OrganizationFactory(name="Fictional Northside Pantry")
    return ReferralLink.objects.create(
        partner=partner,
        program=ProgramFactory(),
        label="Front desk",
        form_template=FormTemplate.objects.get(name="SDoH Screening"),
    )


def form_data(**over):
    data = {
        "id-first_name": "Sam",
        "id-last_name": "Synthetic",
        "id-date_of_birth": "1980-04-02",
        "id-phone": "410-555-0142",
        "id-email": "",
        "id-zip_code": "20678",
        "id-preferred_language": "English",
        "id-preferred_contact_method": "PHONE",
        "id-consent_to_contact": "on",
        "id-consent_to_share": "on",
        "id-website": "",
        "q-housing_worry": "yes",
        "q-food_worry": "no",
        "q-transportation": "yes",
        "q-utilities": "no",
        "q-safety": "yes",
        "q-safety_now": "yes",
    }
    data.update(over)
    return data


def test_get_counts_visit_and_renders_branding(client, link):
    resp = client.get(f"/r/{link.slug}/", secure=True)
    link.refresh_from_db()
    assert resp.status_code == 200 and link.visit_count == 1
    assert b"Fictional Northside Pantry" in resp.content


def test_spanish_version(client, link):
    resp = client.get(f"/r/{link.slug}/?lang=es", secure=True)
    assert "Información de la persona referida".encode() in resp.content
    assert b'lang="es"' in resp.content


def test_submit_creates_client_and_referral(client, link):
    resp = client.post(f"/r/{link.slug}/", form_data(), secure=True)
    assert resp.status_code == 302
    assert "CR-" not in resp["Location"]  # no identifiers in the URL
    referral = Referral.objects.get()
    assert referral.status == "SUBMITTED" and referral.direction == "INBOUND"
    assert referral.sending_organization == link.partner
    assert referral.receiving_organization.slug == "cchd"
    assert referral.needs == ["HOUSING", "TRANSPORTATION", "SAFETY"]
    assert referral.priority == "URGENT"  # "in danger right now" = yes
    assert referral.form_version == link.form_template.version
    assert referral.answers["items"][0]["label"].startswith("Are you worried")
    assert ReferralEvent.objects.filter(referral=referral, to_status="SUBMITTED").exists()
    link.refresh_from_db()
    assert link.submission_count == 1
    thanks = client.get(resp["Location"], secure=True)
    assert referral.reference_number.encode() in thanks.content
    client_rec = Client.objects.get()
    assert client_rec.consent_to_share and client_rec.programs.filter(pk=link.program_id).exists()


def test_required_fields_and_phone_or_email(client, link):
    data = form_data(**{"id-phone": "", "q-housing_worry": ""})
    resp = client.post(f"/r/{link.slug}/", data, secure=True)
    assert resp.status_code == 200
    assert b"Please give a phone number or an email address" in resp.content
    assert b"This question is required" in resp.content
    assert not Referral.objects.exists()


def test_honeypot_stores_nothing(client, link):
    resp = client.post(f"/r/{link.slug}/", form_data(**{"id-website": "spam.example"}), secure=True)
    assert resp.status_code == 302 and not Referral.objects.exists()


def test_inactive_link_is_closed(client, link):
    link.is_active = False
    link.save()
    assert client.get(f"/r/{link.slug}/", secure=True).status_code == 410
    assert client.post(f"/r/{link.slug}/", form_data(), secure=True).status_code == 410


def test_rate_limited(client, link, settings):
    settings.RATELIMIT_ENABLE = True
    for _ in range(10):
        client.post(f"/r/{link.slug}/", form_data(**{"id-first_name": ""}), secure=True)
    assert client.post(f"/r/{link.slug}/", form_data(), secure=True).status_code == 429


def test_same_person_reuses_client(client, link):
    existing = ClientFactory(
        first_name="Sam", last_name="Synthetic", date_of_birth="1980-04-02", phone="(410) 555-0142"
    )
    client.post(f"/r/{link.slug}/", form_data(), secure=True)
    assert Client.objects.count() == 1
    assert Referral.objects.get().client == existing


def test_possible_duplicate_flagged_not_merged(client, link):
    existing = ClientFactory(
        first_name="Samantha", last_name="Synthetic", date_of_birth="1980-04-02", phone=""
    )
    client.post(f"/r/{link.slug}/", form_data(), secure=True)
    new = Client.objects.exclude(pk=existing.pk).get()
    assert new.possible_duplicate_of == existing


def test_staff_create_outbound_referral(client, link):
    staff = UserFactory(role=User.Role.STAFF)
    UserProgramAccess.objects.create(user=staff, program=link.program)
    enroll_mfa(staff)
    client.force_login(staff)
    resp = client.post(
        "/referrals/new/",
        {
            "first_name": "Dana",
            "last_name": "Example",
            "date_of_birth": "1975-01-01",
            "phone": "410-555-0199",
            "program": str(link.program.pk),
            "partner": str(link.partner.pk),
            "priority": "HIGH",
            "needs": ["FOOD"],
            "reason": "Needs groceries this week.",
        },
        secure=True,
    )
    assert resp.status_code == 302
    referral = Referral.objects.get(direction="OUTBOUND")
    assert referral.receiving_organization == link.partner and referral.priority == "HIGH"
    assert referral.created_by == staff


def test_read_only_cannot_create_referrals(client, link):
    leader = UserFactory(role=User.Role.READ_ONLY)
    enroll_mfa(leader)
    client.force_login(leader)
    assert client.get("/referrals/new/", secure=True).status_code == 302

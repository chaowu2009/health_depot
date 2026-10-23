"""Phase 2 previews render; client spreadsheet import works end to end."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.accounts.models import User, UserProgramAccess
from apps.clients.models import Client
from tests.conftest import enroll_mfa
from tests.factories import ClientFactory, ProgramFactory, UserFactory


@pytest.fixture
def manager(db, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    }
    user = UserFactory(role=User.Role.PROGRAM_MANAGER)
    program = ProgramFactory()
    UserProgramAccess.objects.create(user=user, program=program)
    enroll_mfa(user)
    return user, program


@pytest.mark.parametrize(
    "url", ["/scheduling/", "/scheduling/book/", "/events/", "/communications/", "/ehr/"]
)
def test_previews_render_with_badge(client, staff_user, url):
    client.force_login(staff_user)
    resp = client.get(url, secure=True)
    assert resp.status_code == 200 and "Phase 2 — Preview" in resp.content.decode()


def test_communications_preview_report(client, staff_user):
    client.force_login(staff_user)
    resp = client.post(
        "/communications/",
        {"segment": "all_partners", "channel": "email", "subject": "Hi", "body": "x"},
        secure=True,
    )
    assert b"Delivery report" in resp.content and b"no messages were sent" in resp.content


def _csv(text):
    return SimpleUploadedFile("clients.csv", text.encode(), content_type="text/csv")


def test_csv_import_flow(client, manager):
    user, program = manager
    ClientFactory(
        first_name="Existing", last_name="Person", date_of_birth="1970-01-01", phone="410-555-0000"
    )
    client.force_login(user)
    data = (
        "First Name,Last Name,DOB,Phone,ZIP,Language\n"
        "Ana,Synthetic,03/04/1990,410-555-0101,20678,Spanish\n"
        "Existing,Person,1970-01-01,410-555-0000,20657,English\n"
        "Bad,Row,not-a-date,,123,English\n"
    )
    resp = client.post(
        "/import/", {"step": "upload", "program": str(program.pk), "file": _csv(data)}, secure=True
    )
    assert resp.status_code == 302
    page = client.get("/import/", secure=True)
    assert page.context["step"] == "map"
    mapping = page.context["mapping"]
    assert mapping["first_name"] == "First Name" and mapping["date_of_birth"] == "DOB"
    post = {"step": "preview", **{f"map_{k}": v for k, v in mapping.items()}}
    preview = client.post("/import/", post, secure=True)
    assert preview.context["counts"] == {
        "new": 1,
        "existing": 1,
        "possible_duplicate": 0,
        "error": 1,
    }
    done = client.post("/import/", {**post, "step": "confirm"}, secure=True)
    assert done.context["counts"]["created"] == 1 and done.context["counts"]["skipped"] == 1
    ana = Client.objects.get(first_name="Ana")
    assert ana.preferred_language == "Spanish" and ana.programs.filter(pk=program.pk).exists()


def test_xlsx_import_and_missing_required_mapping(client, manager):
    user, program = manager
    wb = Workbook()
    ws = wb.active
    ws.append(["Given name", "Surname", "Birthdate"])
    ws.append(["Leo", "Synthetic", "1999-12-31"])
    buf = io.BytesIO()
    wb.save(buf)
    client.force_login(user)
    client.post(
        "/import/",
        {
            "step": "upload",
            "program": str(program.pk),
            "file": SimpleUploadedFile("c.xlsx", buf.getvalue()),
        },
        secure=True,
    )
    resp = client.post(
        "/import/",
        {
            "step": "preview",
            "map_first_name": "Given name",
            "map_last_name": "",
            "map_date_of_birth": "Birthdate",
        },
        secure=True,
    )
    assert b"Map these required fields" in resp.content


def test_staff_cannot_import(client, staff_user):
    client.force_login(staff_user)
    assert client.get("/import/", secure=True).status_code == 403

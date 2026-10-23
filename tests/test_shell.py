import pytest


@pytest.mark.django_db
def test_shell_requires_login(client):
    resp = client.get("/dashboard/", secure=True)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


@pytest.mark.django_db
def test_shell_renders_navigation(client, staff_user):
    client.force_login(staff_user)
    resp = client.get("/dashboard/", secure=True)
    html = resp.content.decode()
    assert resp.status_code == 200
    for label in ["Dashboard", "Referrals", "Cases", "Partners", "Forms", "Messages", "Reports"]:
        assert label in html
    assert "Phase 2" in html
    assert 'aria-current="page"' in html
    assert "Demo environment" in html
    assert 'href="/manage/users/"' not in html  # admin link hidden from staff


@pytest.mark.django_db
def test_phase2_page_has_preview_badge(client, staff_user):
    client.force_login(staff_user)
    html = client.get("/scheduling/", secure=True).content.decode()
    assert "Phase 2 — Preview" in html


@pytest.mark.django_db
def test_unknown_section_404(client, staff_user):
    client.force_login(staff_user)
    assert client.get("/nope/", secure=True).status_code == 404


def test_no_external_assets_in_base_template():
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / "src" / "templates"
    for tpl in base.rglob("*.html"):
        text = tpl.read_text()
        assert "http://" not in text and "https://" not in text, f"external URL in {tpl}"


def test_code_label_filter_humanizes_stored_codes():
    from apps.core.templatetags.ui import code_label

    assert code_label("SERVICES_PROVIDED") == "Services provided"
    assert code_label("") == ""

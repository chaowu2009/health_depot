"""Dashboards and exports (RFP 3.6)."""

import io
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from openpyxl import load_workbook

from apps.accounts.models import User, UserProgramAccess
from apps.audit.models import AuditLog
from apps.referrals.services import change_status
from apps.reports import services
from tests.conftest import enroll_mfa
from tests.factories import (
    ClientFactory,
    OrganizationFactory,
    ProgramFactory,
    ReferralFactory,
    UserFactory,
)


@pytest.fixture
def data(db):
    call_command("bootstrap", verbosity=0)
    from apps.organizations.models import Organization

    cchd = Organization.objects.get(slug="cchd")
    a, b = ProgramFactory(name="Program A"), ProgramFactory(name="Program B")
    partner = OrganizationFactory(name="Fictional Pantry")
    staff = UserFactory(role=User.Role.STAFF, organization=cchd)
    UserProgramAccess.objects.create(user=staff, program=a)
    enroll_mfa(staff)
    now = timezone.now()
    refs = []
    for i in range(4):
        c = ClientFactory(
            race=["WHITE"],
            ethnicity="NOT_HISPANIC",
            zip_code="20678",
            preferred_language="Spanish" if i % 2 else "English",
        )
        refs.append(
            ReferralFactory(
                program=a,
                client=c,
                sending_organization=cchd,
                receiving_organization=partner,
                direction="OUTBOUND",
                submitted_at=now - timedelta(days=i),
                needs=["FOOD"],
                last_status_change_at=now - timedelta(days=i),
            )
        )
    ReferralFactory(
        program=b,
        sending_organization=partner,
        receiving_organization=cchd,
        submitted_at=now,
        last_status_change_at=now,
        needs=["HOUSING"],
    )
    partner_user = UserFactory(role=User.Role.PARTNER_USER, organization=partner)
    change_status(refs[0], "ACCEPTED", user=partner_user)
    change_status(refs[0], "COMPLETED", user=partner_user, note="Done", outcome="SERVICES_PROVIDED")
    change_status(refs[1], "DECLINED", user=partner_user, note="Full")
    return {"staff": staff, "refs": refs, "partner": partner, "partner_user": partner_user}


def test_dashboard_metrics_respect_scope(data):
    today = timezone.localdate()
    d = services.dashboard(data["staff"], start=today - timedelta(days=30), end=today)
    k = d["kpis"]
    assert k["referrals"] == 4  # program B is out of scope
    assert k["closed_loop_rate"] == 50 and k["completion_rate"] == 50
    assert dict(d["needs"]) == {"Food": 4}
    assert dict(d["languages"]) == {"English": 2, "Spanish": 2}
    perf = d["partners"][0]
    assert perf["partner"] == "Fictional Pantry" and perf["received"] == 4
    assert perf["accepted_pct"] == 50 and perf["completion_pct"] == 50
    assert sum(sum(s["data"]) for s in d["over_time"]["series"]) == 4


def test_dashboard_page_renders_charts_and_tables(client, data):
    client.force_login(data["staff"])
    html = client.get("/dashboard/", secure=True).content.decode()
    assert 'id="dashboard-data"' in html and "chart-over-time" in html
    assert "View as table" in html and "Partner performance" in html


def test_partner_dashboard_only_their_referrals(client, data):
    enroll_mfa(data["partner_user"])
    client.force_login(data["partner_user"])
    resp = client.get("/dashboard/", secure=True)
    assert resp.status_code == 200 and resp.context["data"]["kpis"]["referrals"] == 5
    assert client.get("/reports/", secure=True).status_code == 403


def test_report_preview_and_excel_export_audited(client, data):
    client.force_login(data["staff"])
    resp = client.get("/reports/?columns=reference_number&columns=status", secure=True)
    assert resp.context["headers"] == ["Reference", "Status"] and resp.context["total"] == 4
    resp = client.get("/reports/?columns=reference_number&columns=needs&export=xlsx", secure=True)
    wb = load_workbook(io.BytesIO(resp.content))
    rows = list(wb.active.values)
    assert rows[0] == ("Reference", "Needs") and len(rows) == 5
    entry = AuditLog.objects.get(action="EXPORT")
    assert entry.changes["rows"] == 4 and entry.actor == data["staff"]


def test_csv_export_neutralizes_formulas(client, data):
    from apps.referrals.models import Referral

    Referral.objects.filter(pk=data["refs"][2].pk).update(outcome='=HYPERLINK("x")')
    client.force_login(data["staff"])
    resp = client.get("/reports/?columns=outcome&export=csv", secure=True)
    body = resp.content.decode()
    assert resp["Content-Type"].startswith("text/csv")
    assert "'=" in body or "=hyperlink" not in body.lower()

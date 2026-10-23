"""Dashboard metrics and report datasets. Everything starts from the user's scope."""

import statistics
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.cases.models import Case
from apps.clients.models import Client
from apps.forms_builder.schema import NEED_TAGS
from apps.organizations.models import Organization
from apps.referrals.models import Referral
from apps.referrals.workflow import FINAL_STATUSES

STATUS_GROUPS = OrderedDict(
    [
        ("Waiting", ["SUBMITTED", "RECEIVED"]),
        ("In progress", ["ACCEPTED", "IN_PROGRESS"]),
        ("Completed", ["COMPLETED"]),
        ("Declined or closed", ["DECLINED", "CLOSED_UNABLE_TO_CONTACT"]),
    ]
)
RACE_LABELS = dict(Client.Race.choices)
ETHNICITY_LABELS = dict(Client.Ethnicity.choices)
AGE_BUCKETS = [
    (0, 17, "0–17"),
    (18, 24, "18–24"),
    (25, 44, "25–44"),
    (45, 64, "45–64"),
    (65, 200, "65+"),
]


def scoped_referrals(user, *, start: date, end: date, program=None, partner=None):
    qs = Referral.objects.for_user(user).filter(
        submitted_at__date__gte=start, submitted_at__date__lte=end
    )
    if program:
        qs = qs.filter(program=program)
    if partner:
        qs = qs.filter(Q(sending_organization=partner) | Q(receiving_organization=partner))
    return qs


def first_response_at(r: Referral) -> datetime | None:
    times = [t for t in (r.received_at, r.accepted_at, r.declined_at) if t]
    return min(times) if times else None


def response_days(r: Referral) -> float | None:
    """Days from submission to the first response (received, accepted or declined)."""
    first = first_response_at(r)
    if first is None or r.submitted_at is None:
        return None
    return (first - r.submitted_at).total_seconds() / 86400


def _median_days(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def _age(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def dashboard(user, *, start: date, end: date, program=None, partner=None) -> dict[str, Any]:
    today = timezone.localdate()
    qs = scoped_referrals(user, start=start, end=end, program=program, partner=partner)
    rows = list(
        qs.select_related("client", "program", "sending_organization", "receiving_organization")
    )
    total = len(rows)
    final = [r for r in rows if r.status in FINAL_STATUSES]
    completed = [r for r in rows if r.status == "COMPLETED"]
    response_list = [d for d in (response_days(r) for r in rows) if d is not None]
    month_start = today.replace(day=1)
    this_month = Referral.objects.for_user(user).filter(submitted_at__date__gte=month_start)
    if program:
        this_month = this_month.filter(program=program)

    # Referrals over time, weekly, stacked by status group.
    weeks: list[date] = []
    cursor = start - timedelta(days=start.weekday())
    while cursor <= end:
        weeks.append(cursor)
        cursor += timedelta(days=7)
    series = {name: [0] * len(weeks) for name in STATUS_GROUPS}
    for r in rows:
        week = r.submitted_at.date() - timedelta(days=r.submitted_at.date().weekday())
        idx = (week - weeks[0]).days // 7 if weeks else 0
        for name, statuses in STATUS_GROUPS.items():
            if r.status in statuses and 0 <= idx < len(weeks):
                series[name][idx] += 1

    by_program = Counter(r.program.name for r in rows)
    needs = Counter(n for r in rows for n in r.needs)
    ages = Counter()
    races = Counter()
    ethnicities = Counter()
    languages = Counter()
    zips = Counter()
    seen_clients = set()
    for r in rows:
        c = r.client
        if c.pk in seen_clients:
            continue
        seen_clients.add(c.pk)
        a = _age(c.date_of_birth, today)
        ages[next(label for lo, hi, label in AGE_BUCKETS if lo <= a <= hi)] += 1
        for race in c.race or ["DECLINED"]:
            races[RACE_LABELS.get(race, race)] += 1
        ethnicities[ETHNICITY_LABELS.get(c.ethnicity, "Not recorded")] += 1
        languages[c.preferred_language or "Not recorded"] += 1
        if c.zip_code:
            zips[c.zip_code[:5]] += 1

    return {
        "kpis": {
            "referrals": total,
            "this_month": this_month.count(),
            "closed_loop_rate": round(100 * len(final) / total) if total else None,
            "completion_rate": round(100 * len(completed) / len(final)) if final else None,
            "median_response_days": _median_days(response_list),
            "overdue": Referral.objects.for_user(user).overdue().count(),
            "active_cases": Case.objects.for_user(user).exclude(status="DISCHARGED").count(),
            "clients": len(seen_clients),
        },
        "over_time": {
            "labels": [w.strftime("%b %d") for w in weeks],
            "series": [{"name": k, "data": v} for k, v in series.items()],
        },
        "by_program": _pairs(by_program),
        "needs": [(NEED_TAGS.get(k, k.title()), v) for k, v in needs.most_common()],
        "ages": [(label, ages.get(label, 0)) for _, _, label in AGE_BUCKETS],
        "races": _pairs(races),
        "ethnicities": _pairs(ethnicities),
        "languages": _pairs(languages),
        "zips": _pairs(zips, limit=10),
        "partners": partner_performance(rows),
    }


def _pairs(counter: Counter, limit: int | None = None) -> list[tuple[str, int]]:
    return [(k, v) for k, v in counter.most_common(limit)]


def partner_performance(rows: list[Referral]) -> list[dict[str, Any]]:
    stats: dict[Any, dict[str, Any]] = {}
    for r in rows:
        for org, role in ((r.receiving_organization, "received"), (r.sending_organization, "sent")):
            if org.org_type != Organization.OrgType.COMMUNITY_PARTNER:
                continue
            s = stats.setdefault(
                org.pk,
                {
                    "partner": org.name,
                    "id": str(org.pk),
                    "received": 0,
                    "sent": 0,
                    "accepted": 0,
                    "decided": 0,
                    "completed": 0,
                    "final": 0,
                    "response": [],
                },
            )
            s[role] += 1
            if role != "received":
                continue
            if r.accepted_at or r.declined_at:
                s["decided"] += 1
                if r.accepted_at:
                    s["accepted"] += 1
            if r.status in FINAL_STATUSES:
                s["final"] += 1
                if r.status == "COMPLETED":
                    s["completed"] += 1
            days = response_days(r)
            if days is not None:
                s["response"].append(days)
    out = []
    for s in stats.values():
        out.append(
            {
                "partner": s["partner"],
                "id": s["id"],
                "received": s["received"],
                "sent": s["sent"],
                "accepted_pct": round(100 * s["accepted"] / s["decided"]) if s["decided"] else None,
                "median_response_days": _median_days(s["response"]),
                "completion_pct": round(100 * s["completed"] / s["final"]) if s["final"] else None,
            }
        )
    return sorted(out, key=lambda x: (-(x["received"] + x["sent"]), x["partner"]))


# --- Report builder --------------------------------------------------------------------------
REPORT_FIELDS: "OrderedDict[str, tuple[str, Any]]" = OrderedDict(
    [
        ("reference_number", ("Reference", lambda r: r.reference_number)),
        (
            "submitted",
            ("Submitted", lambda r: r.submitted_at.date().isoformat() if r.submitted_at else ""),
        ),
        ("status", ("Status", lambda r: r.get_status_display())),
        ("priority", ("Priority", lambda r: r.get_priority_display())),
        ("program", ("Program", lambda r: r.program.name)),
        ("from", ("From", lambda r: r.sending_organization.name)),
        ("to", ("To", lambda r: r.receiving_organization.name)),
        ("needs", ("Needs", lambda r: ", ".join(NEED_TAGS.get(n, n) for n in r.needs))),
        (
            "first_response_days",
            (
                "Days to first response",
                lambda r: "" if response_days(r) is None else round(response_days(r) or 0, 1),
            ),
        ),
        ("outcome", ("Outcome", lambda r: r.outcome.replace("_", " ").title())),
        ("assigned_to", ("Assigned to", lambda r: str(r.assigned_to or ""))),
        ("client_name", ("Client name", lambda r: f"{r.client.first_name} {r.client.last_name}")),
        (
            "client_age",
            ("Client age", lambda r: _age(r.client.date_of_birth, timezone.localdate())),
        ),
        ("client_zip", ("Client ZIP", lambda r: r.client.zip_code)),
        ("client_language", ("Language", lambda r: r.client.preferred_language)),
        (
            "client_race",
            ("Race", lambda r: ", ".join(RACE_LABELS.get(x, x) for x in r.client.race)),
        ),
        ("client_ethnicity", ("Ethnicity", lambda r: ETHNICITY_LABELS.get(r.client.ethnicity, ""))),
    ]
)
DEFAULT_FIELDS = [
    "reference_number",
    "submitted",
    "status",
    "program",
    "from",
    "to",
    "needs",
    "first_response_days",
    "outcome",
]
IDENTIFYING_FIELDS = {"client_name"}


def report_rows(qs, fields: list[str]) -> tuple[list[str], list[list[Any]]]:
    fields = [f for f in fields if f in REPORT_FIELDS] or DEFAULT_FIELDS
    headers = [REPORT_FIELDS[f][0] for f in fields]
    rows = [
        [REPORT_FIELDS[f][1](r) for f in fields]
        for r in qs.select_related(
            "client", "program", "sending_organization", "receiving_organization", "assigned_to"
        )
    ]
    return headers, rows

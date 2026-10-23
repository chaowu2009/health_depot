"""Deterministic sample data for Phase 2 previews (no database tables)."""

import random
from datetime import date, datetime, time, timedelta

from django.utils import timezone

CLINICS = [
    {"name": "Prince Frederick — Main Clinic", "short": "Prince Frederick"},
    {"name": "Lusby — Southern Pines Clinic", "short": "Lusby"},
    {"name": "North Beach — Community Center", "short": "North Beach"},
]
SERVICES = [
    "Immunizations",
    "WIC visit",
    "Family planning",
    "TB testing",
    "Blood pressure check",
    "Dental screening",
]
PROVIDERS = ["Nurse Patel", "Nurse Okafor", "Dr. Lindqvist", "CHW Romero", "Nurse Brennan"]
FIRST = [
    "Ava",
    "Liam",
    "Noah",
    "Mia",
    "Elena",
    "Jamal",
    "Grace",
    "Omar",
    "Lucy",
    "Diego",
    "Hana",
    "Isaac",
    "Priya",
    "Tomas",
    "Zoe",
]


def week_days(start: date | None = None) -> list[date]:
    today = start or timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(5)]


def appointments(days: list[date]) -> list[dict]:
    rng = random.Random(days[0].toordinal())
    out = []
    for day in days:
        for c_idx, _clinic in enumerate(CLINICS):
            hour = 8
            while hour < 16:
                if rng.random() < 0.62:
                    length = rng.choice([30, 30, 60])
                    start = datetime.combine(day, time(hour, rng.choice([0, 30])))
                    out.append(
                        {
                            "day": day,
                            "clinic": c_idx,
                            "start": start,
                            "end": start + timedelta(minutes=length),
                            "service": rng.choice(SERVICES),
                            "provider": rng.choice(PROVIDERS),
                            "client": f"{rng.choice(FIRST)} {chr(65 + rng.randrange(26))}.",
                            "booked_by": rng.choice(["Staff", "Self-booked", "Partner"]),
                        }
                    )
                hour += 1
    return out


def event_stats() -> dict:
    now = timezone.localtime()
    rng = random.Random(now.date().toordinal())
    slots = []
    for i in range(16):
        start = datetime.combine(now.date(), time(9, 0)) + timedelta(minutes=30 * i)
        cap = 40
        booked = min(cap, rng.randint(24, 44))
        checked = (
            booked
            if start.time() < now.time()
            else max(0, booked - rng.randint(5, 20))
            if start.time() < (now + timedelta(minutes=30)).time()
            else 0
        )
        slots.append({"start": start, "capacity": cap, "booked": booked, "checked_in": checked})
    return {
        "name": "Flu Vaccination Clinic — Prince Frederick",
        "location": "Calvert County Fairgrounds, Exhibit Hall",
        "date": now.date(),
        "slots": slots,
        "capacity": sum(s["capacity"] for s in slots),
        "booked": sum(s["booked"] for s in slots),
        "checked_in": sum(s["checked_in"] for s in slots),
        "waitlist": rng.randint(18, 40),
    }


SEGMENTS = [
    ("all_partners", "All community partners", 10),
    ("program_mch", "Clients in Maternal & Child Health", 86),
    ("program_imm", "Clients in Immunizations", 142),
    ("zip_20678", "Clients in ZIP 20678 (Prince Frederick)", 61),
    ("zip_20657", "Clients in ZIP 20657 (Lusby)", 54),
]

EHR_MAPPING = [
    ("First name", "PID-5.2 Patient Name (given)", "Patient.name.given", "Two-way"),
    ("Last name", "PID-5.1 Patient Name (family)", "Patient.name.family", "Two-way"),
    ("Date of birth", "PID-7 Date of Birth", "Patient.birthDate", "Two-way"),
    ("Sex", "PID-8 Administrative Sex", "Patient.gender", "EHR → Health Depot"),
    ("Phone", "PID-13 Phone (home)", "Patient.telecom[phone]", "Two-way"),
    ("Address / ZIP", "PID-11 Patient Address", "Patient.address", "Two-way"),
    (
        "Preferred language",
        "PID-15 Primary Language",
        "Patient.communication.language",
        "EHR → Health Depot",
    ),
    (
        "Race / ethnicity",
        "PID-10 / PID-22",
        "US Core race & ethnicity extensions",
        "EHR → Health Depot",
    ),
    (
        "Referral status",
        "ORU / REF^I12 referral message",
        "ServiceRequest.status",
        "Health Depot → EHR",
    ),
    ("Referral outcome", "OBX outcome note", "Task.output / Observation", "Health Depot → EHR"),
]


def ehr_log() -> list[dict]:
    now = timezone.now()
    rng = random.Random(now.date().toordinal())
    events = [
        "Demographics updated (ADT^A08)",
        "New patient registered (ADT^A04)",
        "Referral status sent (ServiceRequest)",
        "Referral outcome sent (Task)",
        "Patient matched to existing client",
    ]
    rows = []
    for i in range(14):
        ok = rng.random() > 0.08
        rows.append(
            {
                "at": now - timedelta(minutes=17 * i + rng.randint(0, 9)),
                "event": rng.choice(events),
                "ok": ok,
                "detail": "OK" if ok else "Retried: EHR timeout after 30s",
            }
        )
    return rows

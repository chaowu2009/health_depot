"""Create realistic SYNTHETIC demo data. Every person and organization here is fictional.

    python manage.py seed_demo            # add demo data (only if none exists)
    python manage.py seed_demo --reset    # wipe operational data and reseed

Demo logins are documented in DEMO_SCRIPT.md. All demo accounts share one password and one
authenticator secret so a presenter can switch roles quickly.
"""

import random
from datetime import date, timedelta

from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.accounts.models import User, UserProgramAccess
from apps.audit.models import AuditLog
from apps.audit.signals import suppress_audit
from apps.cases.models import CarePlanGoal, Case, CaseDocument, CaseNote, CaseTask
from apps.clients.models import Client, ClientProgram
from apps.core.models import SavedView
from apps.forms_builder.dynamic import answers_snapshot, derive_needs
from apps.forms_builder.models import FormTemplate
from apps.messaging.models import Message, MessageReceipt, MessageThread
from apps.notifications.models import EmailOutbox, Notification
from apps.organizations.models import Division, Organization, PartnerProgram, Program
from apps.referrals.models import Referral, ReferralComment, ReferralEvent, ReferralLink
from apps.referrals.services import new_reference_number

DEMO_DOMAIN = "demo.healthdepot.local"
DEMO_PASSWORD = "HealthDepot-Demo-2026!"  # nosec B105 - documented demo-only credential
DEMO_TOTP_SECRET = "HEALTHDEPOTDEMOKEYCALVERTCOUNTYM"  # nosec B105 - demo-only, documented

TOWNS = [  # (town, ZIP, weight)
    ("Prince Frederick", "20678", 20),
    ("Lusby", "20657", 18),
    ("Huntingtown", "20639", 11),
    ("Chesapeake Beach", "20732", 10),
    ("North Beach", "20714", 6),
    ("Owings", "20736", 9),
    ("Dunkirk", "20754", 7),
    ("St. Leonard", "20685", 7),
    ("Solomons", "20688", 5),
    ("Port Republic", "20676", 4),
    ("Sunderland", "20689", 3),
]
DIVISIONS = [("CH", "Community Health"), ("CS", "Clinical Services"), ("BH", "Behavioral Health")]
PROGRAMS = [  # code, name, division, overdue days
    ("MCH", "Maternal & Child Health", "CS", 3),
    ("CDP", "Chronic Disease Prevention", "CH", 5),
    ("BHO", "Behavioral Health Outreach", "BH", 2),
    ("IMM", "Immunizations", "CS", 3),
    ("CHW", "Community Health Workers", "CH", 3),
]
PARTNERS = [  # name, town index, services, programs, color
    ("Chesapeake Community Food Bank", 0, ["FOOD"], ["CHW", "MCH", "CDP"], "#B45309"),
    ("Lusby Neighbors Pantry", 1, ["FOOD"], ["CHW", "MCH"], "#15803D"),
    ("Bayside Housing Partners", 0, ["HOUSING", "UTILITIES"], ["CHW", "BHO"], "#1D4ED8"),
    (
        "Southern Calvert Family Center",
        1,
        ["OTHER", "BEHAVIORAL_HEALTH"],
        ["MCH", "BHO"],
        "#7C3AED",
    ),
    ("Twin Beaches Transit Helpers", 3, ["TRANSPORTATION"], ["CHW", "CDP", "IMM"], "#0E7490"),
    ("Huntingtown Faith & Service Network", 2, ["FOOD", "OTHER"], ["CHW", "CDP"], "#9F1239"),
    ("Patuxent Recovery Alliance", 7, ["BEHAVIORAL_HEALTH"], ["BHO"], "#4D7C0F"),
    ("Solomons Island Senior Circle", 8, ["OTHER", "TRANSPORTATION"], ["CDP", "IMM"], "#C2410C"),
    ("Dunkirk Community Health Clinic", 6, ["MEDICAL"], ["CDP", "IMM", "MCH"], "#0F766E"),
    ("Calvert Energy Assistance Collaborative", 0, ["UTILITIES"], ["CHW"], "#A16207"),
]
NEED_TO_SERVICE = {
    "FOOD": "FOOD",
    "HOUSING": "HOUSING",
    "TRANSPORTATION": "TRANSPORTATION",
    "UTILITIES": "UTILITIES",
}
MESSAGES_FROM_CCHD = [
    "Thanks for the referral — we've reached the client and scheduled a visit.",
    "Could you confirm the best phone number for this client?",
    "Our community health worker will follow up this week.",
    "We left a voicemail. Does the client prefer text messages?",
]
MESSAGES_FROM_PARTNER = [
    "The client picked up a food box today and will come back next week.",
    "We have an opening on Thursday at 10am — does that work for the client?",
    "Client asked about transportation to the appointment. Can you help?",
    "Thanks! We'll let you know once services are delivered.",
]
COMMENTS = [
    "Client may also qualify for WIC — check at next contact.",
    "Spanish-speaking CHW requested for follow-up.",
    "Second attempt to reach client today; will try again tomorrow.",
    "Discussed with supervisor; prioritize this week.",
]
GOALS = [
    "Secure stable housing",
    "Enroll in SNAP benefits",
    "Attend prenatal appointments",
    "Reduce A1c below 7%",
    "Complete childhood immunizations",
    "Connect with counseling",
    "Arrange transportation to dialysis",
    "Apply for energy assistance",
]
TASKS = [
    "Call client to check in",
    "Help complete benefits application",
    "Schedule home visit",
    "Request records from clinic",
    "Confirm transportation booking",
    "Follow up with partner on outcome",
]
NOTES = [
    "Spoke with client by phone; needs are unchanged.",
    "Home visit completed. Client is doing well and engaged.",
    "Client missed appointment; rescheduled for next week.",
    "Connected client with food pantry hours and location.",
]

STAFF_USERS = [  # email, first, last, role, title, programs, level
    ("admin", "Avery", "Morgan", "SYSTEM_ADMIN", "System administrator", "ALL", "EDIT"),
    (
        "manager",
        "Dana",
        "Whitfield",
        "PROGRAM_MANAGER",
        "Community Health Program Manager",
        "ALL",
        "EDIT",
    ),
    ("staff", "Jordan", "Rivera", "STAFF", "Community Health Worker", ["CHW", "MCH"], "EDIT"),
    ("leader", "Dr. Patricia", "Hale", "READ_ONLY", "Health Officer", "ALL", "READ_ONLY"),
    ("nurse.okafor", "Grace", "Okafor", "STAFF", "Public Health Nurse", ["MCH", "IMM"], "EDIT"),
    ("chw.romero", "Luis", "Romero", "STAFF", "Community Health Worker", ["CHW", "CDP"], "EDIT"),
    ("bh.lindqvist", "Erik", "Lindqvist", "STAFF", "Behavioral Health Specialist", ["BHO"], "EDIT"),
    (
        "pm.chen",
        "Mei",
        "Chen",
        "PROGRAM_MANAGER",
        "Clinical Services Manager",
        ["MCH", "IMM"],
        "EDIT",
    ),
    ("staff.brennan", "Kelly", "Brennan", "STAFF", "Health Educator", ["CDP"], "EDIT"),
    ("staff.patel", "Anil", "Patel", "STAFF", "Immunization Coordinator", ["IMM"], "EDIT"),
    ("intern.james", "Taylor", "James", "STAFF", "Public Health Intern", ["CHW"], "READ_ONLY"),
    ("chw.nguyen", "Linh", "Nguyen", "STAFF", "Community Health Worker", ["CHW", "MCH"], "EDIT"),
    ("nurse.ali", "Sara", "Ali", "STAFF", "Public Health Nurse", ["IMM", "CDP"], "EDIT"),
    ("bh.kowalski", "Adam", "Kowalski", "STAFF", "Peer Recovery Specialist", ["BHO"], "EDIT"),
    (
        "pm.robinson",
        "Monique",
        "Robinson",
        "PROGRAM_MANAGER",
        "Behavioral Health Manager",
        ["BHO", "CHW"],
        "EDIT",
    ),
]


class Command(BaseCommand):
    help = "Create realistic synthetic demo data (fictional people and organizations only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete existing operational data first."
        )
        parser.add_argument("--seed", type=int, default=2026)
        parser.add_argument("--clients", type=int, default=300)
        parser.add_argument("--referrals", type=int, default=800)

    def handle(self, *args, **opts):
        if not settings.DEMO_MODE:
            raise CommandError("Demo data can only be loaded when DEMO_MODE=true.")
        self.rng = random.Random(opts["seed"])
        self.fake = Faker("en_US")
        Faker.seed(opts["seed"])
        self.now = timezone.now()
        call_command("bootstrap", verbosity=0)
        with suppress_audit(), transaction.atomic():
            if not opts["reset"] and Referral.objects.exists():
                self.stdout.write("Demo data already present. Use --reset to rebuild it.")
                return
            self.reset()  # also clears half-made setup data on a fresh database
            self.build(opts["clients"], opts["referrals"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {Client.objects.count()} clients, {Referral.objects.count()} "
                f"referrals, {Case.objects.count()} cases, {User.objects.filter(email__endswith=DEMO_DOMAIN).count()} demo users."
            )
        )
        self.stdout.write(
            f"Demo password: {DEMO_PASSWORD}   Authenticator secret: {DEMO_TOTP_SECRET}"
        )

    # ------------------------------------------------------------------------------------
    def reset(self):
        MessageReceipt.objects.all().delete()
        Message.objects.all().delete()
        MessageThread.objects.all().delete()
        ReferralComment.objects.all().delete()
        ReferralEvent.objects.all().delete()
        Referral.objects.all().delete()
        for doc in CaseDocument.objects.all():
            doc.file.delete(save=False)
        CaseDocument.objects.all().delete()
        for model in (CaseTask, CaseNote, CarePlanGoal):
            model.objects.all().delete()
        Case.objects.all().delete()
        ClientProgram.objects.all().delete()
        Client.objects.update(possible_duplicate_of=None)
        Client.objects.all().delete()
        Notification.objects.all().delete()
        EmailOutbox.objects.all().delete()
        SavedView.objects.all().delete()
        AuditLog.objects.all().delete()  # demo environment only
        ReferralLink.objects.all().delete()
        demo_users = User.objects.filter(email__endswith=DEMO_DOMAIN)
        Authenticator.objects.filter(user__in=demo_users).delete()
        UserProgramAccess.objects.all().delete()
        demo_users.delete()
        PartnerProgram.objects.all().delete()
        User.objects.filter(organization__org_type="COMMUNITY_PARTNER").update(organization=None)
        Organization.objects.filter(org_type=Organization.OrgType.COMMUNITY_PARTNER).delete()
        FormTemplate.objects.filter(is_system_template=False).delete()
        Program.objects.all().delete()
        Division.objects.all().delete()

    # ------------------------------------------------------------------------------------
    def build(self, n_clients: int, n_referrals: int):
        rng = self.rng
        cchd = Organization.objects.get(slug="cchd")
        cchd.contact_name, cchd.contact_phone = "Community Health Division", "410-555-0100"
        cchd.address = "975 Solomons Island Rd N, Prince Frederick, MD 20678 (demo)"
        cchd.save()
        divisions = {
            code: Division.objects.create(organization=cchd, code=code, name=name)
            for code, name in DIVISIONS
        }
        programs = {
            code: Program.objects.create(
                code=code,
                name=name,
                division=divisions[div],
                overdue_after_days=days,
                description=f"{name} program (demo).",
            )
            for code, name, div, days in PROGRAMS
        }
        templates = {t.name: t for t in FormTemplate.objects.filter(is_system_template=True)}

        # Partners + links
        partners = []
        for i, (name, town_idx, services, progs, color) in enumerate(PARTNERS):
            town, zip_code, _ = TOWNS[town_idx]
            contact = self.fake.name()
            org = Organization.objects.create(
                name=f"{name} (fictional)",
                slug=f"demo-partner-{i + 1}",
                org_type=Organization.OrgType.COMMUNITY_PARTNER,
                brand_color=color,
                contact_name=contact,
                contact_email=f"contact{i + 1}@partner.{DEMO_DOMAIN}",
                contact_phone=f"410-555-{1100 + i * 7:04d}",
                address=f"{rng.randint(100, 9999)} Main St, {town}, MD {zip_code}",
                service_types=services,
                service_area_zips=sorted({zip_code, *[t[1] for t in rng.sample(TOWNS, 2)]}),
            )
            for code in progs:
                PartnerProgram.objects.create(partner=org, program=programs[code])
            org._programs = [programs[c] for c in progs]  # type: ignore[attr-defined]
            org._links = []  # type: ignore[attr-defined]
            for j, label in enumerate(["Front desk", "Outreach events"][: 1 + (i % 2)]):
                tpl = templates["SDoH Screening"] if j == 0 else templates["General Intake"]
                org._links.append(
                    ReferralLink.objects.create(  # type: ignore[attr-defined]
                        partner=org, program=programs[progs[0]], form_template=tpl, label=label
                    )
                )
            partners.append(org)
        self.partners = partners

        # Users
        users = self._users(cchd, programs, partners)
        staff_by_program = {
            code: [
                u
                for u in users["staff"]
                if u.program_access.filter(program=p, access_level="EDIT").exists()
            ]
            for code, p in programs.items()
        }

        # Clients
        clients = []
        weights = [t[2] for t in TOWNS]
        for _ in range(n_clients):
            town, zip_code, _ = rng.choices(TOWNS, weights=weights)[0]
            spanish = rng.random() < 0.07
            age = rng.choices(
                [
                    rng.randint(0, 17),
                    rng.randint(18, 24),
                    rng.randint(25, 44),
                    rng.randint(45, 64),
                    rng.randint(65, 92),
                ],
                weights=[14, 10, 34, 26, 16],
            )[0]
            dob = (self.now - timedelta(days=age * 365 + rng.randint(0, 364))).date()
            sex = rng.choice(["F", "F", "M", "M", "U"]) if age > 0 else "U"
            first = self.fake.first_name_female() if sex == "F" else self.fake.first_name_male()
            race = rng.choices(
                [["WHITE"], ["BLACK"], ["ASIAN"], ["WHITE", "BLACK"], ["OTHER"], ["DECLINED"]],
                weights=[72, 14, 2, 4, 3, 5],
            )[0]
            clients.append(
                Client(
                    first_name=first,
                    last_name=self.fake.last_name(),
                    date_of_birth=dob,
                    sex=sex,
                    race=race,
                    ethnicity="HISPANIC"
                    if spanish or rng.random() < 0.03
                    else rng.choice(["NOT_HISPANIC"] * 9 + ["DECLINED"]),
                    preferred_language="Spanish"
                    if spanish
                    else rng.choices(["English", "Other"], weights=[97, 3])[0],
                    needs_interpreter=spanish and rng.random() < 0.6,
                    phone=f"410-555-{rng.randint(2000, 9999):04d}",
                    email=f"{first.lower()}.{rng.randint(10, 999)}@example.com"
                    if rng.random() < 0.55
                    else "",
                    address_line=f"{rng.randint(10, 9999)} {self.fake.street_name()}",
                    city=town,
                    zip_code=zip_code,
                    preferred_contact_method=rng.choice(["PHONE", "PHONE", "TEXT", "EMAIL"]),
                    consent_to_contact=True,
                    consent_to_share=rng.random() < 0.95,
                    consent_signed_at=self.now - timedelta(days=rng.randint(1, 200)),
                    consent_text_version="intake-v1",
                )
            )
        Client.objects.bulk_create(clients)
        # A few flagged possible duplicates for the review workflow.
        for c in rng.sample(clients, 4):
            dup = Client.objects.create(
                first_name=c.first_name[:3] + c.first_name[3:].lower(),
                last_name=c.last_name,
                date_of_birth=c.date_of_birth,
                zip_code=c.zip_code,
                phone="",
                preferred_language=c.preferred_language,
                possible_duplicate_of=c,
                consent_to_contact=True,
                consent_to_share=True,
            )
            clients.append(dup)

        # Referrals
        self._referrals(
            n_referrals, clients, programs, partners, cchd, templates, users, staff_by_program
        )
        self._cases(users)
        self._notifications(users)

    # ------------------------------------------------------------------------------------
    def _make_user(self, email_local, first, last, role, title, org):
        user = User.objects.create_user(
            email=f"{email_local}@{DEMO_DOMAIN}",
            password=DEMO_PASSWORD,
            first_name=first,
            last_name=last,
            role=role,
            title=title,
            organization=org,
            is_staff=role == "SYSTEM_ADMIN",
            is_superuser=False,
        )
        TOTP.activate(user, DEMO_TOTP_SECRET)
        return user

    def _users(self, cchd, programs, partners):
        out = {"staff": [], "partners": [], "by_key": {}}
        for local, first, last, role, title, progs, level in STAFF_USERS:
            u = self._make_user(local, first, last, role, title, cchd)
            codes = list(programs) if progs == "ALL" else progs
            if role != "SYSTEM_ADMIN":
                for code in codes:
                    UserProgramAccess.objects.create(
                        user=u, program=programs[code], access_level=level
                    )
            out["by_key"][local] = u
            if role in ("STAFF", "PROGRAM_MANAGER"):
                out["staff"].append(u)
        # Partner users: the demo "partner@" login works at the food bank.
        u = self._make_user(
            "partner", "Sam", "Okonkwo", "PARTNER_USER", "Pantry Coordinator", partners[0]
        )
        out["by_key"]["partner"] = u
        out["partners"].append(u)
        for i, org in enumerate(partners[1:], start=2):
            out["partners"].append(
                self._make_user(
                    f"partner{i}",
                    self.fake.first_name(),
                    self.fake.last_name(),
                    "PARTNER_USER",
                    "Program Coordinator",
                    org,
                )
            )
        partners[0]._demo_user = u  # type: ignore[attr-defined]
        for org, pu in zip(partners[1:], out["partners"][1:], strict=False):
            org._demo_user = pu  # type: ignore[attr-defined]
        return out

    # ------------------------------------------------------------------------------------
    def _sdoh_answers(self, template, need_bias):
        rng = self.rng
        values = {}
        for f in template.fields:
            key, kind = f["key"], f["type"]
            if f.get("show_if"):
                continue
            if kind == "yes_no":
                tag = f.get("need_tag")
                values[key] = "yes" if (tag in need_bias or rng.random() < 0.05) else "no"
            elif kind == "single_choice":
                values[key] = rng.choice(f["options"])["value"]
            elif kind == "multiple_choice":
                opts = [o["value"] for o in f["options"]]
                chosen = [o for o in opts if o in [n.lower() for n in need_bias]]
                values[key] = chosen or rng.sample(opts, 1)
            elif kind == "long_text" and rng.random() < 0.3:
                values[key] = rng.choice(
                    [
                        "Prefers afternoon calls.",
                        "Has two young children at home.",
                        "Recently lost job; needs help quickly.",
                    ]
                )
        if values.get("safety") == "yes":
            values["safety_now"] = "no"
        if "other" in (values.get("help_needed") or []):
            values["help_other"] = "Help paying for prescriptions"
        return values

    def _referrals(self, n, clients, programs, partners, cchd, templates, users, staff_by_program):
        rng = self.rng
        used_refs = set()
        referrals, events = [], []
        program_list = list(programs.values())
        for _ in range(n):
            client = rng.choice(clients)
            age_days = rng.triangular(0, 182, 40)
            submitted = self.now - timedelta(days=age_days, minutes=rng.randint(0, 600))
            inbound = rng.random() < 0.6
            partner = rng.choice(partners)
            program = (
                rng.choice(partner._programs) if rng.random() < 0.85 else rng.choice(program_list)
            )
            ref = new_reference_number()
            while ref in used_refs:
                ref = new_reference_number()
            used_refs.add(ref)
            needs_pool = list(NEED_TO_SERVICE)
            primary = next(
                (n for n, s in NEED_TO_SERVICE.items() if s in partner.service_types),
                rng.choice(needs_pool),
            )
            bias = {primary} | ({rng.choice(needs_pool)} if rng.random() < 0.35 else set())
            if rng.random() < 0.06:
                bias.add("SAFETY")
            if inbound:
                link = rng.choice(partner._links)
                answers_raw = self._sdoh_answers(link.form_template, bias)
                answers = answers_snapshot(link.form_template.fields, answers_raw)
                needs = derive_needs(link.form_template.fields, answers_raw) or [primary]
                sender, receiver, tpl, version = (
                    partner,
                    cchd,
                    link.form_template,
                    link.form_template.version,
                )
                urgent = answers_raw.get("urgency") == "today"
            else:
                link = None
                reason = rng.choice(
                    [
                        "Client screened positive for food insecurity at clinic visit.",
                        "Family needs help with housing costs after job loss.",
                        "Needs rides to weekly appointments.",
                        "Utility shut-off notice received; requesting energy assistance.",
                        "Client asked for support group information.",
                    ]
                )
                answers = [
                    {
                        "key": "reason",
                        "label": "Reason for referral",
                        "value": reason,
                        "raw": reason,
                    }
                ]
                needs = sorted(bias)
                sender, receiver, tpl, version = cchd, partner, None, None
                urgent = rng.random() < 0.05
            status, stamps, outcome, notes = self._timeline(submitted, age_days, program)
            assigned = None
            if receiver == cchd and staff_by_program.get(program.code) and rng.random() < 0.8:
                assigned = rng.choice(staff_by_program[program.code])
            r = Referral(
                reference_number=ref,
                client=client,
                program=program,
                direction="INBOUND" if inbound else "OUTBOUND",
                sending_organization=sender,
                receiving_organization=receiver,
                source_link=link,
                form_template=tpl,
                form_version=version,
                answers={"items": answers},
                needs=needs,
                status=status,
                priority="URGENT"
                if urgent
                else rng.choices(["LOW", "NORMAL", "HIGH"], weights=[10, 75, 15])[0],
                assigned_to=assigned,
                outcome=outcome,
                outcome_notes=notes if status in ("COMPLETED", "CLOSED_UNABLE_TO_CONTACT") else "",
                decline_reason=notes if status == "DECLINED" else "",
                created_by=users["by_key"]["staff"] if not inbound else None,
                **stamps,
            )
            r.created_at = submitted
            referrals.append(r)
        Referral.objects.bulk_create(referrals)
        for r in referrals:
            Referral.objects.filter(pk=r.pk).update(created_at=r.submitted_at)
            events.extend(self._events(r, users))
        ReferralEvent.objects.bulk_create(events)
        # Fix event timestamps (auto_now_add overrides on create).
        for e in events:
            ReferralEvent.objects.filter(pk=e.pk).update(created_at=e._at)
        # Link counters
        for p in partners:
            for link in p._links:
                subs = Referral.objects.filter(source_link=link).count()
                ReferralLink.objects.filter(pk=link.pk).update(
                    submission_count=subs, visit_count=subs + rng.randint(subs, subs * 2 + 10)
                )
        # Client ↔ program enrollment
        pairs = set(Referral.objects.values_list("client_id", "program_id"))
        ClientProgram.objects.bulk_create(
            [ClientProgram(client_id=c, program_id=p) for c, p in pairs], ignore_conflicts=True
        )
        self._messages_and_comments(referrals, users)

    def _timeline(self, submitted, age_days, program):
        """Pick a realistic status for a referral of this age, with consistent timestamps."""
        rng = self.rng
        stamps = {"submitted_at": submitted}
        t = submitted

        def step(hours_lo, hours_hi):
            nonlocal t
            t = t + timedelta(hours=rng.uniform(hours_lo, hours_hi))
            return min(t, self.now - timedelta(minutes=5))

        overdue_window = program.overdue_after_days
        if age_days < 2:
            choices, w = ["SUBMITTED", "RECEIVED", "ACCEPTED"], [55, 30, 15]
        elif age_days < 10:
            choices, w = (
                ["SUBMITTED", "RECEIVED", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "DECLINED"],
                [6, 10, 22, 30, 25, 7],
            )
        else:
            choices, w = (
                [
                    "SUBMITTED",
                    "RECEIVED",
                    "ACCEPTED",
                    "IN_PROGRESS",
                    "COMPLETED",
                    "DECLINED",
                    "CLOSED_UNABLE_TO_CONTACT",
                ],
                [1, 1, 3, 9, 66, 11, 9],
            )
        status = rng.choices(choices, weights=w)[0]
        outcome, notes = "", ""
        if status != "SUBMITTED":
            stamps["received_at"] = step(0.5, 30)
        if status in ("ACCEPTED", "IN_PROGRESS", "COMPLETED", "CLOSED_UNABLE_TO_CONTACT"):
            stamps["accepted_at"] = step(1, 48)
        if status in ("IN_PROGRESS", "COMPLETED"):
            stamps["in_progress_at"] = step(4, 96)
        if status == "COMPLETED":
            stamps["completed_at"] = step(24, 24 * 18)
            outcome = rng.choices(
                ["SERVICES_PROVIDED", "PARTIALLY_MET", "CLIENT_DECLINED", "REFERRED_ELSEWHERE"],
                weights=[75, 12, 6, 7],
            )[0]
            notes = rng.choice(
                [
                    "Services delivered; client satisfied.",
                    "Client enrolled and attending.",
                    "Need met with emergency assistance.",
                    "Connected with ongoing support.",
                ]
            )
        if status == "DECLINED":
            stamps["declined_at"] = step(1, 60)
            notes = rng.choice(
                [
                    "Outside our service area.",
                    "Program at capacity this month.",
                    "Client already receiving this service.",
                ]
            )
        if status == "CLOSED_UNABLE_TO_CONTACT":
            stamps["closed_at"] = step(48, 24 * 10)
            outcome, notes = "UNABLE_TO_CONTACT", "Three calls and a text over two weeks."
        last = max(v for v in stamps.values())
        # Make a share of open referrals overdue (and keep the rest fresh) for the demo.
        if status in ("SUBMITTED", "RECEIVED", "ACCEPTED", "IN_PROGRESS") and age_days > 2:
            if rng.random() < 0.55:
                last = max(last, self.now - timedelta(days=rng.uniform(0.2, overdue_window - 0.5)))
                key = {
                    "SUBMITTED": "submitted_at",
                    "RECEIVED": "received_at",
                    "ACCEPTED": "accepted_at",
                    "IN_PROGRESS": "in_progress_at",
                }[status]
                if status != "SUBMITTED":
                    stamps[key] = last
        stamps["last_status_change_at"] = last
        return status, stamps, outcome, notes

    def _events(self, r, users):
        order = [
            ("SUBMITTED", "submitted_at"),
            ("RECEIVED", "received_at"),
            ("ACCEPTED", "accepted_at"),
            ("DECLINED", "declined_at"),
            ("IN_PROGRESS", "in_progress_at"),
            ("COMPLETED", "completed_at"),
            ("CLOSED_UNABLE_TO_CONTACT", "closed_at"),
        ]
        events, prev = [], ""
        receiver_actor = (
            r.assigned_to
            if r.receiving_organization.org_type == "HEALTH_DEPARTMENT"
            else getattr(r.receiving_organization, "_demo_user", None)
        )
        sender_actor = None if r.direction == "INBOUND" else users["by_key"]["staff"]
        for status, field in order:
            at = getattr(r, field)
            if not at:
                continue
            is_submit = status == "SUBMITTED"
            note = ""
            if is_submit:
                note = (
                    f"Submitted through referral link “{r.source_link.label}”."
                    if r.source_link
                    else "Referral sent to partner."
                )
            elif status == "DECLINED":
                note = r.decline_reason
            elif status in ("COMPLETED", "CLOSED_UNABLE_TO_CONTACT"):
                note = r.outcome_notes
            e = ReferralEvent(
                referral=r,
                event_type="STATUS_CHANGE",
                from_status=prev,
                to_status=status,
                actor=sender_actor if is_submit else receiver_actor,
                actor_organization=r.sending_organization
                if is_submit
                else r.receiving_organization,
                note=note,
            )
            e._at = at
            events.append(e)
            if not is_submit:
                n = ReferralEvent(
                    referral=r,
                    event_type="NOTIFIED",
                    note=f"{r.sending_organization} and {r.receiving_organization} notified.",
                )
                n._at = at + timedelta(seconds=2)
                events.append(n)
            prev = status
        return events

    def _messages_and_comments(self, referrals, users):
        rng = self.rng
        threads, msgs, comments = [], [], []
        cchd_people = users["staff"]
        for r in rng.sample(referrals, k=len(referrals) // 4):
            partner = (
                r.sending_organization if r.direction == "INBOUND" else r.receiving_organization
            )
            partner_user = getattr(partner, "_demo_user", None)
            cchd_user = r.assigned_to or rng.choice(cchd_people)
            if partner_user is None:
                continue
            thread = MessageThread.objects.create(referral=r)
            thread.participant_organizations.set([r.sending_organization, r.receiving_organization])
            t = (r.received_at or r.submitted_at) + timedelta(hours=1)
            for i in range(rng.randint(1, 4)):
                from_partner = (i % 2 == 0) == (r.direction == "INBOUND")
                body = rng.choice(MESSAGES_FROM_PARTNER if from_partner else MESSAGES_FROM_CCHD)
                m = Message(
                    thread=thread, sender=partner_user if from_partner else cchd_user, body=body
                )
                m._at = min(
                    t + timedelta(hours=rng.uniform(1, 30) * (i + 1)),
                    self.now - timedelta(minutes=10),
                )
                msgs.append(m)
            threads.append(thread)
        Message.objects.bulk_create(msgs)
        for m in msgs:
            Message.objects.filter(pk=m.pk).update(created_at=m._at)
            MessageReceipt.objects.get_or_create(message=m, user=m.sender)
        for r in rng.sample(referrals, k=len(referrals) // 10):
            if (
                r.receiving_organization.org_type != "HEALTH_DEPARTMENT"
                and r.sending_organization.org_type != "HEALTH_DEPARTMENT"
            ):
                continue
            comments.append(
                ReferralComment(
                    referral=r, author=rng.choice(cchd_people), body=rng.choice(COMMENTS)
                )
            )
        ReferralComment.objects.bulk_create(comments)

    def _cases(self, users):
        rng = self.rng
        candidates = list(
            Referral.objects.filter(
                receiving_organization__org_type="HEALTH_DEPARTMENT",
                status__in=["ACCEPTED", "IN_PROGRESS", "COMPLETED"],
            ).select_related("client", "program", "assigned_to")
        )
        rng.shuffle(candidates)
        staff = users["staff"]
        seen_clients = set()
        made = 0
        for r in candidates:
            if made >= 90 or r.client_id in seen_clients:
                continue
            seen_clients.add(r.client_id)
            admitted = r.accepted_at or r.submitted_at
            manager = r.assigned_to or rng.choice(staff)
            discharged = r.status == "COMPLETED" and rng.random() < 0.55
            case = Case.objects.create(
                case_number=f"CASE-{admitted.year}-{rng.randint(10000, 99999)}",
                client=r.client,
                program=r.program,
                case_manager=manager,
                status="DISCHARGED"
                if discharged
                else rng.choice(["OPEN", "ACTIVE", "ACTIVE", "ON_HOLD"]),
                admitted_at=admitted,
                discharged_at=(r.completed_at or self.now) if discharged else None,
                discharge_reason="GOALS_MET" if discharged else "",
                discharge_outcome=rng.choice(["IMPROVED", "STABLE"]) if discharged else "",
            )
            Referral.objects.filter(pk=r.pk).update(case=case)
            for g in rng.sample(GOALS, rng.randint(1, 3)):
                CarePlanGoal.objects.create(
                    case=case,
                    description=g,
                    target_date=(admitted + timedelta(days=rng.randint(30, 120))).date(),
                    status="MET" if discharged else rng.choice(["NOT_STARTED", "IN_PROGRESS"]),
                )
            for title in rng.sample(TASKS, rng.randint(1, 3)):
                done = discharged or rng.random() < 0.4
                due = (self.now + timedelta(days=rng.randint(-6, 14))).date()
                CaseTask.objects.create(
                    case=case,
                    title=title,
                    assigned_to=manager,
                    due_date=due,
                    completed_at=self.now if done else None,
                    priority=rng.choice(["NORMAL", "NORMAL", "HIGH"]),
                )
            for body in rng.sample(NOTES, rng.randint(1, 3)):
                CaseNote.objects.create(
                    case=case,
                    author=manager,
                    body=body,
                    note_type=rng.choice(["PHONE", "VISIT", "CONTACT"]),
                    contact_date=(admitted + timedelta(days=rng.randint(0, 20))).date(),
                )
            made += 1
        # Make sure the demo staff user has a busy "My work" page.
        jordan = users["by_key"]["staff"]
        for case in Case.objects.filter(case_manager=jordan).exclude(status="DISCHARGED")[:3]:
            CaseTask.objects.create(
                case=case,
                title="Check in after referral",
                assigned_to=jordan,
                due_date=date.today(),
            )

    def _notifications(self, users):
        rng = self.rng
        jordan, partner = users["by_key"]["staff"], users["by_key"]["partner"]
        for user, refs in (
            (jordan, Referral.objects.filter(assigned_to=jordan)),
            (partner, Referral.objects.filter(receiving_organization=partner.organization)),
        ):
            for r in list(refs.order_by("-submitted_at")[:6]):
                Notification.objects.create(
                    recipient=user,
                    verb="REFERRAL_STATUS",
                    target_type="Referral",
                    target_id=str(r.pk),
                    url=f"/referrals/{r.pk}/",
                    message=f"Referral {r.reference_number} was updated.",
                    read_at=None if rng.random() < 0.6 else self.now,
                )

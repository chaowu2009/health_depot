"""Left-navigation definition for the app shell (single source of truth)."""

from dataclasses import dataclass

STAFF = ("SYSTEM_ADMIN", "PROGRAM_MANAGER", "STAFF", "READ_ONLY")
EVERYONE = (*STAFF, "PARTNER_USER")


@dataclass(frozen=True)
class NavItem:
    slug: str
    label: str
    icon: str  # name of an inline SVG in templates/partials/icon.html
    coming_in: str  # build step that delivered / delivers the page
    description: str
    roles: tuple[str, ...] = STAFF
    partner_label: str = ""  # label shown to partner users, if different


MAIN_NAV: tuple[NavItem, ...] = (
    NavItem(
        "dashboard",
        "Dashboard",
        "chart",
        "Prompt 7",
        "Referral volume, closed-loop completion, demographics and partner performance.",
        roles=EVERYONE,
    ),
    NavItem(
        "referrals",
        "Referrals",
        "inbox",
        "Prompts 4–5",
        "Inbox of incoming and outgoing referrals with the closed-loop status timeline.",
        roles=EVERYONE,
    ),
    NavItem("clients", "Clients", "users", "Prompt 6", "Client profiles."),
    NavItem("cases", "Cases", "folder", "Prompt 6", "Case management from admission to discharge."),
    NavItem(
        "my-work",
        "My work",
        "clipboard",
        "Prompt 6",
        "My open tasks, overdue referrals and active cases.",
    ),
    NavItem(
        "partners",
        "Partners",
        "link",
        "Prompt 3",
        "Community partner organizations and their trackable referral links.",
        roles=EVERYONE,
        partner_label="My organization",
    ),
    NavItem(
        "forms",
        "Forms",
        "clipboard",
        "Prompt 3",
        "Build intake and SDoH screening forms for each partner and program.",
    ),
    NavItem(
        "messages",
        "Messages",
        "chat",
        "Prompt 5",
        "Secure messages between CCHD staff and community partners.",
        roles=EVERYONE,
    ),
    NavItem("reports", "Reports", "table", "Prompt 7", "Custom reports with CSV and Excel export."),
)

PHASE2_NAV: tuple[NavItem, ...] = (
    NavItem(
        "scheduling",
        "Scheduling",
        "calendar",
        "Prompt 8",
        "Multi-clinic calendars and public self-booking.",
    ),
    NavItem(
        "events",
        "Mass events",
        "megaphone",
        "Prompt 8",
        "Mass vaccination and resource distribution events.",
    ),
    NavItem(
        "communications",
        "Communications",
        "mail",
        "Prompt 8",
        "Mass email/SMS to partners and clients.",
    ),
    NavItem(
        "ehr",
        "EHR integration",
        "link",
        "Prompt 8",
        "HL7/FHIR connection, field mapping and sync log.",
    ),
    NavItem(
        "import",
        "Spreadsheet import",
        "upload",
        "Prompt 8",
        "Import clients from existing spreadsheets.",
    ),
)

ALL_NAV = {item.slug: item for item in (*MAIN_NAV, *PHASE2_NAV)}
PHASE2_SLUGS = {item.slug for item in PHASE2_NAV}


def nav_for(user) -> tuple[list[dict], list[dict]]:
    role = "SYSTEM_ADMIN" if getattr(user, "is_superuser", False) else getattr(user, "role", "")
    is_partner = role == "PARTNER_USER"

    def build(items):
        return [
            {
                "slug": i.slug,
                "icon": i.icon,
                "label": i.partner_label if is_partner and i.partner_label else i.label,
            }
            for i in items
            if role in i.roles
        ]

    return build(MAIN_NAV), build(PHASE2_NAV)

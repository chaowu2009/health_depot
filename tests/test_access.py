"""Program scoping: who can see and edit which records (RFP 3.7, 3.9)."""

import pytest
from django.utils import timezone

from apps.accounts.access import can_edit_program
from apps.accounts.models import User, UserProgramAccess
from apps.cases.models import Case, CaseNote
from apps.clients.models import Client
from apps.referrals.models import Referral, ReferralComment
from tests.conftest import enroll_mfa
from tests.factories import (
    ClientFactory,
    DivisionFactory,
    OrganizationFactory,
    ProgramFactory,
    ReferralFactory,
    UserFactory,
)


@pytest.fixture
def world(db):
    division = DivisionFactory()
    program_a = ProgramFactory(division=division, name="Program A")
    program_b = ProgramFactory(division=division, name="Program B")
    partner_1 = OrganizationFactory(name="Fictional Food Pantry")
    partner_2 = OrganizationFactory(name="Fictional Housing Group")
    ref_a = ReferralFactory(program=program_a, sending_organization=partner_1)
    ref_b = ReferralFactory(program=program_b, sending_organization=partner_2)
    case_b = Case.objects.create(
        case_number="CASE-B", client=ref_b.client, program=program_b, admitted_at=timezone.now()
    )
    author = UserFactory(role=User.Role.SYSTEM_ADMIN)
    note_b = CaseNote.objects.create(case=case_b, author=author, body="Synthetic note")
    comment_a = ReferralComment.objects.create(referral=ref_a, author=author, body="Internal")

    def user(role, programs=(), level=UserProgramAccess.AccessLevel.EDIT, org=None, **kw):
        u = UserFactory(role=role, organization=org or division.organization, **kw)
        for p in programs:
            UserProgramAccess.objects.create(user=u, program=p, access_level=level)
        return u

    return {
        "A": program_a,
        "B": program_b,
        "p1": partner_1,
        "p2": partner_2,
        "ref_a": ref_a,
        "ref_b": ref_b,
        "case_b": case_b,
        "note_b": note_b,
        "comment_a": comment_a,
        "user": user,
    }


def test_staff_in_program_a_cannot_read_program_b(world):
    staff = world["user"](User.Role.STAFF, [world["A"]])
    assert list(Referral.objects.for_user(staff)) == [world["ref_a"]]
    assert list(Client.objects.for_user(staff)) == [world["ref_a"].client]
    assert not Case.objects.for_user(staff).exists()
    assert not CaseNote.objects.for_user(staff).exists()


def test_staff_in_program_b_sees_case_and_notes(world):
    staff = world["user"](User.Role.STAFF, [world["B"]])
    assert list(Case.objects.for_user(staff)) == [world["case_b"]]
    assert list(CaseNote.objects.for_user(staff)) == [world["note_b"]]


def test_partner_sees_only_own_organizations_referrals(world):
    partner = world["user"](User.Role.PARTNER_USER, org=world["p1"])
    assert list(Referral.objects.for_user(partner)) == [world["ref_a"]]
    assert list(Client.objects.for_user(partner)) == [world["ref_a"].client]


def test_partner_never_sees_cases_notes_or_internal_comments(world):
    partner = world["user"](User.Role.PARTNER_USER, org=world["p2"])
    assert not Case.objects.for_user(partner).exists()
    assert not CaseNote.objects.for_user(partner).exists()
    assert not ReferralComment.objects.for_user(partner).exists()


def test_partner_cannot_edit_client_records(world):
    partner = world["user"](User.Role.PARTNER_USER, org=world["p1"])
    assert not Client.objects.editable_by(partner).exists()


def test_read_only_role_can_read_but_never_edit(world):
    leader = world["user"](User.Role.READ_ONLY, [world["A"], world["B"]])
    assert Referral.objects.for_user(leader).count() == 2
    assert not Referral.objects.editable_by(leader).exists()
    assert not can_edit_program(leader, world["A"].pk)


def test_read_only_access_level_blocks_editing_in_that_program(world):
    staff = world["user"](
        User.Role.STAFF, [world["A"]], level=UserProgramAccess.AccessLevel.READ_ONLY
    )
    assert Referral.objects.for_user(staff).exists()
    assert not Referral.objects.editable_by(staff).exists()


def test_system_admin_sees_everything(world):
    admin = world["user"](User.Role.SYSTEM_ADMIN)
    assert Referral.objects.for_user(admin).count() == 2
    assert Case.objects.editable_by(admin).count() == 1


def test_inactive_and_anonymous_users_see_nothing(world):
    from django.contrib.auth.models import AnonymousUser

    gone = world["user"](User.Role.STAFF, [world["A"]], is_active=False)
    assert not Referral.objects.for_user(gone).exists()
    assert not Referral.objects.for_user(AnonymousUser()).exists()


def test_partner_without_organization_sees_nothing(world):
    orphan = UserFactory(role=User.Role.PARTNER_USER, organization=None)
    assert not Referral.objects.for_user(orphan).exists()


def test_client_in_both_programs_appears_once(world):
    staff = world["user"](User.Role.STAFF, [world["A"]])
    client = world["ref_a"].client
    ReferralFactory(program=world["A"], client=client)
    assert list(Client.objects.for_user(staff)) == [client]


# --- Through the web: out-of-scope IDs return 404 ------------------------------------------
@pytest.mark.parametrize("who", ["staff_a", "partner_2"])
def test_referral_page_returns_404_outside_scope(client, world, who):
    if who == "staff_a":
        user = world["user"](User.Role.STAFF, [world["A"]])
        target = world["ref_b"]
    else:
        user = world["user"](User.Role.PARTNER_USER, org=world["p2"])
        target = world["ref_a"]
    enroll_mfa(user)
    client.force_login(user)
    assert client.get(f"/referrals/{target.pk}/", secure=True).status_code == 404


def test_referral_page_in_scope_is_shown_and_audited(client, world):
    from apps.audit.models import AuditLog

    user = world["user"](User.Role.STAFF, [world["A"]])
    enroll_mfa(user)
    client.force_login(user)
    resp = client.get(f"/referrals/{world['ref_a'].pk}/", secure=True)
    assert resp.status_code == 200
    entry = AuditLog.objects.filter(action="READ", entity_type="Referral").latest("occurred_at")
    assert entry.actor == user and entry.entity_id == str(world["ref_a"].pk)
    assert entry.program_id == world["A"].pk


def test_client_without_any_program_link_is_invisible_to_staff(world):
    staff = world["user"](User.Role.STAFF, [world["A"]])
    orphan = ClientFactory()
    assert orphan not in Client.objects.for_user(staff)

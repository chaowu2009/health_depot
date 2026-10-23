"""Who gets told about what. Both sides of the loop are always informed."""

from django.db.models import Q
from django.urls import reverse

from apps.accounts.models import User
from apps.notifications.services import notify


def _url(referral) -> str:
    return reverse("referral-detail", args=[referral.pk])


def side_users(referral, org):
    """People at one side (organization) of a referral."""
    if org.org_type == "HEALTH_DEPARTMENT":
        if referral.assigned_to_id:
            return User.objects.filter(
                Q(pk=referral.assigned_to_id)
                | Q(role=User.Role.PROGRAM_MANAGER, program_access__program=referral.program),
                is_active=True,
            ).distinct()
        return User.objects.filter(
            role__in=[User.Role.PROGRAM_MANAGER, User.Role.STAFF],
            program_access__program=referral.program,
            is_active=True,
            program_access__access_level="EDIT",
        ).distinct()
    return User.objects.filter(role=User.Role.PARTNER_USER, organization=org, is_active=True)


def notify_new_referral(referral) -> None:
    notify(
        side_users(referral, referral.receiving_organization),
        verb="REFERRAL_NEW",
        message=f"New referral {referral.reference_number} from {referral.sending_organization}.",
        url=_url(referral),
        target=referral,
    )


def notify_status(referral, actor, label: str) -> None:
    """Closed loop: tell the other side (and anyone assigned) about the change."""
    recipients = [
        *side_users(referral, referral.sending_organization),
        *side_users(referral, referral.receiving_organization),
    ]
    notify(
        recipients,
        verb="REFERRAL_STATUS",
        message=f"Referral {referral.reference_number}: {label} by "
        f"{actor.organization if actor and actor.organization else 'staff'}.",
        url=_url(referral),
        target=referral,
        exclude=actor,
    )


def notify_assigned(referral, assignee, actor) -> None:
    notify(
        [assignee],
        verb="REFERRAL_ASSIGNED",
        message=f"Referral {referral.reference_number} was assigned to you.",
        url=_url(referral),
        target=referral,
        exclude=actor,
    )


def notify_message(referral, sender) -> None:
    recipients = [
        *side_users(referral, referral.sending_organization),
        *side_users(referral, referral.receiving_organization),
    ]
    notify(
        recipients,
        verb="REFERRAL_MESSAGE",
        message=f"New secure message on referral {referral.reference_number}.",
        url=_url(referral) + "#messages",
        target=referral,
        exclude=sender,
    )


def notify_mentions(referral, users, author) -> None:
    notify(
        users,
        verb="REFERRAL_MENTION",
        message=f"{author} mentioned you on referral {referral.reference_number}.",
        url=_url(referral) + "#comments",
        target=referral,
        exclude=author,
    )


def notify_overdue(referral) -> int:
    return notify(
        side_users(referral, referral.receiving_organization),
        verb="REFERRAL_OVERDUE",
        message=f"Referral {referral.reference_number} is waiting for a response.",
        url=_url(referral),
        target=referral,
    )

"""In-app notifications + email outbox. Messages never contain PHI.

In-app text may name the referral number (it's shown only inside the signed-in app). Emails
say only that something changed, with a link to sign in.
"""

from collections.abc import Iterable

from django.conf import settings
from django.db import transaction

from .models import EmailOutbox, Notification

EMAIL_SUBJECT = "Health Depot: you have an update"
EMAIL_BODY = (
    "Hello,\n\n"
    "There is an update for you in Health Depot ({what}).\n"
    "For privacy, details are only shown after you sign in:\n\n"
    "{url}\n\n"
    "— Health Depot (Calvert County Health Department)\n"
    "You received this because you work with referrals in Health Depot."
)
SAFE_WHAT = {
    "REFERRAL_NEW": "a new referral",
    "REFERRAL_STATUS": "a referral was updated",
    "REFERRAL_ASSIGNED": "a referral was assigned to you",
    "REFERRAL_MESSAGE": "a new secure message",
    "REFERRAL_MENTION": "you were mentioned in a comment",
    "REFERRAL_OVERDUE": "a referral is waiting for a response",
    "CASE_TASK": "a case task was assigned to you",
}


def notify(
    recipients: Iterable,
    *,
    verb: str,
    message: str,
    url: str,
    target=None,
    email: bool = True,
    exclude=None,
) -> int:
    """Create a notification (and optional email) for each active recipient."""
    seen = set()
    count = 0
    with transaction.atomic():
        for user in recipients:
            if user is None or not user.is_active or user.pk in seen:
                continue
            if exclude is not None and user.pk == getattr(exclude, "pk", None):
                continue
            seen.add(user.pk)
            Notification.objects.create(
                recipient=user,
                verb=verb,
                message=message[:255],
                url=url,
                target_type=target.__class__.__name__ if target is not None else "",
                target_id=str(target.pk) if target is not None else "",
            )
            if email and user.email:
                EmailOutbox.objects.create(
                    to_email=user.email,
                    subject=EMAIL_SUBJECT,
                    body_text=EMAIL_BODY.format(
                        what=SAFE_WHAT.get(verb, "an update"),
                        url=f"{settings.PUBLIC_BASE_URL}{url}",
                    ),
                )
            count += 1
    return count

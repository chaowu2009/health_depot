"""The closed-loop status workflow — the only place transitions are defined."""

from .models import ReferralStatus as S

TRANSITIONS: dict[str, list[str]] = {
    S.SUBMITTED: [S.RECEIVED, S.ACCEPTED, S.DECLINED],
    S.RECEIVED: [S.ACCEPTED, S.DECLINED],
    S.ACCEPTED: [S.IN_PROGRESS, S.COMPLETED, S.CLOSED_UNABLE_TO_CONTACT],
    S.IN_PROGRESS: [S.COMPLETED, S.CLOSED_UNABLE_TO_CONTACT],
    S.DECLINED: [],
    S.COMPLETED: [],
    S.CLOSED_UNABLE_TO_CONTACT: [],
}
FINAL_STATUSES = {S.DECLINED, S.COMPLETED, S.CLOSED_UNABLE_TO_CONTACT}
OPEN_STATUSES = [s for s in S.values if s not in FINAL_STATUSES]

ACTION_LABELS = {
    S.RECEIVED: "Mark received",
    S.ACCEPTED: "Accept",
    S.DECLINED: "Decline",
    S.IN_PROGRESS: "Start services",
    S.COMPLETED: "Mark completed",
    S.CLOSED_UNABLE_TO_CONTACT: "Close — unable to contact",
}
# Transitions that need an explanation from the person making the change.
NOTE_REQUIRED = {
    S.DECLINED: "Why is this referral being declined?",
    S.COMPLETED: "What was the outcome?",
    S.CLOSED_UNABLE_TO_CONTACT: "What contact attempts were made?",
}
TIMESTAMP_FIELD = {
    S.SUBMITTED: "submitted_at",
    S.RECEIVED: "received_at",
    S.ACCEPTED: "accepted_at",
    S.DECLINED: "declined_at",
    S.IN_PROGRESS: "in_progress_at",
    S.COMPLETED: "completed_at",
    S.CLOSED_UNABLE_TO_CONTACT: "closed_at",
}
OUTCOMES = [
    ("SERVICES_PROVIDED", "Services provided"),
    ("PARTIALLY_MET", "Need partially met"),
    ("CLIENT_DECLINED", "Client declined services"),
    ("REFERRED_ELSEWHERE", "Referred elsewhere"),
    ("OTHER", "Other"),
]
STATUS_STYLE = {
    S.SUBMITTED: "bg-sky-100 text-sky-900",
    S.RECEIVED: "bg-indigo-100 text-indigo-900",
    S.ACCEPTED: "bg-teal-100 text-teal-900",
    S.IN_PROGRESS: "bg-amber-100 text-amber-900",
    S.COMPLETED: "bg-emerald-100 text-emerald-900",
    S.DECLINED: "bg-rose-100 text-rose-900",
    S.CLOSED_UNABLE_TO_CONTACT: "bg-slate-200 text-slate-800",
}


def allowed_next(status: str) -> list[str]:
    return list(TRANSITIONS.get(status, []))


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, [])

from django.contrib import messages as flash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.accounts.access import can_edit_anything, can_edit_program, sees_everything
from apps.accounts.mixins import StaffRequiredMixin
from apps.accounts.models import User
from apps.audit.services import log_read
from apps.clients.models import Client
from apps.core.models import SavedView
from apps.messaging.models import Message, MessageReceipt
from apps.organizations.views import editable_programs

from . import services
from .forms import CommentForm, InboxFilterForm, MessageForm, OutboundReferralForm
from .models import Referral
from .workflow import (
    ACTION_LABELS,
    NOTE_REQUIRED,
    OPEN_STATUSES,
    OUTCOMES,
    STATUS_STYLE,
    allowed_next,
)

FILTER_KEYS = [
    "q",
    "status",
    "direction",
    "program",
    "partner",
    "priority",
    "date_from",
    "date_to",
    "overdue",
    "mine",
]


def filter_referrals(user, qs, data: dict):
    if data.get("q"):
        q = data["q"].strip()
        parts = q.split()
        name_q = Q()
        for p in parts:
            name_q &= Q(client__first_name__icontains=p) | Q(client__last_name__icontains=p)
        qs = qs.filter(Q(reference_number__icontains=q) | name_q)
    status = data.get("status")
    if status == "OPEN":
        qs = qs.filter(status__in=OPEN_STATUSES)
    elif status:
        qs = qs.filter(status=status)
    org_id = user.organization_id
    if data.get("direction") == "incoming" and org_id:
        qs = qs.filter(receiving_organization_id=org_id)
    elif data.get("direction") == "outgoing" and org_id:
        qs = qs.filter(sending_organization_id=org_id)
    if data.get("program"):
        qs = qs.filter(program=data["program"])
    if data.get("partner"):
        qs = qs.filter(
            Q(sending_organization=data["partner"]) | Q(receiving_organization=data["partner"])
        )
    if data.get("priority"):
        qs = qs.filter(priority=data["priority"])
    if data.get("date_from"):
        qs = qs.filter(submitted_at__date__gte=data["date_from"])
    if data.get("date_to"):
        qs = qs.filter(submitted_at__date__lte=data["date_to"])
    if data.get("overdue"):
        qs = qs & Referral.objects.overdue()
    if data.get("mine"):
        qs = qs.filter(assigned_to=user)
    return qs


class InboxView(LoginRequiredMixin, View):
    template_name = "referrals/inbox.html"

    def get(self, request):
        user = request.user
        form = InboxFilterForm(request.GET or None)
        qs = Referral.objects.for_user(user).select_related(
            "client", "program", "sending_organization", "receiving_organization", "assigned_to"
        )
        if form.is_valid():
            qs = filter_referrals(user, qs, form.cleaned_data)
        sort = request.GET.get("sort", "-submitted_at")
        if sort not in ("-submitted_at", "submitted_at", "-last_status_change_at", "priority"):
            sort = "-submitted_at"
        qs = qs.order_by(sort, "-created_at")
        page = Paginator(qs, 25).get_page(request.GET.get("page"))
        params = request.GET.copy()
        params.pop("page", None)
        saved = SavedView.objects.filter(owner=user, view_type=SavedView.ViewType.REFERRAL_INBOX)
        counts = {
            "open": Referral.objects.for_user(user).open().count(),
            "overdue": Referral.objects.for_user(user).overdue().count(),
            "mine": Referral.objects.for_user(user).open().filter(assigned_to=user).count(),
        }
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "page_obj": page,
                "referrals": page.object_list,
                "querystring": params.urlencode(),
                "saved_views": saved,
                "counts": counts,
                "status_style": STATUS_STYLE,
                "active": "referrals",
                "can_create": user.role != user.Role.PARTNER_USER and can_edit_anything(user),
                "is_partner": user.role == user.Role.PARTNER_USER,
            },
        )


class SavedViewCreateView(LoginRequiredMixin, View):
    def post(self, request):
        name = (request.POST.get("name") or "").strip()[:100]
        filters = {k: request.POST.get(k, "") for k in FILTER_KEYS if request.POST.get(k)}
        if name:
            SavedView.objects.create(
                owner=request.user,
                name=name,
                filters=filters,
                view_type=SavedView.ViewType.REFERRAL_INBOX,
            )
            flash.success(request, f"Saved view “{name}”.")
        return redirect(
            reverse("referral-inbox") + "?" + "&".join(f"{k}={v}" for k, v in filters.items())
        )


class SavedViewDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        SavedView.objects.filter(owner=request.user, pk=pk).delete()
        return redirect("referral-inbox")


class ReferralDetailView(LoginRequiredMixin, View):
    """Referral page. Records outside the user's scope return 404 — never 403."""

    template_name = "referrals/referral_detail.html"

    def get_referral(self, request, pk) -> Referral:
        referral = (
            Referral.objects.for_user(request.user)
            .select_related(
                "client",
                "program",
                "sending_organization",
                "receiving_organization",
                "assigned_to",
                "source_link",
                "case",
            )
            .filter(pk=pk)
            .first()
        )
        if referral is None:
            raise Http404
        return referral

    def get(self, request, pk):
        referral = self.get_referral(request, pk)
        log_read(request, referral)
        referral = services.auto_mark_received(referral, request.user)
        return render(request, self.template_name, self.context(request, referral))

    def context(self, request, referral, **extra):
        user = request.user
        is_partner = user.role == user.Role.PARTNER_USER
        can_act = services.can_change_status(user, referral)
        thread = getattr(referral, "thread", None)
        thread_messages = (
            list(thread.messages.select_related("sender", "sender__organization")) if thread else []
        )
        if thread_messages:
            for m in thread_messages:
                MessageReceipt.objects.get_or_create(message=m, user=user)
        staff_qs = User.objects.filter(is_active=True).exclude(role=User.Role.PARTNER_USER)
        program_staff = (
            staff_qs.filter(
                Q(program_access__program=referral.program) | Q(role=User.Role.SYSTEM_ADMIN)
            )
            .distinct()
            .order_by("first_name", "last_name")
        )
        can_assign = not is_partner and (
            sees_everything(user) or can_edit_program(user, referral.program_id)
        )
        events = referral.events.select_related("actor", "actor_organization")
        return {
            "referral": referral,
            "client": referral.client,
            "active": "referrals",
            "is_partner": is_partner,
            "can_act": can_act,
            "actions": [
                (s, ACTION_LABELS[s], NOTE_REQUIRED.get(s)) for s in allowed_next(referral.status)
            ]
            if can_act
            else [],
            "outcomes": OUTCOMES,
            "status_style": STATUS_STYLE,
            "events": events,
            "thread_messages": thread_messages,
            "comments": []
            if is_partner
            else referral.comments.select_related("author").prefetch_related("mentions"),
            "comment_form": None if is_partner else CommentForm(mention_users=program_staff),
            "message_form": MessageForm(),
            "can_assign": can_assign,
            "assignable": program_staff,
            "can_open_case": not is_partner
            and referral.status in ("ACCEPTED", "IN_PROGRESS")
            and referral.case_id is None
            and can_edit_program(user, referral.program_id),
            **extra,
        }


class StatusChangeView(LoginRequiredMixin, View):
    def post(self, request, pk):
        referral = ReferralDetailView().get_referral(request, pk)
        try:
            services.change_status(
                referral,
                request.POST.get("to_status", ""),
                user=request.user,
                note=request.POST.get("note", ""),
                outcome=request.POST.get("outcome", ""),
            )
            flash.success(request, "Status updated. Both organizations were notified.")
        except (services.WorkflowError, ValueError) as exc:
            flash.error(request, str(exc))
        return redirect("referral-detail", pk=pk)


class AssignView(LoginRequiredMixin, View):
    def post(self, request, pk):
        referral = ReferralDetailView().get_referral(request, pk)
        assignee = User.objects.filter(pk=request.POST.get("assignee") or 0).first()
        try:
            services.assign(referral, assignee, user=request.user)
            flash.success(request, "Assignment updated.")
        except services.WorkflowError as exc:
            flash.error(request, str(exc))
        return redirect("referral-detail", pk=pk)


class CommentView(StaffRequiredMixin, View):
    def post(self, request, pk):
        referral = ReferralDetailView().get_referral(request, pk)
        staff = User.objects.filter(is_active=True).exclude(role=User.Role.PARTNER_USER)
        form = CommentForm(request.POST, mention_users=staff)
        if form.is_valid():
            services.add_comment(
                referral,
                user=request.user,
                body=form.cleaned_data["body"],
                mentions=list(form.cleaned_data["mentions"]),
            )
            flash.success(request, "Comment added.")
        else:
            flash.error(request, "Comment can't be empty.")
        return redirect(reverse("referral-detail", args=[pk]) + "#comments")


class MessageSendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        referral = ReferralDetailView().get_referral(request, pk)
        form = MessageForm(request.POST)
        if form.is_valid():
            try:
                services.send_message(referral, user=request.user, body=form.cleaned_data["body"])
                flash.success(request, "Message sent.")
            except services.WorkflowError as exc:
                flash.error(request, str(exc))
        else:
            flash.error(request, "Message can't be empty.")
        return redirect(reverse("referral-detail", args=[pk]) + "#messages")


class MessagesView(LoginRequiredMixin, View):
    """All secure message threads the user can see, newest first."""

    def get(self, request):
        user = request.user
        referrals = (
            Referral.objects.for_user(user)
            .filter(thread__isnull=False)
            .annotate(
                last_message=Max("thread__messages__created_at"),
                message_count=Count("thread__messages", distinct=True),
            )
            .select_related("client", "sending_organization", "receiving_organization")
            .order_by("-last_message")
        )
        page = Paginator(referrals, 25).get_page(request.GET.get("page"))
        read_ids = set(
            MessageReceipt.objects.filter(user=user).values_list("message_id", flat=True)
        )
        for r in page.object_list:
            msgs = Message.objects.filter(thread__referral=r).values_list("id", flat=True)
            r.unread = sum(1 for m in msgs if m not in read_ids)
            r.preview = (
                Message.objects.filter(thread__referral=r)
                .order_by("-created_at")
                .select_related("sender")
                .first()
            )
        return render(
            request,
            "referrals/messages.html",
            {"page_obj": page, "threads": page.object_list, "active": "messages"},
        )


class OutboundCreateView(StaffRequiredMixin, View):
    """CCHD staff refer a client to a community partner."""

    template_name = "referrals/referral_new.html"

    def _form(self, request, data=None):
        user = request.user
        clients = (
            Client.objects.all() if sees_everything(user) else Client.objects.editable_by(user)
        )
        initial = {}
        if request.GET.get("client"):
            initial["client"] = clients.filter(pk=request.GET["client"]).first()
        return OutboundReferralForm(
            data,
            clients=clients.order_by("last_name", "first_name"),
            programs=editable_programs(user),
            initial=initial,
        )

    def get(self, request):
        if not can_edit_anything(request.user):
            flash.error(request, "Your role can view referrals but not create them.")
            return redirect("referral-inbox")
        return render(
            request, self.template_name, {"form": self._form(request), "active": "referrals"}
        )

    def post(self, request):
        form = self._form(request, request.POST)
        if not can_edit_anything(request.user) or not form.is_valid():
            return render(request, self.template_name, {"form": form, "active": "referrals"})
        d = form.cleaned_data
        client = d.get("client") or services.find_or_create_client(
            {
                "first_name": d["first_name"],
                "last_name": d["last_name"],
                "date_of_birth": d["date_of_birth"],
                "phone": d.get("phone", ""),
            },
            program=d["program"],
            user=request.user,
        )
        referral = services.create_outbound(
            user=request.user,
            client=client,
            program=d["program"],
            partner=d["partner"],
            priority=d["priority"],
            reason=d["reason"],
            needs=d["needs"],
        )
        flash.success(request, f"Referral {referral.reference_number} sent to {d['partner']}.")
        return redirect("referral-detail", pk=referral.pk)

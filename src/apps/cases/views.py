from django.contrib import messages as flash
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.accounts.access import sees_everything
from apps.accounts.mixins import StaffRequiredMixin
from apps.accounts.models import User
from apps.audit.services import log_read
from apps.clients.models import Client
from apps.organizations.views import editable_programs
from apps.referrals.models import Referral

from . import services
from .forms import DischargeForm, DocumentForm, GoalForm, NewCaseForm, NoteForm, TaskForm
from .models import CarePlanGoal, Case, CaseDocument, CaseTask


def staff_for_program(program):
    return (
        User.objects.filter(is_active=True)
        .exclude(role=User.Role.PARTNER_USER)
        .filter(Q(program_access__program=program) | Q(role=User.Role.SYSTEM_ADMIN))
        .distinct()
        .order_by("first_name", "last_name")
    )


def _case(request, pk, *, edit=False) -> Case:
    qs = Case.objects.editable_by(request.user) if edit else Case.objects.for_user(request.user)
    case = qs.select_related("client", "program", "case_manager").filter(pk=pk).first()
    if case is None:
        raise Http404
    return case


class CaseListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = (
            Case.objects.for_user(request.user)
            .select_related("client", "program", "case_manager")
            .annotate(open_tasks=Count("tasks", filter=Q(tasks__completed_at__isnull=True)))
        )
        status = request.GET.get("status", "active")
        if status == "active":
            qs = qs.exclude(status=Case.Status.DISCHARGED)
        elif status in Case.Status.values:
            qs = qs.filter(status=status)
        if request.GET.get("mine"):
            qs = qs.filter(case_manager=request.user)
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(case_number__icontains=q)
                | Q(client__first_name__icontains=q)
                | Q(client__last_name__icontains=q)
            )
        page = Paginator(qs.order_by("-admitted_at"), 25).get_page(request.GET.get("page"))
        params = request.GET.copy()
        params.pop("page", None)
        return render(
            request,
            "cases/case_list.html",
            {
                "page_obj": page,
                "cases": page.object_list,
                "status": status,
                "q": q,
                "statuses": Case.Status.choices,
                "querystring": params.urlencode(),
                "active": "cases",
            },
        )


class CaseCreateView(StaffRequiredMixin, View):
    def _form(self, request, data=None):
        clients = (
            Client.objects.all()
            if sees_everything(request.user)
            else Client.objects.editable_by(request.user)
        )
        managers = User.objects.filter(is_active=True).exclude(
            role__in=[User.Role.PARTNER_USER, User.Role.READ_ONLY]
        )
        initial = {"case_manager": request.user}
        if request.GET.get("client"):
            initial["client"] = clients.filter(pk=request.GET["client"]).first()
        return NewCaseForm(
            data,
            clients=clients.order_by("last_name"),
            programs=editable_programs(request.user),
            managers=managers,
            initial=initial,
        )

    def get(self, request):
        return render(
            request, "cases/case_new.html", {"form": self._form(request), "active": "cases"}
        )

    def post(self, request):
        form = self._form(request, request.POST)
        if not form.is_valid():
            return render(request, "cases/case_new.html", {"form": form, "active": "cases"})
        d = form.cleaned_data
        case = services.create_case(
            client=d["client"],
            program=d["program"],
            manager=d["case_manager"] or request.user,
            user=request.user,
        )
        flash.success(request, f"Case {case.case_number} opened.")
        return redirect("case-detail", pk=case.pk)


class CaseFromReferralView(StaffRequiredMixin, View):
    def post(self, request, pk):
        referral = Referral.objects.editable_by(request.user).filter(pk=pk).first()
        if referral is None:
            raise Http404
        try:
            case = services.open_from_referral(referral, user=request.user)
        except services.CaseError as exc:
            flash.error(request, str(exc))
            return redirect("referral-detail", pk=pk)
        flash.success(request, f"Case {case.case_number} opened from {referral.reference_number}.")
        return redirect("case-detail", pk=case.pk)


class CaseDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        case = _case(request, pk)
        log_read(request, case)
        editable = Case.objects.editable_by(request.user).filter(pk=pk).exists()
        staff = staff_for_program(case.program)
        return render(
            request,
            "cases/case_detail.html",
            {
                "case": case,
                "client": case.client,
                "editable": editable,
                "active": "cases",
                "goals": case.goals.all(),
                "tasks": case.tasks.select_related("assigned_to"),
                "notes": case.notes.select_related("author"),
                "documents": case.documents.select_related("uploaded_by"),
                "referrals": Referral.objects.for_user(request.user).filter(case=case),
                "goal_form": GoalForm(),
                "task_form": TaskForm(staff=staff, initial={"assigned_to": request.user}),
                "note_form": NoteForm(initial={"contact_date": timezone.localdate()}),
                "document_form": DocumentForm(),
                "discharge_form": DischargeForm(),
                "statuses": [c for c in Case.Status.choices if c[0] != "DISCHARGED"],
                "goal_statuses": CarePlanGoal.Status.choices,
            },
        )


class CaseActionView(StaffRequiredMixin, View):
    """All edits to a case post here with an `action` field (keeps URLs simple)."""

    def post(self, request, pk, action):
        case = _case(request, pk, edit=True)
        user = request.user
        anchor = ""
        try:
            if action == "status":
                services.set_status(case, request.POST.get("status", ""), user=user)
            elif action == "reopen":
                services.set_status(case, Case.Status.ACTIVE, user=user)
            elif action == "goal":
                form = GoalForm(request.POST)
                if not form.is_valid():
                    raise services.CaseError("Enter the goal.")
                services.add_goal(case, user=user, **form.cleaned_data)
                anchor = "#goals"
            elif action == "goal-status":
                goal = case.goals.filter(pk=request.POST.get("goal")).first()
                if goal and request.POST.get("status") in CarePlanGoal.Status.values:
                    services.set_goal_status(goal, request.POST["status"])
                anchor = "#goals"
            elif action == "task":
                form = TaskForm(request.POST, staff=staff_for_program(case.program))
                if not form.is_valid():
                    raise services.CaseError("Enter a task title.")
                services.add_task(case, user=user, **form.cleaned_data)
                anchor = "#tasks"
            elif action == "task-toggle":
                task = case.tasks.filter(pk=request.POST.get("task")).first()
                if task:
                    services.toggle_task(task, user=user)
                anchor = "#tasks"
            elif action == "note":
                form = NoteForm(request.POST)
                if not form.is_valid():
                    raise services.CaseError("Write the note.")
                services.add_note(case, user=user, **form.cleaned_data)
                anchor = "#notes"
            elif action == "document":
                form = DocumentForm(request.POST, request.FILES)
                if not form.is_valid():
                    raise services.CaseError("Choose a file.")
                services.add_document(
                    case,
                    upload=form.cleaned_data["file"],
                    user=user,
                    document_type=form.cleaned_data["document_type"],
                )
                anchor = "#documents"
            elif action == "discharge":
                form = DischargeForm(request.POST)
                if not form.is_valid():
                    raise services.CaseError("Choose a discharge reason and outcome.")
                services.discharge(case, user=user, **form.cleaned_data)
            else:
                raise Http404
            flash.success(request, "Saved.")
        except (services.CaseError, ValidationError) as exc:
            flash.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
        return redirect(reverse("case-detail", args=[pk]) + anchor)


class DocumentDownloadView(StaffRequiredMixin, View):
    """Checks access, logs the read, then redirects to a 5-minute presigned URL."""

    def get(self, request, pk):
        doc = CaseDocument.objects.for_user(request.user).filter(pk=pk).first()
        if doc is None:
            raise Http404
        log_read(request, doc)
        safe_name = "".join(c for c in doc.filename if c.isalnum() or c in "._- ")[:100]
        try:  # S3: ask storage to serve it as a download with the original name
            url = doc.file.storage.url(
                doc.file.name,
                parameters={"ResponseContentDisposition": f'attachment; filename="{safe_name}"'},
            )
        except TypeError:  # other storage backends (tests)
            url = doc.file.storage.url(doc.file.name)
        return redirect(url)


class ClientListView(StaffRequiredMixin, View):
    def get(self, request):
        qs = Client.objects.for_user(request.user).annotate(
            referral_count=Count("referrals", distinct=True),
            case_count=Count("cases", distinct=True),
        )
        q = request.GET.get("q", "").strip()
        for part in q.split():
            qs = qs.filter(
                Q(first_name__icontains=part)
                | Q(last_name__icontains=part)
                | Q(phone__icontains=part)
                | Q(zip_code=part)
            )
        if request.GET.get("duplicates"):
            qs = qs.filter(possible_duplicate_of__isnull=False)
        page = Paginator(qs.order_by("last_name", "first_name"), 30).get_page(
            request.GET.get("page")
        )
        params = request.GET.copy()
        params.pop("page", None)
        return render(
            request,
            "cases/client_list.html",
            {
                "page_obj": page,
                "clients": page.object_list,
                "q": q,
                "active": "clients",
                "querystring": params.urlencode(),
            },
        )


class ClientDetailView(StaffRequiredMixin, View):
    def get(self, request, pk):
        client = Client.objects.for_user(request.user).filter(pk=pk).first()
        if client is None:
            raise Http404
        log_read(request, client)
        duplicate = client.possible_duplicate_of
        if duplicate and not Client.objects.for_user(request.user).filter(pk=duplicate.pk).exists():
            duplicate = None
        return render(
            request,
            "cases/client_detail.html",
            {
                "client": client,
                "active": "clients",
                "duplicate": duplicate,
                "referrals": Referral.objects.for_user(request.user)
                .filter(client=client)
                .select_related("program", "sending_organization", "receiving_organization")
                .order_by("-submitted_at"),
                "cases": Case.objects.for_user(request.user)
                .filter(client=client)
                .select_related("program", "case_manager"),
                "programs": client.programs.all(),
            },
        )


class ClientDuplicateResolveView(StaffRequiredMixin, View):
    """Mark a flagged possible duplicate as reviewed (not the same person)."""

    def post(self, request, pk):
        client = Client.objects.editable_by(request.user).filter(pk=pk).first()
        if client is None:
            raise Http404
        client.possible_duplicate_of = None
        client.updated_by = request.user
        client.save()
        flash.success(request, "Marked as a different person.")
        return redirect("client-detail", pk=pk)


class MyWorkView(StaffRequiredMixin, View):
    def get(self, request):
        user = request.user
        today = timezone.localdate()
        tasks = (
            CaseTask.objects.for_user(user)
            .filter(assigned_to=user, completed_at__isnull=True)
            .select_related("case", "case__client")
            .order_by("due_date")
        )
        return render(
            request,
            "cases/my_work.html",
            {
                "tasks": tasks,
                "today": today,
                "active": "my-work",
                "overdue_referrals": Referral.objects.for_user(user)
                .overdue()
                .filter(Q(assigned_to=user) | Q(assigned_to__isnull=True))
                .select_related("client", "program", "sending_organization")[:50],
                "my_referrals": Referral.objects.for_user(user)
                .open()
                .filter(assigned_to=user)
                .select_related("client", "sending_organization")[:50],
                "cases": Case.objects.for_user(user)
                .filter(case_manager=user)
                .exclude(status=Case.Status.DISCHARGED)
                .select_related("client", "program"),
            },
        )

import json

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.accounts.access import can_manage_partners
from apps.accounts.mixins import ManagePartnersRequiredMixin, StaffRequiredMixin
from apps.organizations.models import Organization

from . import services
from .dynamic import build_form
from .forms import FieldForm, NewTemplateForm, TemplateMetaForm
from .intake import TEXT, IdentityForm
from .models import FormTemplate
from .schema import FIELD_TYPES, NEED_TAGS


class TemplateListView(StaffRequiredMixin, ListView):
    template_name = "forms_builder/template_list.html"
    context_object_name = "templates"

    def get_queryset(self):
        return FormTemplate.objects.select_related("program").order_by(
            "-is_system_template", "name"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(active="forms", can_manage=can_manage_partners(self.request.user))
        return ctx


class TemplateCreateView(ManagePartnersRequiredMixin, View):
    def get(self, request):
        initial = {}
        if request.GET.get("copy"):
            initial["start_from"] = request.GET["copy"]
        return render(
            request,
            "forms_builder/template_new.html",
            {"form": NewTemplateForm(initial=initial), "active": "forms"},
        )

    def post(self, request):
        form = NewTemplateForm(request.POST)
        if not form.is_valid():
            return render(
                request, "forms_builder/template_new.html", {"form": form, "active": "forms"}
            )
        cchd = Organization.objects.filter(org_type=Organization.OrgType.HEALTH_DEPARTMENT).first()
        source = form.cleaned_data.get("start_from")
        if source:
            template = services.copy_template(
                source,
                name=form.cleaned_data["name"],
                owner=cchd,
                program=form.cleaned_data.get("program"),
                user=request.user,
            )
            template.description = form.cleaned_data.get("description") or source.description
            template.save(update_fields=["description"])
        else:
            template = form.save(commit=False)
            template.owner_organization = cchd
            template.created_by = template.updated_by = request.user
            template.save()
        messages.success(request, "Form created. Add or edit questions below.")
        return redirect("form-builder", pk=template.pk)


class BuilderView(StaffRequiredMixin, View):
    """The form builder: questions on the left, live public preview on the right."""

    def get(self, request, pk):
        template = get_object_or_404(FormTemplate, pk=pk)
        return render(request, "forms_builder/builder.html", self.context(request, template))

    def context(self, request, template, *, add_form=None, meta_form=None, edit_errors=None):
        partners = Organization.objects.filter(
            org_type=Organization.OrgType.COMMUNITY_PARTNER, is_active=True
        )
        partner = (
            partners.filter(pk=request.GET.get("partner")).first()
            if request.GET.get("partner")
            else partners.first()
        )
        lang = "es" if request.GET.get("lang") == "es" else "en"
        field_forms = []
        for f in template.fields:
            others = [o for o in template.fields if o["key"] != f["key"]]
            bound = (edit_errors or {}).get(f["key"])
            field_forms.append(
                (
                    f,
                    bound
                    or FieldForm(
                        initial=services.form_initial(f),
                        other_fields=others,
                        prefix=f"edit-{f['key']}",
                    ),
                )
            )
        return {
            "template": template,
            "active": "forms",
            "can_edit": can_manage_partners(request.user) and not template.is_system_template,
            "can_manage": can_manage_partners(request.user),
            "meta_form": meta_form or TemplateMetaForm(instance=template),
            "add_form": add_form or FieldForm(other_fields=template.fields, prefix="add"),
            "field_forms": field_forms,
            "field_types": FIELD_TYPES,
            "need_tags": NEED_TAGS,
            "partners": partners,
            "partner": partner,
            "lang": lang,
            "t": TEXT[lang],
            "identity_form": IdentityForm(lang=lang, prefix="id"),
            "question_form": build_form(template.fields, lang=lang),
            "preview": True,
        }


class _EditMixin(ManagePartnersRequiredMixin):
    def get_template(self, pk) -> FormTemplate:
        template = get_object_or_404(FormTemplate, pk=pk)
        if template.is_system_template:
            raise Http404
        return template


class MetaUpdateView(_EditMixin, View):
    def post(self, request, pk):
        template = self.get_template(pk)
        form = TemplateMetaForm(request.POST, instance=template)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, "Form details saved.")
            return redirect("form-builder", pk=pk)
        return render(
            request,
            "forms_builder/builder.html",
            BuilderView().context(request, template, meta_form=form),
        )


class FieldAddView(_EditMixin, View):
    def post(self, request, pk):
        template = self.get_template(pk)
        form = FieldForm(request.POST, other_fields=template.fields, prefix="add")
        if form.is_valid():
            try:
                services.add_field(template, form.cleaned_data, request.user)
                messages.success(request, "Question added.")
                return redirect("form-builder", pk=pk)
            except ValueError as exc:
                form.add_error(None, str(exc))
        return render(
            request,
            "forms_builder/builder.html",
            BuilderView().context(request, template, add_form=form),
        )


class FieldUpdateView(_EditMixin, View):
    def post(self, request, pk, key):
        template = self.get_template(pk)
        if key not in {f["key"] for f in template.fields}:
            raise Http404
        others = [f for f in template.fields if f["key"] != key]
        form = FieldForm(request.POST, other_fields=others, prefix=f"edit-{key}")
        if form.is_valid():
            try:
                services.update_field(template, key, form.cleaned_data, request.user)
                messages.success(request, "Question saved.")
                return redirect("form-builder", pk=pk)
            except ValueError as exc:
                form.add_error(None, str(exc))
        return render(
            request,
            "forms_builder/builder.html",
            BuilderView().context(request, template, edit_errors={key: form}),
        )


class FieldDeleteView(_EditMixin, View):
    def post(self, request, pk, key):
        template = self.get_template(pk)
        services.delete_field(template, key, request.user)
        messages.success(request, "Question removed.")
        return redirect("form-builder", pk=pk)


class ReorderView(_EditMixin, View):
    """Called by SortableJS after a drag (HTMX/fetch POST with JSON body or form list)."""

    def post(self, request, pk):
        template = self.get_template(pk)
        try:
            order = (
                json.loads(request.body)["order"]
                if request.content_type == "application/json"
                else request.POST.getlist("order")
            )
            services.reorder_fields(template, order, request.user)
        except (ValueError, KeyError, TypeError):
            return HttpResponseBadRequest("Invalid order")
        return HttpResponse(status=204)

import io
import uuid

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.accounts.access import can_edit_program, can_manage_partners, program_ids, sees_everything
from apps.accounts.mixins import ManagePartnersRequiredMixin
from apps.referrals.models import ReferralLink

from .forms import PartnerForm, ReferralLinkForm
from .models import Organization, PartnerProgram, Program


def public_link_url(link: ReferralLink) -> str:
    return f"{settings.PUBLIC_BASE_URL}{reverse('public-intake', args=[link.slug])}"


def visible_partners(user):
    qs = Organization.objects.filter(org_type=Organization.OrgType.COMMUNITY_PARTNER)
    if user.role == user.Role.PARTNER_USER:
        return qs.filter(pk=user.organization_id)
    return qs


def editable_programs(user):
    qs = Program.objects.filter(is_active=True)
    return qs if sees_everything(user) else qs.filter(pk__in=program_ids(user, edit=True))


class PartnerListView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        if user.role == user.Role.PARTNER_USER:
            if not user.organization_id:
                raise PermissionDenied
            return redirect("partner-detail", pk=user.organization_id)
        q = request.GET.get("q", "").strip()
        partners = (
            visible_partners(user)
            .annotate(
                link_count=Count("referral_links", distinct=True),
                referral_count=Count("referrals_sent", distinct=True)
                + Count("referrals_received", distinct=True),
            )
            .order_by("-is_active", "name")
        )
        if q:
            partners = partners.filter(Q(name__icontains=q) | Q(service_area_zips__icontains=q))
        return render(
            request,
            "organizations/partner_list.html",
            {
                "partners": partners,
                "q": q,
                "active": "partners",
                "can_manage": can_manage_partners(user),
            },
        )


class PartnerEditView(ManagePartnersRequiredMixin, View):
    template_name = "organizations/partner_form.html"

    def _get(self, pk):
        if pk is None:
            return Organization(org_type=Organization.OrgType.COMMUNITY_PARTNER)
        return get_object_or_404(
            Organization, pk=pk, org_type=Organization.OrgType.COMMUNITY_PARTNER
        )

    def get(self, request, pk=None):
        partner = self._get(pk)
        return render(
            request,
            self.template_name,
            {"form": PartnerForm(instance=partner), "partner": partner, "active": "partners"},
        )

    def post(self, request, pk=None):
        partner = self._get(pk)
        form = PartnerForm(request.POST, request.FILES, instance=partner)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form, "partner": partner, "active": "partners"},
            )
        with transaction.atomic():
            obj = form.save(commit=False)
            if not obj.slug:
                obj.slug = f"partner-{uuid.uuid4().hex[:10]}"
            upload = form.cleaned_data.get("logo")
            if upload and hasattr(upload, "content_type"):
                ext = "png" if upload.read(4).startswith(b"\x89PNG") else "jpg"
                upload.seek(0)
                obj.logo.save(f"{uuid.uuid4().hex}.{ext}", upload, save=False)
            obj.save()
            selected = set(form.cleaned_data.get("programs") or [])
            PartnerProgram.objects.filter(partner=obj).exclude(program__in=selected).delete()
            for program in selected:
                PartnerProgram.objects.get_or_create(partner=obj, program=program)
        messages.success(request, f"Saved {obj.name}.")
        return redirect("partner-detail", pk=obj.pk)


class PartnerDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        partner = get_object_or_404(visible_partners(request.user), pk=pk)
        links = (
            ReferralLink.objects.for_user(request.user)
            .filter(partner=partner)
            .select_related("program", "form_template")
            .order_by("-is_active", "label")
        )
        for link in links:
            link.public_url = public_link_url(link)
            link.can_edit = can_manage_partners(request.user) and can_edit_program(
                request.user, link.program_id
            )
        can_manage = can_manage_partners(request.user)
        return render(
            request,
            "organizations/partner_detail.html",
            {
                "partner": partner,
                "links": links,
                "active": "partners",
                "can_manage": can_manage,
                "link_form": ReferralLinkForm(programs=editable_programs(request.user))
                if can_manage
                else None,
                "programs": partner.partner_programs.all(),
            },
        )


class LinkCreateView(ManagePartnersRequiredMixin, View):
    def post(self, request, pk):
        partner = get_object_or_404(
            Organization, pk=pk, org_type=Organization.OrgType.COMMUNITY_PARTNER
        )
        form = ReferralLinkForm(request.POST, programs=editable_programs(request.user))
        if form.is_valid():
            link = form.save(commit=False)
            link.partner = partner
            link.created_by = link.updated_by = request.user
            link.save()
            PartnerProgram.objects.get_or_create(partner=partner, program=link.program)
            messages.success(request, f"Referral link created: {public_link_url(link)}")
        else:
            messages.error(
                request,
                "Couldn't create the link: "
                + "; ".join(f"{k}: {' '.join(v)}" for k, v in form.errors.items()),
            )
        return redirect("partner-detail", pk=pk)


class LinkToggleView(ManagePartnersRequiredMixin, View):
    def post(self, request, pk):
        link = get_object_or_404(ReferralLink.objects.editable_by(request.user), pk=pk)
        link.is_active = not link.is_active
        link.updated_by = request.user
        link.save(update_fields=["is_active", "updated_by", "updated_at"])
        messages.success(request, f"Link {'activated' if link.is_active else 'deactivated'}.")
        return redirect("partner-detail", pk=link.partner_id)


class LinkQRCodeView(LoginRequiredMixin, View):
    """Download a QR code (SVG) for printing on flyers and front-desk signs."""

    def get(self, request, pk):
        link = ReferralLink.objects.for_user(request.user).filter(pk=pk).first()
        if link is None:
            raise Http404
        img = qrcode.make(
            public_link_url(link),
            image_factory=qrcode.image.svg.SvgPathImage,
            box_size=12,
            border=2,
        )
        buffer = io.BytesIO()
        img.save(buffer)
        response = HttpResponse(buffer.getvalue(), content_type="image/svg+xml")
        if request.GET.get("download"):
            response["Content-Disposition"] = (
                f'attachment; filename="referral-link-{link.slug}.svg"'
            )
        return response

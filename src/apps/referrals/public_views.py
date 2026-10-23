"""Public intake form at /r/<slug> — no login. Partner-branded, English/Spanish."""

from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django_ratelimit.core import is_ratelimited

from apps.forms_builder.dynamic import answers_snapshot, build_form, derive_needs
from apps.forms_builder.intake import TEXT, IdentityForm

from . import services
from .models import Referral, ReferralLink

RATE = "10/m"  # submissions per minute per IP


def _lang(request: HttpRequest) -> str:
    return "es" if request.GET.get("lang") == "es" or request.POST.get("lang") == "es" else "en"


def _link_or_inactive(slug: str) -> ReferralLink:
    return get_object_or_404(
        ReferralLink.objects.select_related("partner", "program", "form_template"), slug=slug
    )


def _is_open(link: ReferralLink) -> bool:
    if not link.is_active or not link.partner.is_active:
        return False
    return not (link.expires_at and link.expires_at < timezone.now())


@never_cache
def intake(request: HttpRequest, slug: str) -> HttpResponse:
    link = _link_or_inactive(slug)
    lang = _lang(request)
    t = TEXT[lang]
    ctx = {
        "link": link,
        "partner": link.partner,
        "t": t,
        "lang": lang,
        "lang_switch_url": f"{reverse('public-intake', args=[slug])}?lang={t['switch_lang']}",
    }
    if not _is_open(link):
        return render(request, "public/intake_closed.html", ctx, status=410)

    fields = link.form_template.fields
    if request.method == "POST":
        if is_ratelimited(request, group="public-intake", key="ip", rate=RATE, increment=True):
            return render(request, "public/rate_limited.html", ctx, status=429)
        identity = IdentityForm(request.POST, lang=lang, prefix="id")
        questions = build_form(fields, lang=lang, data=request.POST)
        if identity.is_valid() and questions.is_valid():
            if identity.is_bot:
                # Pretend success; store nothing.
                return redirect(f"{reverse('public-intake-done', args=[slug])}?lang={lang}")
            referral = services.create_from_link(
                link,
                identity=identity.cleaned_data,
                answers=answers_snapshot(fields, questions.cleaned_data),
                needs=derive_needs(fields, questions.cleaned_data),
            )
            # Reference number goes in the session, never the URL.
            request.session["last_reference"] = referral.reference_number
            return redirect(f"{reverse('public-intake-done', args=[slug])}?lang={lang}")
    else:
        ReferralLink.objects.filter(pk=link.pk).update(visit_count=F("visit_count") + 1)
        identity = IdentityForm(lang=lang, prefix="id")
        questions = build_form(fields, lang=lang)
    ctx.update(identity_form=identity, question_form=questions)
    return render(request, "public/intake.html", ctx)


@never_cache
def intake_done(request: HttpRequest, slug: str) -> HttpResponse:
    link = _link_or_inactive(slug)
    lang = _lang(request)
    reference = request.session.pop("last_reference", None)
    return render(
        request,
        "public/intake_done.html",
        {
            "link": link,
            "partner": link.partner,
            "t": TEXT[lang],
            "lang": lang,
            "reference": reference,
        },
    )


__all__ = ["intake", "intake_done", "Referral"]

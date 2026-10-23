from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .navigation import ALL_NAV, PHASE2_SLUGS


@login_required
def home(request: HttpRequest) -> HttpResponse:
    return redirect("dashboard")


@login_required
def section(request: HttpRequest, slug: str) -> HttpResponse:
    """Placeholder page for each section of the app shell until its build step lands."""
    item = ALL_NAV.get(slug)
    if item is None:
        raise Http404
    return render(
        request,
        "core/section_placeholder.html",
        {
            "item": item,
            "active": slug,
            "is_phase2": slug in PHASE2_SLUGS,
        },
    )

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active"] = "notifications"
        return ctx


class NotificationOpenView(LoginRequiredMixin, View):
    def get(self, request, pk):
        note = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not note.read_at:
            note.read_at = timezone.now()
            note.save(update_fields=["read_at", "updated_at"])
        target = note.url if url_has_allowed_host_and_scheme(note.url, None) else "/"
        return redirect(target or "/")


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return redirect("notification-list")

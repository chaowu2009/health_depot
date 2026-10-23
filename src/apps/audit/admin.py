from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: the audit log can be viewed and filtered, never changed."""

    list_display = ("occurred_at", "action", "entity_type", "entity_id", "actor", "actor_ip")
    list_filter = ("action", "entity_type", "program")
    search_fields = ("entity_id", "actor__email", "request_id")
    date_hierarchy = "occurred_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

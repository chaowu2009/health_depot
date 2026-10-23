from django.contrib import admin
from django.http import HttpRequest


class HealthDepotAdminSite(admin.AdminSite):
    site_header = "Health Depot administration"
    site_title = "Health Depot admin"
    index_title = "System administration"

    def has_permission(self, request: HttpRequest) -> bool:
        """Only active SYSTEM_ADMIN users (or Django superusers) may use the admin."""
        user = request.user
        if not (user.is_active and user.is_authenticated):
            return False
        return bool(user.is_superuser or getattr(user, "is_system_admin", False))

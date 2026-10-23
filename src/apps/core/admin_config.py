from django.contrib.admin.apps import AdminConfig


class HealthDepotAdminConfig(AdminConfig):
    """Replaces the default admin site with one restricted to system administrators."""

    default_site = "apps.core.admin_site.HealthDepotAdminSite"

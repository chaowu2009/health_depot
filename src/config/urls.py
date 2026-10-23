from allauth.account.decorators import secure_admin_login
from django.contrib import admin
from django.urls import include, path

from apps.cases.views import MyWorkView
from apps.reports.views import DashboardView

# Django admin uses the same login (with MFA) as the rest of the app.
admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("manage/", include("apps.accounts.urls_manage")),
    path("health/", include("apps.core.health_urls")),
    path("referrals/", include("apps.referrals.urls")),
    path("partners/", include("apps.organizations.urls")),
    path("forms/", include("apps.forms_builder.urls")),
    path("r/", include("apps.referrals.public_urls")),
    path("messages/", include("apps.referrals.messages_urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("cases/", include("apps.cases.urls")),
    path("clients/", include("apps.cases.client_urls")),
    path("my-work/", MyWorkView.as_view(), name="my-work"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/", include("apps.reports.urls")),
    path("", include("apps.phase2.urls")),
    path("", include("apps.core.urls")),
]

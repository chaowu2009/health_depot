from django.urls import path

from . import views_manage as views

urlpatterns = [
    path("users/", views.UserListView.as_view(), name="manage-user-list"),
    path("users/new/", views.UserEditView.as_view(), name="manage-user-create"),
    path("users/<int:pk>/", views.UserEditView.as_view(), name="manage-user-edit"),
    path("users/<int:pk>/reset-mfa/", views.ResetMFAView.as_view(), name="manage-user-reset-mfa"),
    path("audit/", views.AuditLogListView.as_view(), name="manage-audit-log"),
    path("tools/", views.ToolsView.as_view(), name="manage-tools"),
]

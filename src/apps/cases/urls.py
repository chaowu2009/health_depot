from django.urls import path

from . import views

urlpatterns = [
    path("", views.CaseListView.as_view(), name="case-list"),
    path("new/", views.CaseCreateView.as_view(), name="case-create"),
    path(
        "from-referral/<uuid:pk>/", views.CaseFromReferralView.as_view(), name="case-from-referral"
    ),
    path("<uuid:pk>/", views.CaseDetailView.as_view(), name="case-detail"),
    path("<uuid:pk>/do/<slug:action>/", views.CaseActionView.as_view(), name="case-action"),
    path("documents/<uuid:pk>/", views.DocumentDownloadView.as_view(), name="case-document"),
]

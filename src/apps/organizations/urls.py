from django.urls import path

from . import views

urlpatterns = [
    path("", views.PartnerListView.as_view(), name="partner-list"),
    path("new/", views.PartnerEditView.as_view(), name="partner-create"),
    path("<uuid:pk>/", views.PartnerDetailView.as_view(), name="partner-detail"),
    path("<uuid:pk>/edit/", views.PartnerEditView.as_view(), name="partner-edit"),
    path("<uuid:pk>/links/new/", views.LinkCreateView.as_view(), name="partner-link-create"),
    path("links/<uuid:pk>/toggle/", views.LinkToggleView.as_view(), name="link-toggle"),
    path("links/<uuid:pk>/qr.svg", views.LinkQRCodeView.as_view(), name="link-qr"),
]

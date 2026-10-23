from django.urls import path

from . import views

urlpatterns = [
    path("", views.ClientListView.as_view(), name="client-list"),
    path("<uuid:pk>/", views.ClientDetailView.as_view(), name="client-detail"),
    path(
        "<uuid:pk>/not-duplicate/",
        views.ClientDuplicateResolveView.as_view(),
        name="client-not-duplicate",
    ),
]

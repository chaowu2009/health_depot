from django.urls import path

from . import views

urlpatterns = [
    path("", views.TemplateListView.as_view(), name="form-list"),
    path("new/", views.TemplateCreateView.as_view(), name="form-create"),
    path("<uuid:pk>/", views.BuilderView.as_view(), name="form-builder"),
    path("<uuid:pk>/details/", views.MetaUpdateView.as_view(), name="form-meta"),
    path("<uuid:pk>/questions/add/", views.FieldAddView.as_view(), name="form-field-add"),
    path("<uuid:pk>/questions/reorder/", views.ReorderView.as_view(), name="form-reorder"),
    path(
        "<uuid:pk>/questions/<slug:key>/", views.FieldUpdateView.as_view(), name="form-field-update"
    ),
    path(
        "<uuid:pk>/questions/<slug:key>/delete/",
        views.FieldDeleteView.as_view(),
        name="form-field-delete",
    ),
]

from django.urls import path

from . import views

urlpatterns = [
    path("scheduling/", views.SchedulingView.as_view(), name="phase2-scheduling"),
    path("scheduling/book/", views.BookingView.as_view(), name="phase2-booking"),
    path("events/", views.EventView.as_view(), name="phase2-events"),
    path("communications/", views.CommunicationsView.as_view(), name="phase2-communications"),
    path("ehr/", views.EHRView.as_view(), name="phase2-ehr"),
    path("import/", views.ImportView.as_view(), name="client-import"),
]

from django.urls import path

from . import public_views

urlpatterns = [
    path("<slug:slug>/", public_views.intake, name="public-intake"),
    path("<slug:slug>/thanks/", public_views.intake_done, name="public-intake-done"),
]

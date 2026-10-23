from django.urls import path

from . import views

urlpatterns = [
    path("", views.InboxView.as_view(), name="referral-inbox"),
    path("new/", views.OutboundCreateView.as_view(), name="referral-create"),
    path("views/save/", views.SavedViewCreateView.as_view(), name="referral-view-save"),
    path(
        "views/<uuid:pk>/delete/", views.SavedViewDeleteView.as_view(), name="referral-view-delete"
    ),
    path("<uuid:pk>/", views.ReferralDetailView.as_view(), name="referral-detail"),
    path("<uuid:pk>/status/", views.StatusChangeView.as_view(), name="referral-status"),
    path("<uuid:pk>/assign/", views.AssignView.as_view(), name="referral-assign"),
    path("<uuid:pk>/comments/", views.CommentView.as_view(), name="referral-comment"),
    path("<uuid:pk>/messages/", views.MessageSendView.as_view(), name="referral-message"),
]

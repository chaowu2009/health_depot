"""Secure messaging between CCHD and partners, one thread per referral."""

from django.conf import settings
from django.db import models

from apps.accounts.access import MessageQuerySet, ReferralChildQuerySet
from apps.core.models import TimeStampedModel


class MessageThread(TimeStampedModel):
    referral = models.OneToOneField(
        "referrals.Referral", on_delete=models.CASCADE, related_name="thread"
    )
    participant_organizations = models.ManyToManyField(
        "organizations.Organization", related_name="message_threads"
    )

    objects = ReferralChildQuerySet.as_manager()

    def __str__(self) -> str:
        return f"Thread for {self.referral}"


class Message(TimeStampedModel):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body = models.TextField()
    attachment = models.FileField(upload_to="messages/", blank=True)  # via the S3 API
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="MessageReceipt", related_name="read_messages"
    )

    objects = MessageQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Message from {self.sender} at {self.created_at:%Y-%m-%d %H:%M}"


class MessageReceipt(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="unique_message_receipt")
        ]

    def __str__(self) -> str:
        return f"{self.user} read {self.message_id} at {self.read_at:%Y-%m-%d %H:%M}"

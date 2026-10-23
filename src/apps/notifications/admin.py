from django.contrib import admin

from .models import EmailOutbox, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("verb", "recipient", "read_at", "created_at")
    list_filter = ("verb",)


@admin.register(EmailOutbox)
class EmailOutboxAdmin(admin.ModelAdmin):
    list_display = ("subject", "to_email", "status", "attempts", "sent_at", "created_at")
    list_filter = ("status",)

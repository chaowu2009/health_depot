from django.contrib import admin

from .models import Message, MessageThread


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("sender", "body", "created_at")
    readonly_fields = ("created_at",)


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("referral", "created_at")
    inlines = [MessageInline]

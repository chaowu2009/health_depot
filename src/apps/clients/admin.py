from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "date_of_birth", "zip_code", "created_at")
    search_fields = ("last_name", "first_name")
    list_filter = ("preferred_language",)
    raw_id_fields = ("possible_duplicate_of",)

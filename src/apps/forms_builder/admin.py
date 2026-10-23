from django.contrib import admin

from .models import FormTemplate


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "version",
        "program",
        "owner_organization",
        "is_published",
        "is_system_template",
    )
    list_filter = ("is_published", "is_system_template")
    search_fields = ("name",)

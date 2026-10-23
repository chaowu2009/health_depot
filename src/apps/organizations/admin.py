from django.contrib import admin

from .models import Division, Organization, PartnerProgram, Program


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "org_type", "contact_name", "is_active")
    list_filter = ("org_type", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization")


class PartnerProgramInline(admin.TabularInline):
    model = PartnerProgram
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "division", "overdue_after_days", "is_active")
    list_filter = ("division", "is_active")
    search_fields = ("name", "code")
    inlines = [PartnerProgramInline]

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserProgramAccess


class UserProgramAccessInline(admin.TabularInline):
    model = UserProgramAccess
    extra = 0
    autocomplete_fields = ["program"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ("email", "first_name", "last_name", "role", "organization", "is_active")
    list_filter = ("role", "organization", "is_active")
    search_fields = ("email", "first_name", "last_name")
    inlines = [UserProgramAccessInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "title", "phone", "organization")}),
        ("Access", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "role", "organization", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ("last_login", "date_joined")

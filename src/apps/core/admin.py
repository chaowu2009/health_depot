from django.contrib import admin

from .models import SavedView, SchedulerLock


@admin.register(SchedulerLock)
class SchedulerLockAdmin(admin.ModelAdmin):
    list_display = ("job_name", "locked_by", "locked_until")


@admin.register(SavedView)
class SavedViewAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "view_type", "updated_at")
    list_filter = ("view_type",)

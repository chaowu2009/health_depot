from django.contrib import admin

from .models import Referral, ReferralComment, ReferralEvent, ReferralLink


@admin.register(ReferralLink)
class ReferralLinkAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "partner",
        "program",
        "slug",
        "is_active",
        "visit_count",
        "submission_count",
    )
    list_filter = ("is_active", "program")
    readonly_fields = ("slug", "visit_count", "submission_count")


class ReferralEventInline(admin.TabularInline):
    model = ReferralEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "event_type",
        "from_status",
        "to_status",
        "actor",
        "actor_organization",
        "note",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        "reference_number",
        "program",
        "status",
        "priority",
        "receiving_organization",
        "created_at",
    )
    list_filter = ("status", "priority", "program", "direction")
    search_fields = ("reference_number",)
    raw_id_fields = ("client", "case", "source_link")
    inlines = [ReferralEventInline]


@admin.register(ReferralComment)
class ReferralCommentAdmin(admin.ModelAdmin):
    list_display = ("referral", "author", "created_at")

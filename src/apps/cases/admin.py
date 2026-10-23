from django.contrib import admin

from .models import CarePlanGoal, Case, CaseDocument, CaseNote, CaseTask


class GoalInline(admin.TabularInline):
    model = CarePlanGoal
    extra = 0


class TaskInline(admin.TabularInline):
    model = CaseTask
    extra = 0
    fields = ("title", "assigned_to", "due_date", "completed_at", "priority")


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("case_number", "program", "status", "case_manager", "admitted_at")
    list_filter = ("status", "program")
    search_fields = ("case_number",)
    raw_id_fields = ("client",)
    inlines = [GoalInline, TaskInline]


@admin.register(CaseNote)
class CaseNoteAdmin(admin.ModelAdmin):
    list_display = ("case", "note_type", "author", "created_at")


@admin.register(CaseDocument)
class CaseDocumentAdmin(admin.ModelAdmin):
    list_display = ("filename", "case", "document_type", "uploaded_by", "created_at")

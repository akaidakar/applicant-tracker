from django.contrib import admin

from .models import Application, Note, StageEntry


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    readonly_fields = ("created_at",)


class StageEntryInline(admin.TabularInline):
    model = StageEntry
    extra = 0
    readonly_fields = ("entered_at",)
    show_change_link = True


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "submitted_at", "stage", "receipt")
    list_filter = ("stage",)
    search_fields = ("name", "email", "receipt")
    ordering = ("-submitted_at", "-id")
    readonly_fields = ("receipt", "stage")
    inlines = [StageEntryInline]


@admin.register(StageEntry)
class StageEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "stage", "entered_at")
    list_filter = ("stage",)
    inlines = [NoteInline]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("id", "stage_entry", "created_at")

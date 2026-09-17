from django.contrib import admin

from .models import Application, Note, StageEntry, make_receipt


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    readonly_fields = ("created_at",)


class StageEntryInline(admin.TabularInline):
    """Read-only: `Application.enter_stage()` is the only writer, so
    Application.stage and the entries can't drift apart."""

    model = StageEntry
    extra = 0
    fields = ("stage", "entered_at")
    readonly_fields = ("stage", "entered_at")
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "submitted_at", "stage", "receipt")
    list_filter = ("stage",)
    search_fields = ("name", "email", "receipt")
    ordering = ("-submitted_at", "-id")
    readonly_fields = ("receipt", "stage")
    inlines = [StageEntryInline]

    def save_model(self, request, obj, form, change):
        # The add form can't fill the read-only fields. Without this the row
        # saves with an empty receipt, and the second one hits the unique
        # constraint. Issue a receipt and the first stage entry like the
        # submission endpoint does.
        if not obj.receipt:
            obj.receipt = make_receipt(obj.submitted_at)
        super().save_model(request, obj, form, change)
        if not change:
            obj.enter_stage(obj.stage)


@admin.register(StageEntry)
class StageEntryAdmin(admin.ModelAdmin):
    """Exists so notes can be added to a past stage. The entry itself is read-only."""

    list_display = ("id", "application", "stage", "entered_at")
    list_filter = ("stage",)
    readonly_fields = ("application", "stage", "entered_at")
    inlines = [NoteInline]

    def has_add_permission(self, request):
        return False


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("id", "stage_entry", "created_at")

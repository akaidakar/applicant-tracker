import secrets
from datetime import datetime, timezone

from django.db import models


class Stage(models.TextChoices):
    NEW = "new", "New"
    PHONE_SCREEN_SCHEDULED = "phone_screen_scheduled", "Phone screen scheduled"
    INTERVIEW_SCHEDULED = "interview_scheduled", "Interview scheduled"
    HIRED = "hired", "Hired"
    REJECTED = "rejected", "Rejected"


# The order of the choices is the order of the pipeline.
STAGE_ORDER = list(Stage.values)


def allowed_next_stages(current):
    """Stages an application may move to from `current`: every later one.

    Moves only go forward, as the task requires. Rejected is last, so nothing
    leaves it; Hired can still become Rejected. The stage endpoint validates
    with this and the detail response lists it, so the rule lives in one place.
    """
    return STAGE_ORDER[STAGE_ORDER.index(current) + 1:]


def make_receipt(moment=None):
    """The gist's receipt format: thank-you-from-b12-<utc iso ms Z>-<12 hex>."""
    moment = moment or datetime.now(timezone.utc)
    stamp = moment.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    return f"thank-you-from-b12-{stamp.replace('+00:00', 'Z')}-{secrets.token_hex(6)}"


class Application(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True)
    resume_link = models.URLField()
    repository_link = models.URLField()
    action_run_link = models.URLField()
    submitted_at = models.DateTimeField(db_index=True)  # payload timestamp
    receipt = models.CharField(max_length=100, unique=True)
    # Duplicates the latest StageEntry so stage checks and filters need no
    # subquery. Written only inside the same transaction as the new entry.
    stage = models.CharField(max_length=32, choices=Stage.choices, default=Stage.NEW)

    class Meta:
        indexes = [
            # The list page filters by stage and sorts newest first. One index
            # serves both, and a stage-only filter uses its leading column.
            models.Index(fields=["stage", "-submitted_at", "-id"], name="apply_app_stage_newest_idx"),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}> ({self.receipt})"

    def current_entry(self):
        """The StageEntry for the current stage.

        Every code path that sets `stage` also creates an entry, but a row made
        by hand (admin, shell) may have none. Create it then, so a note always
        has a stage to attach to.
        """
        entry = self.stage_entries.order_by("-id").first()
        if entry is None:
            entry = self.stage_entries.create(stage=self.stage)
        return entry


class StageEntry(models.Model):
    """One row per stage the applicant entered. The latest one is the current stage.

    Entries order by id, the order the moves were made, rather than by
    `entered_at`. The date is for display; seeded or hand-edited dates must
    not change which entry counts as current.
    """

    application = models.ForeignKey(
        Application, related_name="stage_entries", on_delete=models.CASCADE
    )
    stage = models.CharField(max_length=32, choices=Stage.choices)
    entered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.application_id}: {self.stage} @ {self.entered_at}"


class Note(models.Model):
    stage_entry = models.ForeignKey(
        StageEntry, related_name="notes", on_delete=models.CASCADE
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.content[:50]

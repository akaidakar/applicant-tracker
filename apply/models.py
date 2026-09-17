import secrets
from datetime import datetime, timezone

from django.db import models, transaction
from django.db.models.functions import Upper


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


class ApplicationManager(models.Manager):
    def submit(self, *, submitted_at, receipt=None, **fields):
        """Create an application at New with its first stage entry.

        Every code path that makes an application goes through here, so a row
        never exists without the entry that `current_entry()` reads.
        """
        with transaction.atomic():
            application = self.create(
                submitted_at=submitted_at,
                receipt=receipt or make_receipt(submitted_at),
                stage=Stage.NEW,
                **fields,
            )
            application.enter_stage(Stage.NEW)
        return application


class Application(models.Model):
    objects = ApplicationManager()

    name = models.CharField(max_length=255)
    email = models.EmailField()
    resume_link = models.URLField()
    repository_link = models.URLField()
    action_run_link = models.URLField()
    submitted_at = models.DateTimeField()  # payload timestamp
    receipt = models.CharField(max_length=100, unique=True)
    # Duplicates the latest StageEntry so stage checks and filters need no
    # subquery. `objects.submit()` sets it at New and `enter_stage()` is the
    # only later writer, so the two can't drift.
    stage = models.CharField(max_length=32, choices=Stage.choices, default=Stage.NEW)

    class Meta:
        indexes = [
            # The list sorts newest first: ORDER BY submitted_at DESC, id DESC.
            # Both columns are in the index so Postgres needs no sort step.
            models.Index(fields=["-submitted_at", "-id"], name="apply_app_newest_idx"),
            # The same sort with a stage filter in front of it.
            models.Index(fields=["stage", "-submitted_at", "-id"], name="apply_app_stage_newest_idx"),
            # The email filter is case-insensitive. Postgres compiles iexact
            # to UPPER(email) = UPPER(%s), which this index serves.
            models.Index(Upper("email"), name="apply_app_email_upper_idx"),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}> ({self.receipt})"

    def enter_stage(self, stage):
        """Record that the applicant is now at `stage` and return the new entry.

        The only place that changes `stage` or creates a StageEntry. Callers
        validate the transition first and hold the row lock when it matters.
        The column is saved only when it changes, so entering the stage a
        fresh row already has costs one INSERT.
        """
        if self.stage != stage:
            self.stage = stage
            self.save(update_fields=["stage"])
        return self.stage_entries.create(stage=stage)

    def current_entry(self):
        """The StageEntry for the current stage.

        A row made by hand in the shell may have none. Create it then, so a
        note always has a stage to attach to.
        """
        entry = self.stage_entries.order_by("-id").first()
        if entry is None:
            entry = self.enter_stage(self.stage)
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

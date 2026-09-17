"""Create fake applications for local development.

Each application gets a random submission date in the last 90 days, a random
walk through the stages, one StageEntry per stage entered, and a few notes.
Application.stage always equals the latest entry, the same invariant the
stage endpoint keeps.
"""

import random
import secrets
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apply.models import STAGE_ORDER, Application, Note, Stage, StageEntry

FIRST_NAMES = ["Ada", "Grace", "Linus", "Margaret", "Dennis", "Barbara", "Ken", "Radia",
               "Guido", "Frances", "Tim", "Hedy", "Alan", "Katherine", "Donald", "Mary"]
LAST_NAMES = ["Lovelace", "Hopper", "Torvalds", "Hamilton", "Ritchie", "Liskov", "Thompson",
              "Perlman", "van Rossum", "Allen", "Berners-Lee", "Lamarr", "Turing", "Johnson",
              "Knuth", "Shaw"]
NOTES = [
    "Strong take-home, clean signing code.",
    "Asked good questions about idempotency.",
    "Scheduled with the platform team.",
    "Follow up on the retry discussion.",
    "References checked.",
    "Needs more depth on databases.",
]


def make_receipt(moment):
    stamp = moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return f"thank-you-from-b12-{stamp}-{secrets.token_hex(6)}"


def random_path(rng):
    """A forward-only walk through the stages, sometimes skipping, sometimes ending early."""
    path = [Stage.NEW]
    while path[-1] != Stage.REJECTED and rng.random() < 0.6:
        path.append(rng.choice(STAGE_ORDER[STAGE_ORDER.index(path[-1]) + 1:]))
    return path


class Command(BaseCommand):
    help = "Seed the database with fake applications."

    def add_arguments(self, parser):
        parser.add_argument("count", nargs="?", type=int, default=100)
        parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible data.")
        parser.add_argument(
            "--if-empty", action="store_true",
            help="Do nothing when applications already exist. Used on deploy start.",
        )

    @transaction.atomic
    def handle(self, count, seed, if_empty, **options):
        if if_empty and Application.objects.exists():
            self.stdout.write("Applications exist; not seeding.")
            return
        rng = random.Random(seed)
        now = timezone.now()
        for i in range(count):
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            slug = f"{first}.{last}".lower().replace(" ", "")
            submitted_at = now - timedelta(days=rng.uniform(0, 90))
            application = Application.objects.create(
                name=f"{first} {last}",
                email=f"{slug}{i}@example.com",
                resume_link=f"https://example.com/resumes/{slug}.pdf",
                repository_link=f"https://github.com/{slug}/application-submitter",
                action_run_link=f"https://github.com/{slug}/application-submitter/actions/runs/{1000 + i}",
                submitted_at=submitted_at,
                receipt=make_receipt(submitted_at),
            )
            entered_at = submitted_at
            for stage in random_path(rng):
                entry = StageEntry.objects.create(application=application, stage=stage)
                # auto_now_add ignores a passed value, so backdate after creating.
                StageEntry.objects.filter(pk=entry.pk).update(entered_at=entered_at)
                for _ in range(rng.choice([0, 0, 1, 2])):
                    note = Note.objects.create(stage_entry=entry, content=rng.choice(NOTES))
                    Note.objects.filter(pk=note.pk).update(
                        created_at=entered_at + timedelta(hours=rng.uniform(1, 48))
                    )
                application.stage = stage
                entered_at += timedelta(days=rng.uniform(1, 7))
            application.save(update_fields=["stage"])
        self.stdout.write(self.style.SUCCESS(f"Created {count} applications."))

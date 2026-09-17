from django.db import migrations, models


class Migration(migrations.Migration):
    """Replace the single-column stage index with one that matches the list query.

    The list runs `WHERE stage = ? ORDER BY submitted_at DESC, id DESC`. A
    composite index serves the filter and the sort in one scan, and a
    stage-only filter still uses its leading column, so the index from 0002
    is redundant.
    """

    dependencies = [
        ("apply", "0003_stage_entry_ordering"),
    ]

    operations = [
        migrations.AlterField(
            model_name="application",
            name="stage",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("phone_screen_scheduled", "Phone screen scheduled"),
                    ("interview_scheduled", "Interview scheduled"),
                    ("hired", "Hired"),
                    ("rejected", "Rejected"),
                ],
                default="new",
                max_length=32,
            ),
        ),
        migrations.AddIndex(
            model_name="application",
            index=models.Index(
                fields=["stage", "-submitted_at", "-id"], name="apply_app_stage_newest_idx"
            ),
        ),
    ]

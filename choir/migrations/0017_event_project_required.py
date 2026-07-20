import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Only safe to apply once 0016_backfill_default_project has actually run
    and every Event row has a project assigned - see the deploy checklist
    in .claude/plans/fluffy-herding-creek.md (verify
    Event.objects.filter(project__isnull=True).count() == 0 in production
    before this migration is applied there).
    """

    dependencies = [
        ("choir", "0016_backfill_default_project"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="project",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="choir.project",
            ),
        ),
    ]

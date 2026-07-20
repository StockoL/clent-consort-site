import django.db.models.deletion
from django.db import migrations, models


def backfill_project_repertoire(apps, schema_editor):
    """
    For each Project, set its repertoire to the union of every piece
    attached to any of its Events via the (about-to-be-removed)
    Event.pieces field. Zero data loss even if two events within the
    same project previously had different piece lists - they merge into
    one project-level list rather than either being silently dropped.

    Runs after AddField (Project.repertoire exists) but before RemoveField
    (Event.pieces / its reverse "events" relation still exists) below -
    both are guaranteed by this migration's operations being applied in
    list order.
    """
    Project = apps.get_model("choir", "Project")
    Repertoire = apps.get_model("choir", "Repertoire")

    for project in Project.objects.all():
        pieces = Repertoire.objects.filter(events__project=project).distinct()
        project.repertoire.set(pieces)


def noop_reverse(apps, schema_editor):
    # No-op: Event.pieces is gone by the time this migration's reverse
    # would run (RemoveField happens in this same migration), so there's
    # no field left to backfill data into on the way back down.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("choir", "0017_event_project_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="repertoire",
            field=models.ManyToManyField(
                blank=True, related_name="projects", to="choir.repertoire"
            ),
        ),
        migrations.RunPython(backfill_project_repertoire, noop_reverse),
        migrations.RemoveField(
            model_name="event",
            name="pieces",
        ),
    ]

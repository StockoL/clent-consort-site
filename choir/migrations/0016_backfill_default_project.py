from django.db import migrations


def backfill_default_project(apps, schema_editor):
    """
    Every Event created before this migration has project=None (the field
    was only just added, nullable, in 0015). Assign them all to one
    archived "legacy" Project so 0017 can safely make the field required.

    Uses .update() rather than a per-row loop - a single UPDATE statement
    (cheap regardless of table size) that deliberately does NOT fire
    post_save, so choir/signals.py's auto_add_existing_users_to_new_event
    doesn't re-run for every historical event.
    """
    Project = apps.get_model("choir", "Project")
    Event = apps.get_model("choir", "Event")

    legacy_project, _ = Project.objects.get_or_create(
        name="Prior to Project Tracking",
        defaults={"status": "ARCHIVED"},
    )
    Event.objects.filter(project__isnull=True).update(project=legacy_project)


def noop_reverse(apps, schema_editor):
    # No-op: this migration's reverse is only ever reached before 0017
    # makes the field required, so there's nothing that needs undoing -
    # leaving the legacy Project and its backfilled Events in place is
    # harmless and simpler than trying to un-assign them.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("choir", "0015_event_project_nullable"),
    ]

    operations = [
        migrations.RunPython(backfill_default_project, noop_reverse),
    ]

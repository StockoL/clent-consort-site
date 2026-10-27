"""
Broadcasts created before drafts existed were sent the moment they were
saved, so mark them SENT (0028 added status with a default of DRAFT). They
already have sent_at. They get no BroadcastDelivery rows; per-recipient
records start with the next broadcast. Reversing leaves the data as it is.
"""

from django.db import migrations


def mark_sent(apps, schema_editor):
    ChoirCommunication = apps.get_model("choir", "ChoirCommunication")
    ChoirCommunication.objects.filter(status="DRAFT", sent_at__isnull=False).update(status="SENT")


class Migration(migrations.Migration):
    dependencies = [
        ("choir", "0028_broadcast_drafts"),
    ]

    operations = [
        migrations.RunPython(mark_sent, migrations.RunPython.noop),
    ]

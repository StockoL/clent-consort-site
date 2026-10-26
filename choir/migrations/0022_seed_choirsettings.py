"""
Seed the single ChoirSettings row from the values that used to be hard-coded:
the term from settings.CURRENT_TERM, and the amount and bank details from the
member dashboard's subscription card. Idempotent (leaves an existing row
alone) and reversible (removes the row).
"""

from django.conf import settings
from django.db import migrations


def seed(apps, schema_editor):
    ChoirSettings = apps.get_model("choir", "ChoirSettings")
    ChoirSettings.objects.get_or_create(
        pk=1,
        defaults={
            # getattr: Build Order Phase 11 removes CURRENT_TERM, and this
            # migration still has to run on a fresh database after that.
            "current_term": getattr(settings, "CURRENT_TERM", "Autumn 2026"),
            "subscription_amount": 50,
            "bank_account_name": "Clent Consort",
            "bank_sort_code": "23-05-80",
            "bank_account_number": "58234028",
        },
    )


def unseed(apps, schema_editor):
    apps.get_model("choir", "ChoirSettings").objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("choir", "0021_choirsettings"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

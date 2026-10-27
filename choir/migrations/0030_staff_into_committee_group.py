"""
Before committee access stops honouring is_staff (Build Order Phase 11),
put every user who currently has it into the Committee group, so nobody's
access changes on the day. 0024 did this once in Phase 5; this catches
anyone given staff access since. Idempotent; reversing leaves the group as
it is (taking people out could lock someone out).
"""

from django.db import migrations

# Matches choir.permissions.COMMITTEE_GROUP (migrations keep their own copy)
COMMITTEE_GROUP = "Committee"


def add_staff(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")
    group, _ = Group.objects.get_or_create(name=COMMITTEE_GROUP)
    group.user_set.add(*User.objects.filter(is_staff=True, is_active=True))


class Migration(migrations.Migration):
    dependencies = [
        ("choir", "0029_mark_existing_broadcasts_sent"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(add_staff, migrations.RunPython.noop),
    ]

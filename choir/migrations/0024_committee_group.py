"""
Create the "Committee" auth Group and put every current staff user in it,
so committee access carries over unchanged when is_committee() starts
checking the group (Build Order Phase 5). Idempotent: re-running adds
nobody twice. Reversible: removing it deletes the group, which also drops
its memberships.
"""

from django.db import migrations

# Matches choir.permissions.COMMITTEE_GROUP; migrations keep their own copy
# so they still run if that module changes later.
COMMITTEE_GROUP = "Committee"


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")
    group, _ = Group.objects.get_or_create(name=COMMITTEE_GROUP)
    group.user_set.add(*User.objects.filter(is_staff=True))


def remove_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=COMMITTEE_GROUP).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("choir", "0023_memberprofile_is_singer"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_group, remove_group),
    ]

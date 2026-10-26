"""
Local development seed data. NEVER run this in production - it creates
users with a shared, publicly documented password. It refuses to run
unless DEBUG is True.

Creates (idempotently - safe to re-run):
  - one committee user and three members across voice parts, each with a
    verified email address so allauth lets them log in
  - one ACTIVE project with three events (one past, two future) and two
    repertoire pieces with one learning asset each
  - one PLANNING project with an open availability poll
"""

from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from choir.models import AvailabilityPoll, Event, LearningAsset, Project, Repertoire
from choir.permissions import COMMITTEE_GROUP

DEV_PASSWORD = "choir-dev-password"

USERS = [
    # username, first name, last name, voice part, committee
    ("committee", "Clara", "Committee", "S", True),
    ("soprano", "Sam", "Soprano", "S", False),
    ("alto", "Alex", "Alto", "A", False),
    ("tenor", "Toby", "Tenor", "T", False),
]

ACTIVE_PROJECT = "Dev Seed: Active Project"
PLANNING_PROJECT = "Dev Seed: Planning Project"


class Command(BaseCommand):
    help = "Create local development seed data. Refuses to run unless DEBUG is True."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_dev_data only runs with DEBUG=True. It must never run in production."
            )

        with transaction.atomic():
            # Users first, so the new-Event signal backfills their RSVPs below.
            for username, first, last, voice, committee in USERS:
                self._seed_user(username, first, last, voice, committee)
            self._seed_active_project()
            self._seed_planning_project()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed data ready. Log in as committee@example.com (or soprano@, alto@, "
                f"tenor@) with password '{DEV_PASSWORD}'."
            )
        )

    def _seed_user(self, username, first, last, voice, committee):
        email = f"{username}@example.com"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first,
                "last_name": last,
                "is_staff": committee,
            },
        )
        if created:
            user.set_password(DEV_PASSWORD)
            user.save()
            # The post_save signal creates the profile; fill in the voice part.
            user.profile.voice_part = voice
            user.profile.save()
        if committee:
            # Committee access comes from the group (choir.permissions)
            user.groups.add(Group.objects.get_or_create(name=COMMITTEE_GROUP)[0])
        EmailAddress.objects.get_or_create(
            user=user, email=email, defaults={"verified": True, "primary": True}
        )

    def _seed_active_project(self):
        project, created = Project.objects.get_or_create(
            name=ACTIVE_PROJECT, defaults={"status": "ACTIVE"}
        )
        if not created:
            return

        now = timezone.now()
        Event.objects.create(
            project=project, event_type="REH", date_time=now - timedelta(days=7)
        )
        Event.objects.create(
            project=project, event_type="REH", date_time=now + timedelta(days=7)
        )
        Event.objects.create(
            project=project,
            event_type="RES",
            date_time=now + timedelta(days=21),
            location="Worcester Cathedral",
        )

        pieces = [
            ("Byrd", "Ave verum corpus", "SOP", "Soprano practice track"),
            ("Tallis", "If ye love me", "ALL", "PDF score"),
        ]
        for composer, title, part, asset_name in pieces:
            piece = Repertoire.objects.create(composer=composer, title=title)
            project.repertoire.add(piece)
            LearningAsset.objects.create(
                repertoire=piece,
                voice_part=part,
                asset_name=asset_name,
                external_url="https://www.youtube.com/",
            )

    def _seed_planning_project(self):
        project, created = Project.objects.get_or_create(
            name=PLANNING_PROJECT, defaults={"status": "PLANNING"}
        )
        if not created:
            return

        AvailabilityPoll.objects.create(
            project=project,
            question="Are you available for a weekend residency next spring?",
            proposed_date=(timezone.now() + timedelta(days=150)).date(),
            is_open=True,
        )

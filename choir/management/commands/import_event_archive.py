"""
Import the choir's past performances from the old static Events page
(choir/templates/choir/events.html) as public Event rows, so the
database-driven Events page (Build Order Phase 9) has its history.

Run once on production after deploying:  python manage.py import_event_archive
Safe to re-run: an event already present (same month and location) is
skipped. --dry-run lists what would be created without saving anything.

Dates are the visible month and year from the static page (its machine-
readable datetime attributes were wrong in places); only month and year are
known, so each event is stored at midday on the 1st and the public page
shows month and year for past events.

Projects: the two recent performances with repertoire get a project each
(their repertoire is what the "Recent performances" cards list); the rest
are grouped into one archived project per year. Events are created with
bulk_create, which skips the signal that gives every singer an RSVP.

Not imported: the upcoming Ewelme Evensong (March 2027). Upcoming events
come from the committee's own schedule, marked public on the event edit
page.
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from choir.models import Event, Project, Repertoire

# (year, month, public title, location)
ARCHIVE = [
    (2025, 10, "Choral Eucharist and Evensong", "Carlisle Cathedral"),
    (2025, 4, "Choral Eucharist and Evensong", "Exeter Cathedral"),
    (2024, 11, "Evensong", "Rochester Cathedral"),
    (2024, 4, "Evensong", "Hereford Cathedral"),
    (2023, 7, "Whallet Wedding", "Clent"),
    (2022, 12, "Christmas Carols", "Hagley Hall"),
    (2022, 10, "Sung Services and Choral Recital", "Lindisfarne Weekend"),
    (2022, 6, "Flower Festival Evensong", "Clent"),
    (2022, 2, "Evensong", "St Albans"),
    (2021, 12, "Carol Service", "Clent"),
    (2019, 10, "Sung Services", "St Edmundsbury Cathedral Weekend"),
    (2019, 3, "Sung Services and Choral Recital", "St David's Cathedral (Pembrokeshire) Weekend"),
    (2018, 10, "Evensong", "Leicester Cathedral"),
    (2018, 7, "Choral Compline", "Tardebigge"),
    (2018, 4, "Sung Services", "Wells Cathedral Weekend"),
    (2017, 10, "Evensong", "Derby Cathedral"),
    (2017, 3, "Evensong", "Southwark Cathedral"),
    (2016, 10, "Sung Services", "Salisbury Cathedral Weekend"),
    (2016, 3, "Evensong", "Bristol Cathedral"),
    (2015, 12, "Evensong", "Tardebigge"),
    (2015, 4, "Evensong", "Bath Abbey"),
    (2014, 11, "Evensong", "Sherborne Abbey"),
    (2014, 3, "Evensong", "Tardebigge"),
    (2013, 11, "Clent Accord", "Clent"),
    (2013, 4, "Evensong", "Lichfield Cathedral"),
    (2012, 11, "Sung Services", "Peterborough Cathedral Weekend"),
    (2012, 6, "Inaugural Evensong", "Belbroughton Church"),
]

# Recent performances with their repertoire: (year, month, title, location,
# project name, [(composer, title), ...])
RECENT = [
    (
        2026, 9, "Choral Evensong", "St Leonard's Church, Clent",
        "Clent Evensong, September 2026",
        [
            ("Ayleward", "Responses"),
            ("Atkins", "Magnificat and Nunc Dimittis in G"),
            ("Elgar", "Light of the World"),
        ],
    ),
    (
        2026, 3, "Choral Eucharist and Evensong", "St Lawrence's Church, Ludlow",
        "Ludlow, March 2026",
        [
            ("Stanford", "Communion Service in C"),
            ("Elgar", "O salutaris hostia in F"),
            ("John IV of Portugal", "Crux fidelis"),
            ("Radcliffe", "Responses"),
            ("Aston", "Magnificat and Nunc Dimittis in F (No. 2)"),
            ("Haydn", "Insanae et vanae curae"),
        ],
    ),
]


def month_start(year, month):
    return timezone.make_aware(datetime(year, month, 1, 12, 0))


class Command(BaseCommand):
    help = "Import past performances from the old static Events page as public events."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List what would be created; save nothing.")

    def handle(self, *args, dry_run=False, **options):
        to_create = []  # (project name, pieces, year, month, title, location)

        for year, month, title, location, project_name, pieces in RECENT:
            to_create.append((project_name, pieces, year, month, title, location))
        for year, month, title, location in ARCHIVE:
            to_create.append((f"Performance archive {year}", [], year, month, title, location))

        created = skipped = 0
        with transaction.atomic():
            new_events = []
            for project_name, pieces, year, month, title, location in to_create:
                when = month_start(year, month)
                if Event.objects.filter(
                    date_time__year=year, date_time__month=month, location=location
                ).exists():
                    skipped += 1
                    continue

                label = f"{when:%B %Y}  {title}, {location}"
                if dry_run:
                    self.stdout.write(f"would create: {label}  [{project_name}]")
                    created += 1
                    continue

                project, _ = Project.objects.get_or_create(
                    name=project_name,
                    defaults={"status": "ARCHIVED", "start_date": when.date(), "end_date": when.date()},
                )
                for composer, piece_title in pieces:
                    piece, _ = Repertoire.objects.get_or_create(composer=composer, title=piece_title)
                    project.repertoire.add(piece)

                new_events.append(
                    Event(
                        project=project,
                        event_type="RES",
                        date_time=when,
                        location=location,
                        is_public=True,
                        public_title=title,
                    )
                )
                created += 1

            if not dry_run:
                # bulk_create skips post_save, so no RSVP rows are created
                # for performances that happened years ago.
                Event.objects.bulk_create(new_events)

        verb = "Would create" if dry_run else "Created"
        self.stdout.write(self.style.SUCCESS(f"{verb} {created} public events; {skipped} already present."))

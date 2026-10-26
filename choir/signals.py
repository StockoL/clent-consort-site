from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Attendance, Event
from .permissions import is_singer


# 1. THE NEW SINGER TRIGGER
@receiver(post_save, sender=User)
def auto_add_new_user_to_future_events(sender, instance, created, **kwargs):
    """
    When a brand new User is created, automatically generate a 'PENDING'
    RSVP for every event that hasn't happened yet - singers only (a new
    profile is a singer by default; see MemberProfile.is_singer).
    """
    if created and is_singer(instance):
        # Fetch all events happening from this exact moment onward
        upcoming_events = Event.objects.filter(date_time__gte=timezone.now())

        # Build the database rows in memory
        attendances_to_create = [
            Attendance(user=instance, event=event, status="PENDING")
            for event in upcoming_events
        ]

        # bulk_create writes them to the SQL database all at once for high performance
        Attendance.objects.bulk_create(attendances_to_create)


# 2. THE NEW EVENT TRIGGER
@receiver(post_save, sender=Event)
def auto_add_existing_users_to_new_event(sender, instance, created, **kwargs):
    """
    When the Director creates a new Event in the admin panel,
    automatically generate a 'PENDING' RSVP for every active singer.

    This is the single canonical place this happens (a second, duplicate
    receiver used to live in choir/models.py and both fired on every new
    Event, colliding on Attendance.unique_together=("user", "event")).
    A superuser can also be an active choir member, so membership is
    determined by is_active and MemberProfile.is_singer, not by
    account-privilege flags.
    """
    if created:
        active_singers = User.objects.filter(is_active=True, profile__is_singer=True)

        attendances_to_create = [
            Attendance(user=singer, event=instance, status="PENDING")
            for singer in active_singers
        ]

        # ignore_conflicts as defense-in-depth against any other future
        # source of Attendance rows for the same (user, event) pair.
        Attendance.objects.bulk_create(attendances_to_create, ignore_conflicts=True)

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Attendance, Event


# 1. THE NEW SINGER TRIGGER
@receiver(post_save, sender=User)
def auto_add_new_user_to_future_events(sender, instance, created, **kwargs):
    """
    When a brand new User is created, automatically generate a 'PENDING'
    RSVP for every event that hasn't happened yet.
    """
    if created:
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
    """
    if created:
        # Exclude superusers/admins if they aren't actually singing in the choir
        # Adjust this filter if you have a specific way of denoting active singers!
        active_singers = User.objects.filter(is_active=True, is_superuser=False)

        attendances_to_create = [
            Attendance(user=singer, event=instance, status="PENDING")
            for singer in active_singers
        ]

        Attendance.objects.bulk_create(attendances_to_create)

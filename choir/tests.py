from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Attendance, ChoirCommunication, Event


class AttendanceAutoCreationTests(TestCase):
    """Guards against choir/models.py and choir/signals.py both firing
    post_save on Event and colliding on Attendance.unique_together."""

    def test_new_event_creates_exactly_one_attendance_per_active_user(self):
        active_users = [
            User.objects.create_user(username=f"member{i}", password="pw")
            for i in range(3)
        ]
        User.objects.create_user(username="inactive", password="pw", is_active=False)

        event = Event.objects.create(
            date_time=timezone.now() + timedelta(days=7),
            location="Test Venue",
        )

        self.assertEqual(
            Attendance.objects.filter(event=event).count(), len(active_users)
        )
        for user in active_users:
            self.assertTrue(Attendance.objects.filter(event=event, user=user).exists())


class CommitteePermissionModelTests(TestCase):
    """Encodes the confirmed policy: committee_hub and committee_documents
    are open (read) to any active member, while financials, emergency
    roster, broadcast and scheduling stay committee/staff-only."""

    def setUp(self):
        self.member = User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

    def test_hub_and_documents_open_to_any_active_member(self):
        for name in ("committee_hub", "committee_documents"):
            response = self.client.get(reverse(name))
            self.assertEqual(
                response.status_code, 200, f"{name} should be open to any active member"
            )

    def test_sensitive_committee_views_blocked_for_non_staff(self):
        for name in (
            "committee_financials",
            "committee_emergency",
            "committee_broadcast",
            "committee_schedule",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(
                response.status_code, 302, f"{name} should redirect non-staff members"
            )


class ChoirCommunicationSendTests(TestCase):
    def test_save_does_not_crash_with_no_matching_recipients(self):
        # No users have voice_part "S" assigned, so recipients is empty.
        ChoirCommunication.objects.create(
            audience="SOP",
            subject="Test subject",
            message="<p>Hello</p>",
        )


class GiftAidPageTests(TestCase):
    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

    def test_giftaid_page_loads_for_logged_in_member(self):
        response = self.client.get(reverse("giftaid"))
        self.assertEqual(response.status_code, 200)

    def test_successful_submission_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("giftaid"),
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "address_line_1": "1 Church Lane",
                "town_city": "Stourbridge",
                "postcode": "DY9 1AA",
                "consent_given": "on",
            },
        )
        self.assertRedirects(response, reverse("members"))

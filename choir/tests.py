from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Attendance, ChoirCommunication, Enquiry, Event


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

    def test_resubmission_does_not_crash(self):
        # GiftAidDeclaration.member is a OneToOneField - a second submission
        # used to hit that uniqueness constraint directly (IntegrityError,
        # uncaught -> 500) instead of being handled gracefully. Covers the
        # stale-tab/double-submit case the template's {% if existing_declaration
        # %} guard doesn't protect against server-side.
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "address_line_1": "1 Church Lane",
            "town_city": "Stourbridge",
            "postcode": "DY9 1AA",
            "consent_given": "on",
        }
        self.client.post(reverse("giftaid"), payload)
        response = self.client.post(reverse("giftaid"), payload)
        self.assertIn(response.status_code, (200, 302))


class ContactFormTests(TestCase):
    """Guards against contact_view redirecting (losing the user's input and
    field-specific errors) instead of re-rendering the bound form on a
    validation failure."""

    def test_invalid_enquiry_rerenders_with_errors_and_preserves_input(self):
        response = self.client.post(
            reverse("contact"),
            {
                "name": "Jane Doe",
                "email": "not-an-email",
                "subject": "general",
                "message": "Hello there",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["enquiry_form"].is_valid())
        self.assertEqual(
            response.context["enquiry_form"]["name"].value(), "Jane Doe"
        )
        self.assertFalse(Enquiry.objects.exists())

    def test_valid_enquiry_still_redirects(self):
        response = self.client.post(
            reverse("contact"),
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "subject": "general",
                "message": "Hello there",
            },
        )
        self.assertRedirects(response, reverse("contact"))
        self.assertTrue(Enquiry.objects.filter(email="jane@example.com").exists())


class CommitteeBroadcastTests(TestCase):
    """Guards against choir/views.py's committee_broadcast setting a
    nonexistent 'sent_by' attribute instead of the model's real 'author'
    field, which silently left every frontend-sent broadcast unattributed."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="committee", password="pw", is_staff=True
        )
        self.client.login(username="committee", password="pw")

    def test_broadcast_records_author(self):
        self.client.post(
            reverse("committee_broadcast"),
            {
                "audience": "ALL",
                "subject": "Rehearsal moved",
                "message": "<p>This week's rehearsal moves to Tuesday.</p>",
            },
        )
        broadcast = ChoirCommunication.objects.latest("sent_at")
        self.assertEqual(broadcast.author, self.staff)


class EmailManagementTests(TestCase):
    """Guards against the Settings page updating User.email directly
    without allauth's EmailAddress model ever knowing - since login is by
    email (ACCOUNT_LOGIN_METHODS = {"email"}), that used to risk a member
    locking themselves out by "changing" their email in Settings. Email
    changes now go through allauth's own verified-change flow instead."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="member", password="pw", email="original@example.com"
        )
        EmailAddress.objects.create(
            user=self.user,
            email="original@example.com",
            verified=True,
            primary=True,
        )
        self.client.login(username="member", password="pw")

    def test_settings_form_no_longer_accepts_an_email_field(self):
        response = self.client.post(
            reverse("settings"),
            {"first_name": "Jane", "last_name": "Doe"},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jane")
        # Untouched - no email field exists on this form to change it via.
        self.assertEqual(self.user.email, "original@example.com")

    def test_manage_email_page_loads(self):
        response = self.client.get(reverse("account_email"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "original@example.com")

    def test_adding_a_new_email_creates_an_unverified_address_without_touching_user_email(self):
        self.client.post(
            reverse("account_email"),
            {"action_add": "", "email": "new@example.com"},
        )
        new_address = EmailAddress.objects.get(email="new@example.com")
        self.assertFalse(new_address.verified)
        self.assertFalse(new_address.primary)
        # User.email must not change until the new address is verified
        # and explicitly made primary - that's the whole point of the fix.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "original@example.com")

from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Attendance,
    AvailabilityPoll,
    AvailabilityResponse,
    ChoirCommunication,
    Enquiry,
    Event,
    Project,
    Repertoire,
)


class AttendanceAutoCreationTests(TestCase):
    """Guards against choir/models.py and choir/signals.py both firing
    post_save on Event and colliding on Attendance.unique_together."""

    def test_new_event_creates_exactly_one_attendance_per_active_user(self):
        active_users = [
            User.objects.create_user(username=f"member{i}", password="pw")
            for i in range(3)
        ]
        User.objects.create_user(username="inactive", password="pw", is_active=False)

        project = Project.objects.create(name="Test Project", status="ACTIVE")
        event = Event.objects.create(
            project=project,
            date_time=timezone.now() + timedelta(days=7),
            location="Test Venue",
        )

        self.assertEqual(
            Attendance.objects.filter(event=event).count(), len(active_users)
        )
        for user in active_users:
            self.assertTrue(Attendance.objects.filter(event=event, user=user).exists())


class ProjectModelTests(TestCase):
    """Guards the two load-bearing pieces of the Project-centric migration:
    Event.project is genuinely required at the DB level (not just in
    Python), and Project.get_active() picks the right project when more
    than one happens to be ACTIVE at once (a deliberately allowed, not
    DB-enforced, overlap - see Project.get_active()'s docstring)."""

    def test_event_requires_a_project(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Event.objects.create(
                    date_time=timezone.now() + timedelta(days=7),
                    location="Test Venue",
                )

    def test_get_active_prefers_most_recent_start_date(self):
        Project.objects.create(
            name="Older Active Project", status="ACTIVE", start_date="2026-01-01"
        )
        newer = Project.objects.create(
            name="Newer Active Project", status="ACTIVE", start_date="2026-06-01"
        )
        Project.objects.create(name="Planning Project", status="PLANNING")

        self.assertEqual(Project.get_active(), newer)

    def test_get_active_returns_none_when_no_project_is_active(self):
        Project.objects.create(name="Planning Project", status="PLANNING")
        self.assertIsNone(Project.get_active())


class MemberRepertoireViewTests(TestCase):
    """Guards member_repertoire_view - Repertoire & Learning on the
    subnav, split out of dashboard_view in the Phase 5 restructure. Shows
    the active project's repertoire, and doesn't crash when there isn't
    one."""

    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

    def test_shows_active_projects_repertoire(self):
        active = Project.objects.create(name="Christmas 2026", status="ACTIVE")
        piece = Repertoire.objects.create(composer="Elgar", title="Ave Verum")
        active.repertoire.add(piece)
        Project.objects.create(name="Old Project", status="ARCHIVED")

        response = self.client.get(reverse("member_repertoire"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(piece, response.context["current_repertoire"])

    def test_does_not_crash_with_no_active_project(self):
        response = self.client.get(reverse("member_repertoire"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["current_repertoire"]), [])


class DashboardSubnavTests(TestCase):
    """Guards dashboard_view's Phase 5 project-scoping: the "Schedule &
    Logistics" subnav tab should only auto-heal/show Attendance for the
    ACTIVE project's events, not every Event ever (the pre-Phase-5
    behavior), and must not crash with no active project."""

    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

    def test_dashboard_does_not_crash_with_no_active_project(self):
        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["active_project"])

    def test_dashboard_only_autoheals_active_projects_events(self):
        # Event creation's own post_save signal (signals.py) already backs
        # every active user with a PENDING Attendance row regardless of
        # project - that's unrelated to this phase's change. What Phase 5
        # actually changed is dashboard_view's own catch-up pass, which
        # used to sweep every Event ever; simulate the gap that pass is
        # meant to catch (a missing Attendance row) on both an active- and
        # an archived-project event, and confirm the view only heals the
        # active one.
        active = Project.objects.create(name="Christmas 2026", status="ACTIVE")
        archived = Project.objects.create(name="Old Project", status="ARCHIVED")

        active_event = Event.objects.create(
            project=active,
            date_time=timezone.now() + timedelta(days=7),
            location="St Leonard's Church",
        )
        archived_event = Event.objects.create(
            project=archived,
            date_time=timezone.now() - timedelta(days=100),
            location="St Leonard's Church",
        )

        member = User.objects.get(username="member")
        Attendance.objects.filter(
            user=member, event__in=[active_event, archived_event]
        ).delete()

        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            Attendance.objects.filter(user=member, event=active_event).exists()
        )
        self.assertFalse(
            Attendance.objects.filter(user=member, event=archived_event).exists()
        )


class CommitteeProjectManagementTests(TestCase):
    """Guards the frontend Project CRUD pages - creation, editing, and the
    PLANNING -> ACTIVE status transition that happens there."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="committee", password="pw", is_staff=True
        )
        self.client.login(username="committee", password="pw")

    def test_create_project(self):
        response = self.client.post(
            reverse("committee_projects"),
            {"name": "Christmas 2026", "status": "PLANNING"},
        )
        self.assertRedirects(response, reverse("committee_projects"))
        self.assertTrue(Project.objects.filter(name="Christmas 2026").exists())

    def test_edit_project_changes_status_and_repertoire(self):
        project = Project.objects.create(name="Christmas 2026", status="PLANNING")
        piece = Repertoire.objects.create(composer="Elgar", title="Ave Verum")

        response = self.client.post(
            reverse("committee_project_edit", args=[project.id]),
            {"name": "Christmas 2026", "status": "ACTIVE", "repertoire": [piece.id]},
        )
        self.assertRedirects(response, reverse("committee_projects"))

        project.refresh_from_db()
        self.assertEqual(project.status, "ACTIVE")
        self.assertIn(piece, project.repertoire.all())
        self.assertEqual(Project.get_active(), project)

    def test_project_edit_blocked_for_non_staff(self):
        project = Project.objects.create(name="Christmas 2026", status="PLANNING")
        self.client.logout()
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

        response = self.client.get(reverse("committee_project_edit", args=[project.id]))
        self.assertEqual(response.status_code, 302)


class CommitteeScheduleEventTests(TestCase):
    """Guards QuickEventScheduleForm's project field - added as a hard
    blocker alongside Event.project becoming required, since this form is
    the only frontend path that creates Event rows. Without a project
    field here, every committee-scheduled event would fail validation."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="committee", password="pw", is_staff=True
        )
        self.client.login(username="committee", password="pw")
        self.project = Project.objects.create(name="Christmas 2026", status="ACTIVE")

    def test_scheduling_an_event_requires_and_sets_a_project(self):
        response = self.client.post(
            reverse("committee_schedule"),
            {
                "project": self.project.id,
                "event_type": "REH",
                "date_time": "2026-12-01T19:00",
                "location": "St Leonard's Church",
            },
        )
        self.assertRedirects(response, reverse("committee_hub"))
        event = Event.objects.latest("date_time")
        self.assertEqual(event.project, self.project)

    def test_scheduling_without_a_project_fails_validation(self):
        response = self.client.post(
            reverse("committee_schedule"),
            {
                "event_type": "REH",
                "date_time": "2026-12-01T19:00",
                "location": "St Leonard's Church",
            },
        )
        self.assertEqual(response.status_code, 200)  # re-renders, doesn't 500
        self.assertFalse(Event.objects.exists())


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
            "committee_projects",
            "committee_polling",
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


class AvailabilityPollingTests(TestCase):
    """Guards the availability polling feature: response uniqueness,
    committee poll creation, and the confirmed scoping decision that
    members answering a poll never see that PLANNING project's
    repertoire or description (only committee-facing pages do)."""

    def setUp(self):
        self.planning = Project.objects.create(name="Easter 2027", status="PLANNING")
        self.poll = AvailabilityPoll.objects.create(
            project=self.planning,
            question="Are you available the weekend of 14-15 March 2027?",
        )
        self.member = User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

    def test_response_unique_together_enforced(self):
        AvailabilityResponse.objects.create(
            poll=self.poll, user=self.member, response="YES"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AvailabilityResponse.objects.create(
                    poll=self.poll, user=self.member, response="NO"
                )

    def test_respond_endpoint_updates_existing_response(self):
        self.client.post(
            reverse("member_poll_respond", args=[self.poll.id]),
            data='{"response": "YES"}',
            content_type="application/json",
        )
        self.client.post(
            reverse("member_poll_respond", args=[self.poll.id]),
            data='{"response": "MAYBE"}',
            content_type="application/json",
        )
        self.assertEqual(AvailabilityResponse.objects.filter(poll=self.poll).count(), 1)
        response = AvailabilityResponse.objects.get(poll=self.poll, user=self.member)
        self.assertEqual(response.response, "MAYBE")

    def test_member_polling_page_never_exposes_project_details(self):
        self.planning.description = "Secret repertoire planning notes"
        self.planning.save()
        piece = Repertoire.objects.create(composer="Byrd", title="Ave Verum Corpus")
        self.planning.repertoire.add(piece)

        response = self.client.get(reverse("member_polling"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.poll.question)
        self.assertNotContains(response, "Secret repertoire planning notes")
        self.assertNotContains(response, "Ave Verum Corpus")


class CommitteePollManagementTests(TestCase):
    """Guards the committee-facing poll creation/results page."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="committee", password="pw", is_staff=True
        )
        self.client.login(username="committee", password="pw")
        self.planning = Project.objects.create(name="Easter 2027", status="PLANNING")

    def test_create_poll(self):
        response = self.client.post(
            reverse("committee_polling"),
            {
                "project": self.planning.id,
                "question": "Available for a March residency?",
            },
        )
        self.assertRedirects(response, reverse("committee_polling"))
        self.assertTrue(
            AvailabilityPoll.objects.filter(
                question="Available for a March residency?"
            ).exists()
        )

    def test_results_show_response_counts_and_non_responders(self):
        poll = AvailabilityPoll.objects.create(
            project=self.planning, question="Available in March?"
        )
        member = User.objects.create_user(username="singer", password="pw")
        AvailabilityResponse.objects.create(poll=poll, user=member, response="YES")

        response = self.client.get(reverse("committee_polling"))
        self.assertEqual(response.status_code, 200)
        row = next(r for r in response.context["poll_data"] if r["poll"] == poll)
        self.assertEqual(row["yes_count"], 1)
        # self.staff never responded, so should appear as a non-responder
        self.assertIn(self.staff, row["non_responders"])

import json
import tempfile
from io import StringIO
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Attendance,
    AuditionApplication,
    AvailabilityPoll,
    AvailabilityResponse,
    ChoirCommunication,
    ChoirSettings,
    CommitteeDocument,
    Enquiry,
    Event,
    LearningAsset,
    Project,
    Repertoire,
    SubscriptionPayment,
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

    def test_shows_a_tab_per_simultaneous_active_project_without_leakage(self):
        project_a = Project.objects.create(name="Clent 2026", status="ACTIVE")
        project_b = Project.objects.create(name="Ewelme 2027", status="ACTIVE")
        piece_a = Repertoire.objects.create(composer="Elgar", title="Ave Verum")
        piece_b = Repertoire.objects.create(composer="Byrd", title="Ave Verum Corpus")
        project_a.repertoire.add(piece_a)
        project_b.repertoire.add(piece_b)

        response = self.client.get(reverse("member_repertoire"))
        self.assertEqual(response.status_code, 200)

        active_projects = list(response.context["active_projects"])
        self.assertEqual(set(active_projects), {project_a, project_b})

        projects_data = {
            entry["project"].id: list(entry["repertoire"])
            for entry in response.context["projects_data"]
        }
        self.assertEqual(projects_data[project_a.id], [piece_a])
        self.assertEqual(projects_data[project_b.id], [piece_b])


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

    def test_shows_a_tab_per_simultaneous_active_project_without_leakage(self):
        project_a = Project.objects.create(name="Clent 2026", status="ACTIVE")
        project_b = Project.objects.create(name="Ewelme 2027", status="ACTIVE")

        event_a = Event.objects.create(
            project=project_a,
            date_time=timezone.now() + timedelta(days=7),
            location="St Leonard's Church",
        )
        event_b = Event.objects.create(
            project=project_b,
            date_time=timezone.now() + timedelta(days=30),
            location="Ewelme Village Hall",
        )

        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 200)

        active_projects = list(response.context["active_projects"])
        self.assertEqual(set(active_projects), {project_a, project_b})

        projects_data = {
            entry["project"].id: [a.event_id for a in entry["user_attendances"]]
            for entry in response.context["projects_data"]
        }
        self.assertEqual(projects_data[project_a.id], [event_a.id])
        self.assertEqual(projects_data[project_b.id], [event_b.id])


class HubViewTests(TestCase):
    """Guards hub_view's project scoping - a LearningAsset attached to one
    project's repertoire shouldn't appear under another project's hub, even
    for the same voice part."""

    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

        self.project_a = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.project_b = Project.objects.create(name="Ewelme 2027", status="ACTIVE")

        self.piece_a = Repertoire.objects.create(composer="Elgar", title="Ave Verum")
        self.piece_b = Repertoire.objects.create(composer="Byrd", title="Mass")
        self.project_a.repertoire.add(self.piece_a)
        self.project_b.repertoire.add(self.piece_b)

        self.asset_a = LearningAsset.objects.create(
            repertoire=self.piece_a, voice_part="SOP", asset_name="Sop Track A"
        )
        self.asset_b = LearningAsset.objects.create(
            repertoire=self.piece_b, voice_part="SOP", asset_name="Sop Track B"
        )

    def test_hub_only_shows_the_requested_projects_assets(self):
        response = self.client.get(reverse("hub", args=["soprano", self.project_a.id]))
        self.assertEqual(response.status_code, 200)

        assets = list(response.context["assets"])
        self.assertIn(self.asset_a, assets)
        self.assertNotIn(self.asset_b, assets)

    def test_hub_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("hub", args=["soprano", self.project_a.id]))
        self.assertEqual(response.status_code, 302)

    def test_hub_404s_for_a_non_active_project(self):
        archived = Project.objects.create(name="Old Project", status="ARCHIVED")
        response = self.client.get(reverse("hub", args=["soprano", archived.id]))
        self.assertEqual(response.status_code, 404)


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
        self.assertRedirects(response, reverse("committee_schedule"))
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


class ContactHoneypotTests(TestCase):
    """The spam-trap field is on the page (it never used to be rendered,
    so it caught nothing) and a submission that fills it in is dropped."""

    def test_both_forms_render_the_hidden_trap(self):
        response = self.client.get(reverse("contact"))
        self.assertContains(response, 'id="enquiry-website"', count=1)
        self.assertContains(response, 'id="audition-website"', count=1)
        self.assertContains(response, 'class="honeypot"', count=2)

    def test_filled_trap_blocks_the_enquiry(self):
        self.client.post(
            reverse("contact"),
            {
                "name": "Spam Bot",
                "email": "bot@example.com",
                "subject": "general",
                "message": "Buy now",
                "website": "http://spam.example.com",
            },
        )
        self.assertFalse(Enquiry.objects.exists())

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


class CommitteeFinancialsTests(TestCase):
    """Guards the finance ledger CRUD: logging a payment now goes through
    SubscriptionPaymentForm instead of a raw request.POST.get("amount")
    with no validation - a non-numeric amount used to 500 the whole view.
    Also covers editing, deleting, and the exempt-status toggle."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="committee", password="pw", is_staff=True
        )
        self.client.login(username="committee", password="pw")

        self.singer = User.objects.create_user(username="singer", password="pw")
        self.profile = self.singer.profile

    def test_create_payment_with_valid_amount_logs_it(self):
        response = self.client.post(
            reverse("committee_financials"),
            {"member_id": self.profile.id, "amount": "45.00", "payment_method": "BACS"},
        )
        self.assertRedirects(response, reverse("committee_financials"))
        payment = SubscriptionPayment.objects.get(member=self.profile)
        self.assertEqual(str(payment.amount), "45.00")

    def test_create_payment_with_invalid_amount_does_not_crash(self):
        response = self.client.post(
            reverse("committee_financials"),
            {"member_id": self.profile.id, "amount": "not-a-number", "payment_method": "BACS"},
        )
        self.assertNotEqual(response.status_code, 500)
        self.assertFalse(SubscriptionPayment.objects.filter(member=self.profile).exists())

    def test_edit_payment_updates_amount(self):
        payment = SubscriptionPayment.objects.create(
            member=self.profile,
            amount="50.00",
            date_paid=timezone.now().date(),
            term_reference="Autumn 2026",
        )
        response = self.client.post(
            reverse("committee_financials_edit", args=[payment.id]),
            {
                "amount": "60.00",
                "date_paid": payment.date_paid.isoformat(),
                "term_reference": "Autumn 2026",
                "payment_method": "CASH",
            },
        )
        self.assertRedirects(response, reverse("committee_financials"))
        payment.refresh_from_db()
        self.assertEqual(str(payment.amount), "60.00")
        self.assertEqual(payment.payment_method, "CASH")

    def test_delete_payment_removes_it(self):
        payment = SubscriptionPayment.objects.create(
            member=self.profile,
            amount="50.00",
            date_paid=timezone.now().date(),
            term_reference="Autumn 2026",
        )
        response = self.client.post(
            reverse("committee_financials_delete", args=[payment.id])
        )
        self.assertRedirects(response, reverse("committee_financials"))
        self.assertFalse(SubscriptionPayment.objects.filter(id=payment.id).exists())

    def test_toggle_exempt_flips_status(self):
        self.assertFalse(self.profile.is_exempt_from_subs)
        self.client.post(reverse("committee_toggle_exempt", args=[self.profile.id]))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_exempt_from_subs)

        self.client.post(reverse("committee_toggle_exempt", args=[self.profile.id]))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_exempt_from_subs)

    def test_edit_delete_and_toggle_blocked_for_non_staff(self):
        self.client.logout()
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

        payment = SubscriptionPayment.objects.create(
            member=self.profile,
            amount="50.00",
            date_paid=timezone.now().date(),
            term_reference="Autumn 2026",
        )
        for response in (
            self.client.get(reverse("committee_financials_edit", args=[payment.id])),
            self.client.post(reverse("committee_financials_delete", args=[payment.id])),
            self.client.post(reverse("committee_toggle_exempt", args=[self.profile.id])),
        ):
            self.assertEqual(response.status_code, 302)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CommitteeDocumentDeleteTests(TestCase):
    """Guards the document vault's staff-gated delete endpoint - the
    "open read, staff write" split already established for uploads in
    committee_documents_view carries over to deletion too."""

    def setUp(self):
        self.document = CommitteeDocument.objects.create(
            title="AGM Minutes",
            doc_type="MIN",
            file=SimpleUploadedFile("minutes.txt", b"minutes content"),
        )

    def test_staff_can_delete_document(self):
        User.objects.create_user(username="committee", password="pw", is_staff=True)
        self.client.login(username="committee", password="pw")

        response = self.client.post(
            reverse("committee_document_delete", args=[self.document.id])
        )
        self.assertRedirects(response, reverse("committee_documents"))
        self.assertFalse(
            CommitteeDocument.objects.filter(id=self.document.id).exists()
        )

    def test_non_staff_member_cannot_delete_document(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")

        response = self.client.post(
            reverse("committee_document_delete", args=[self.document.id])
        )
        self.assertRedirects(response, reverse("committee_documents"))
        self.assertTrue(
            CommitteeDocument.objects.filter(id=self.document.id).exists()
        )


class CommitteeRsvpProjectScopingTests(TestCase):
    """Guards the concrete dual-axis attendance implementation: the Event
    Logistics panel defaults to the ACTIVE project and is switchable via
    ?project=<id>, while Member Overview stays all-time/unfiltered
    regardless of which project is selected."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="committee", password="pw", is_staff=True
        )
        self.client.login(username="committee", password="pw")

        self.active_project = Project.objects.create(
            name="Christmas 2026", status="ACTIVE"
        )
        self.archived_project = Project.objects.create(
            name="Summer 2025", status="ARCHIVED"
        )
        self.active_event = Event.objects.create(
            project=self.active_project,
            date_time=timezone.now() + timedelta(days=7),
            location="Active Venue",
        )
        self.archived_event = Event.objects.create(
            project=self.archived_project,
            date_time=timezone.now() - timedelta(days=200),
            location="Archived Venue",
        )

    def test_defaults_to_active_project_events_only(self):
        response = self.client.get(reverse("committee_rsvps"))
        self.assertEqual(response.status_code, 200)
        events_shown = [row["event"] for row in response.context["report_data"]]
        self.assertIn(self.active_event, events_shown)
        self.assertNotIn(self.archived_event, events_shown)
        self.assertEqual(response.context["selected_project_id"], str(self.active_project.id))

    def test_can_switch_to_a_different_project(self):
        response = self.client.get(
            reverse("committee_rsvps"), {"project": self.archived_project.id}
        )
        events_shown = [row["event"] for row in response.context["report_data"]]
        self.assertIn(self.archived_event, events_shown)
        self.assertNotIn(self.active_event, events_shown)

    def test_all_projects_option_shows_every_event(self):
        response = self.client.get(reverse("committee_rsvps"), {"project": ""})
        events_shown = [row["event"] for row in response.context["report_data"]]
        self.assertIn(self.active_event, events_shown)
        self.assertIn(self.archived_event, events_shown)

    def test_member_overview_is_unaffected_by_project_selection(self):
        singer = User.objects.create_user(username="singer", password="pw")
        Attendance.objects.filter(event=self.active_event, user=singer).update(
            status="ATTENDING"
        )
        Attendance.objects.filter(event=self.archived_event, user=singer).update(
            status="ATTENDING"
        )

        default_response = self.client.get(reverse("committee_rsvps"))
        scoped_response = self.client.get(
            reverse("committee_rsvps"), {"project": self.archived_project.id}
        )

        def rate_for(response):
            row = next(
                r for r in response.context["member_stats"] if r["user"] == singer
            )
            return row["attending"]

        self.assertEqual(rate_for(default_response), rate_for(scoped_response))

    def test_default_event_is_the_next_upcoming_one_not_the_last_in_the_list(self):
        # report_data/the dropdown stay newest-first, but the *default*
        # selection should be whichever event is soonest from now - not
        # simply the first item in that descending list (which, with
        # several future dates already on the calendar, was the last
        # rehearsal in the cycle rather than the next one).
        soon = Event.objects.create(
            project=self.active_project,
            date_time=timezone.now() + timedelta(days=1),
            location="Next Rehearsal",
        )
        Event.objects.create(
            project=self.active_project,
            date_time=timezone.now() + timedelta(days=60),
            location="Final Concert",
        )

        response = self.client.get(reverse("committee_rsvps"))
        self.assertEqual(response.context["default_event_id"], soon.id)


class SeedDevDataCommandTests(TestCase):
    """seed_dev_data must refuse to run outside DEBUG (it creates users with
    a published password), and be safe to re-run locally."""

    def test_refuses_to_run_without_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_dev_data", stdout=StringIO())
        self.assertFalse(User.objects.filter(username="committee").exists())

    @override_settings(DEBUG=True)
    def test_creates_the_seed_data(self):
        call_command("seed_dev_data", stdout=StringIO())

        committee = User.objects.get(username="committee")
        self.assertTrue(committee.is_staff)
        self.assertEqual(User.objects.filter(is_staff=False).count(), 3)
        self.assertTrue(
            EmailAddress.objects.filter(email="soprano@example.com", verified=True).exists()
        )

        active = Project.objects.get(status="ACTIVE")
        self.assertEqual(active.events.count(), 3)
        self.assertEqual(active.events.filter(date_time__lt=timezone.now()).count(), 1)
        self.assertEqual(active.repertoire.count(), 2)
        self.assertEqual(LearningAsset.objects.count(), 2)
        # Users were created before the events, so every user has an RSVP for each.
        self.assertEqual(Attendance.objects.count(), 4 * 3)

        planning = Project.objects.get(status="PLANNING")
        self.assertTrue(planning.polls.filter(is_open=True).exists())

    @override_settings(DEBUG=True)
    def test_is_idempotent(self):
        call_command("seed_dev_data", stdout=StringIO())
        call_command("seed_dev_data", stdout=StringIO())

        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Event.objects.count(), 3)
        self.assertEqual(AvailabilityPoll.objects.count(), 1)

    @override_settings(DEBUG=True)
    def test_seeded_member_can_log_in(self):
        call_command("seed_dev_data", stdout=StringIO())
        response = self.client.post(
            reverse("account_login"),
            {"login": "soprano@example.com", "password": "choir-dev-password"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)


class SiteMessagesTests(TestCase):
    """base.html renders Django messages once, for every page - before Build
    Order Phase 1 most committee pages queued success messages that were
    never shown."""

    def setUp(self):
        User.objects.create_user(username="committee", password="pw", is_staff=True)
        self.client.login(username="committee", password="pw")
        self.singer = User.objects.create_user(
            username="singer", password="pw", first_name="Sam", last_name="Singer"
        )

    def test_success_message_renders_after_redirect(self):
        response = self.client.post(
            reverse("committee_financials"),
            {"member_id": self.singer.profile.id, "amount": "45.00", "payment_method": "BACS"},
            follow=True,
        )
        self.assertContains(
            response, "Payment successfully logged for Sam Singer.", count=1
        )
        self.assertContains(response, 'data-status="success"')

    def test_error_message_maps_to_danger_status(self):
        response = self.client.post(
            reverse("committee_financials"),
            {"member_id": self.singer.profile.id, "amount": "nope", "payment_method": "BACS"},
            follow=True,
        )
        self.assertContains(response, 'data-status="danger"')

    def test_settings_page_shows_its_message_only_once(self):
        response = self.client.post(
            reverse("settings"),
            {"first_name": "Clara", "last_name": "Committee", "email": "c@example.com"},
            follow=True,
        )
        self.assertContains(
            response, "Your profile has been updated successfully.", count=1
        )


class DashboardPastEventsTests(TestCase):
    """Past events of an active project move out of the upcoming list into
    a collapsed "Earlier this project" section, without an RSVP select."""

    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")
        self.project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.past = Event.objects.create(
            project=self.project,
            date_time=timezone.now() - timedelta(days=7),
            location="Past Hall",
        )
        self.future = Event.objects.create(
            project=self.project,
            date_time=timezone.now() + timedelta(days=7),
            location="Future Hall",
        )

    def test_past_event_is_listed_as_earlier_not_upcoming(self):
        response = self.client.get(reverse("members"))
        data = response.context["projects_data"][0]

        self.assertEqual([a.event_id for a in data["user_attendances"]], [self.future.id])
        self.assertEqual([a.event_id for a in data["past_attendances"]], [self.past.id])
        self.assertContains(response, "Earlier this project (1)")

    def test_past_event_has_no_rsvp_select(self):
        response = self.client.get(reverse("members"))
        past_attendance = Attendance.objects.get(event=self.past)
        future_attendance = Attendance.objects.get(event=self.future)

        self.assertContains(response, f'data-attendance-id="{future_attendance.id}"')
        self.assertNotContains(response, f'data-attendance-id="{past_attendance.id}"')

    def test_no_earlier_section_without_past_events(self):
        self.past.delete()
        response = self.client.get(reverse("members"))
        self.assertNotContains(response, "Earlier this project")


class LoginErrorTests(TestCase):
    """The login page shows allauth's own non-field error text rather than
    only a generic fallback."""

    def test_wrong_password_shows_allauths_message(self):
        user = User.objects.create_user(username="m", email="m@example.com", password="pw")
        EmailAddress.objects.create(user=user, email="m@example.com", verified=True, primary=True)

        response = self.client.post(
            reverse("account_login"), {"login": "m@example.com", "password": "wrong"}
        )
        errors = response.context["form"].non_field_errors()
        self.assertTrue(errors)
        for error in errors:
            self.assertContains(response, error)
        self.assertNotContains(response, "Your email and password didn't match.")


class MembersShellTests(TestCase):
    """Every logged-in page renders inside _members_base.html with one
    members navigation; the committee group only shows for committee."""

    MEMBER_PAGES = ["members", "member_repertoire", "member_polling", "settings", "committee_hub", "committee_documents"]
    COMMITTEE_PAGES = [
        "committee_projects",
        "committee_schedule",
        "committee_rsvps",
        "committee_polling",
        "committee_financials",
        "committee_broadcast",
        "committee_emergency",
    ]

    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        User.objects.create_user(username="committee", password="pw", is_staff=True)

    def test_every_page_uses_the_shell_and_one_nav(self):
        self.client.login(username="committee", password="pw")
        for name in self.MEMBER_PAGES + self.COMMITTEE_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "choir/_members_base.html")
                self.assertContains(response, 'aria-label="Members area"', count=1)

    def test_committee_group_shows_for_committee_only(self):
        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("members"))
        self.assertContains(response, reverse("committee_financials"))

        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("members"))
        self.assertNotContains(response, reverse("committee_financials"))
        self.assertContains(response, "Document Vault")

    def test_current_page_is_marked(self):
        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("member_polling"))
        self.assertContains(
            response,
            f'<a href="{reverse("member_polling")}" class="members-nav__link" aria-current="page">',
            html=False,
        )

    def test_hub_shows_non_committee_only_the_vault(self):
        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("committee_hub"))
        self.assertContains(response, reverse("committee_documents"))
        self.assertNotContains(response, reverse("committee_projects"))
        self.assertNotContains(response, "🔒")

    def test_vault_upload_form_is_committee_only(self):
        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("committee_documents"))
        self.assertNotContains(response, 'enctype="multipart/form-data"')

        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_documents"))
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_members_header_nav_is_just_public_site_and_logout(self):
        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("members"))
        self.assertContains(response, "Back to Public Site")
        self.assertNotContains(response, 'class="nav-link">Settings</a>')


class PageScriptsTests(TestCase):
    """Each page loads only the scripts it uses."""

    PUBLIC_SCRIPTS = ["looseleaf-behaviors", "mobile-menu", "back-to-top"]
    MEMBERS_SCRIPTS = ["rsvp-dashboard", "member-dashboard", "project-tabs", "confirm-forms"]

    def test_public_pages_load_only_the_shared_scripts(self):
        for name in ["home", "events", "contact"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                for script in self.PUBLIC_SCRIPTS:
                    self.assertContains(response, f"js/{script}")
                for script in self.MEMBERS_SCRIPTS + ["project-carousel"]:
                    self.assertNotContains(response, f"js/{script}")

    def test_about_page_also_loads_the_carousel(self):
        response = self.client.get(reverse("about"))
        self.assertContains(response, "js/project-carousel")

    def test_rsvp_dashboard_loads_its_script(self):
        User.objects.create_user(username="committee", password="pw", is_staff=True)
        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_rsvps"))
        self.assertContains(response, "js/rsvp-dashboard")
        self.assertNotContains(response, "onclick=")
        self.assertNotContains(response, "onchange=")


class NoInlineStylesTests(TestCase):
    """Templates carry no style="" attributes (Build Order Phase 2). The
    exceptions: the Spotify embed on About, and the invitation email,
    which needs inline styles because email clients ignore stylesheets."""

    ALLOWED = {"choir/about.html", "invitations/email/email_invite_message.html"}

    def test_no_inline_styles_in_templates(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent / "templates"
        offenders = [
            path.relative_to(root).as_posix()
            for path in root.rglob("*.html")
            if 'style="' in path.read_text(encoding="utf-8")
            and path.relative_to(root).as_posix() not in self.ALLOWED
        ]
        self.assertEqual(offenders, [])


class CommitteeEventManagementTests(TestCase):
    """Build Order Phase 3: the committee lists, edits and deletes events
    from the schedule page instead of Django admin."""

    def setUp(self):
        User.objects.create_user(username="committee", password="pw", is_staff=True)
        self.singer = User.objects.create_user(username="singer", password="pw")
        self.client.login(username="committee", password="pw")

        self.active = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.archived = Project.objects.create(name="Old Project", status="ARCHIVED")
        self.event = Event.objects.create(
            project=self.active,
            date_time=timezone.now() + timedelta(days=7),
            location="St Leonard's Church",
        )

    def edit_payload(self, **overrides):
        payload = {
            "project": self.active.id,
            "event_type": "REH",
            "date_time": "2026-12-03T19:30",
            "location": "St Leonard's Church",
            "additional_notes": "<p>Bars 1-40 of the Byrd</p>",
        }
        payload.update(overrides)
        return payload

    def test_schedule_lists_upcoming_events_of_live_projects_only(self):
        past = Event.objects.create(
            project=self.active, date_time=timezone.now() - timedelta(days=7), location="Past Hall"
        )
        archived = Event.objects.create(
            project=self.archived,
            date_time=timezone.now() + timedelta(days=3),
            location="Archived Hall",
        )

        response = self.client.get(reverse("committee_schedule"))
        listed = [e for _, events in response.context["events_by_project"] for e in events]
        self.assertEqual(listed, [self.event])
        self.assertNotIn(past, listed)
        self.assertNotIn(archived, listed)
        self.assertContains(response, reverse("committee_event_edit", args=[self.event.id]))

    def test_edit_changes_date_and_rehearsal_plan(self):
        response = self.client.post(
            reverse("committee_event_edit", args=[self.event.id]), self.edit_payload()
        )
        self.assertRedirects(response, reverse("committee_schedule"))

        self.event.refresh_from_db()
        self.assertEqual(timezone.localtime(self.event.date_time).strftime("%Y-%m-%d %H:%M"), "2026-12-03 19:30")
        self.assertIn("Bars 1-40", self.event.additional_notes)

    def test_edit_page_loads_the_rich_text_editor(self):
        response = self.client.get(reverse("committee_event_edit", args=[self.event.id]))
        self.assertContains(response, "tinymce")

    def test_invalid_edit_rerenders_without_saving(self):
        response = self.client.post(
            reverse("committee_event_edit", args=[self.event.id]),
            self.edit_payload(date_time="not a date"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.event.refresh_from_db()
        self.assertEqual(self.event.additional_notes, "")

    def test_an_archived_projects_event_can_still_be_edited(self):
        old = Event.objects.create(
            project=self.archived, date_time=timezone.now() - timedelta(days=60), location="Old Hall"
        )
        response = self.client.post(
            reverse("committee_event_edit", args=[old.id]),
            self.edit_payload(project=self.archived.id, location="Corrected Hall"),
        )
        self.assertRedirects(response, reverse("committee_schedule"))
        old.refresh_from_db()
        self.assertEqual(old.location, "Corrected Hall")

    def test_delete_removes_the_event_and_its_rsvps(self):
        self.assertTrue(Attendance.objects.filter(event=self.event).exists())

        response = self.client.post(reverse("committee_event_delete", args=[self.event.id]))
        self.assertRedirects(response, reverse("committee_schedule"))
        self.assertFalse(Event.objects.filter(id=self.event.id).exists())
        self.assertFalse(Attendance.objects.filter(event_id=self.event.id).exists())

    def test_delete_refuses_an_archived_projects_event(self):
        old = Event.objects.create(
            project=self.archived, date_time=timezone.now() - timedelta(days=60), location="Old Hall"
        )
        response = self.client.post(reverse("committee_event_delete", args=[old.id]), follow=True)
        self.assertTrue(Event.objects.filter(id=old.id).exists())
        self.assertContains(response, "archived project")

    def test_delete_is_post_only(self):
        response = self.client.get(reverse("committee_event_delete", args=[self.event.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Event.objects.filter(id=self.event.id).exists())


class CommitteeNewUrlPermissionTests(TestCase):
    """Every URL Phase 3 adds is committee-only: anonymous visitors and
    non-committee members are redirected and nothing changes."""

    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        planning = Project.objects.create(name="Easter 2027", status="PLANNING")
        active = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.event = Event.objects.create(
            project=active, date_time=timezone.now() + timedelta(days=7), location="Hall"
        )
        self.poll = AvailabilityPoll.objects.create(project=planning, question="March?")

    def urls(self):
        return [
            ("get", reverse("committee_schedule")),
            ("get", reverse("committee_event_edit", args=[self.event.id])),
            ("post", reverse("committee_event_delete", args=[self.event.id])),
            ("get", reverse("committee_poll_edit", args=[self.poll.id])),
            ("post", reverse("committee_poll_toggle", args=[self.poll.id])),
        ]

    def assert_all_blocked(self):
        for method, url in self.urls():
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("account_login"), response["Location"])
        self.assertTrue(Event.objects.filter(id=self.event.id).exists())
        self.poll.refresh_from_db()
        self.assertTrue(self.poll.is_open)

    def test_anonymous_is_redirected_to_login(self):
        self.assert_all_blocked()

    def test_non_committee_member_is_redirected(self):
        self.client.login(username="member", password="pw")
        self.assert_all_blocked()


class CommitteePollEditingTests(TestCase):
    """Polls can be edited, closed and reopened; a closed poll disappears
    from members' Looking Ahead."""

    def setUp(self):
        User.objects.create_user(username="committee", password="pw", is_staff=True)
        self.member = User.objects.create_user(username="member", password="pw")
        self.planning = Project.objects.create(name="Easter 2027", status="PLANNING")
        self.poll = AvailabilityPoll.objects.create(
            project=self.planning, question="Available for a March residency?"
        )

    def test_close_hides_the_poll_from_members_and_reopen_restores_it(self):
        self.client.login(username="committee", password="pw")
        self.client.post(reverse("committee_poll_toggle", args=[self.poll.id]))
        self.poll.refresh_from_db()
        self.assertFalse(self.poll.is_open)

        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("member_polling"))
        self.assertNotContains(response, self.poll.question)

        self.client.login(username="committee", password="pw")
        self.client.post(reverse("committee_poll_toggle", args=[self.poll.id]))
        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("member_polling"))
        self.assertContains(response, self.poll.question)

    def test_results_row_offers_edit_and_close(self):
        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_polling"))
        self.assertContains(response, reverse("committee_poll_edit", args=[self.poll.id]))
        self.assertContains(response, reverse("committee_poll_toggle", args=[self.poll.id]))
        self.assertContains(response, "Close<span")

    def test_edit_updates_the_question_and_can_close(self):
        self.client.login(username="committee", password="pw")
        response = self.client.post(
            reverse("committee_poll_edit", args=[self.poll.id]),
            {"project": self.planning.id, "question": "Available 14-15 March?"},
        )
        self.assertRedirects(response, reverse("committee_polling"))
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.question, "Available 14-15 March?")
        # An unticked checkbox isn't submitted, so leaving it off closes the poll
        self.assertFalse(self.poll.is_open)

    def test_poll_stays_editable_after_its_project_goes_active(self):
        self.planning.status = "ACTIVE"
        self.planning.save()
        self.client.login(username="committee", password="pw")
        response = self.client.post(
            reverse("committee_poll_edit", args=[self.poll.id]),
            {"project": self.planning.id, "question": "Still editable?", "is_open": "on"},
        )
        self.assertRedirects(response, reverse("committee_polling"))

    def test_create_form_defaults_to_open(self):
        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_polling"))
        self.assertTrue(response.context["form"]["is_open"].value())


class MemberPollNotesTests(TestCase):
    """Members can add a note to their availability answer; the committee
    sees it on the Results list."""

    def setUp(self):
        User.objects.create_user(username="committee", password="pw", is_staff=True)
        self.member = User.objects.create_user(
            username="member", password="pw", first_name="Sam", last_name="Singer"
        )
        planning = Project.objects.create(name="Easter 2027", status="PLANNING")
        self.poll = AvailabilityPoll.objects.create(project=planning, question="March?")
        self.client.login(username="member", password="pw")

    def respond(self, payload):
        return self.client.post(
            reverse("member_poll_respond", args=[self.poll.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_notes_round_trip(self):
        response = self.respond({"response": "MAYBE", "notes": "  Away until the 10th  "})
        self.assertEqual(response.status_code, 200)

        saved = AvailabilityResponse.objects.get(poll=self.poll, user=self.member)
        self.assertEqual(saved.notes, "Away until the 10th")

        page = self.client.get(reverse("member_polling"))
        self.assertContains(page, 'value="Away until the 10th"')

        self.client.login(username="committee", password="pw")
        results = self.client.get(reverse("committee_polling"))
        self.assertContains(results, "Away until the 10th")
        self.assertContains(results, "Sam Singer")

    def test_answer_without_notes_keeps_the_existing_note(self):
        self.respond({"response": "MAYBE", "notes": "Away until the 10th"})
        self.respond({"response": "YES"})
        saved = AvailabilityResponse.objects.get(poll=self.poll, user=self.member)
        self.assertEqual(saved.response, "YES")
        self.assertEqual(saved.notes, "Away until the 10th")

    def test_empty_note_clears_it(self):
        self.respond({"response": "MAYBE", "notes": "Away until the 10th"})
        self.respond({"response": "MAYBE", "notes": ""})
        self.assertEqual(AvailabilityResponse.objects.get(poll=self.poll).notes, "")

    def test_overlong_note_is_trimmed_and_non_text_rejected(self):
        self.respond({"response": "YES", "notes": "x" * 500})
        self.assertEqual(len(AvailabilityResponse.objects.get(poll=self.poll).notes), 200)

        response = self.respond({"response": "YES", "notes": ["not", "text"]})
        self.assertEqual(response.status_code, 400)

    def test_non_object_payload_is_rejected(self):
        response = self.client.post(
            reverse("member_poll_respond", args=[self.poll.id]),
            data="[1, 2]",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class ChoirSettingsTests(TestCase):
    """Build Order Phase 4a: the term, subscription and bank details live
    in one ChoirSettings row the committee edits on the site."""

    def setUp(self):
        User.objects.create_user(username="committee", password="pw", is_staff=True)
        self.member = User.objects.create_user(username="member", password="pw", last_name="Singer")

    def test_load_returns_the_seeded_row(self):
        # The data migration (0022) seeds pk=1 from the old hard-coded values
        choir_settings = ChoirSettings.load()
        self.assertEqual(choir_settings.pk, 1)
        self.assertEqual(choir_settings.current_term, settings.CURRENT_TERM)
        self.assertEqual(choir_settings.bank_sort_code, "23-05-80")
        self.assertEqual(ChoirSettings.objects.count(), 1)

    def test_load_recreates_a_missing_row_and_save_keeps_one_row(self):
        ChoirSettings.objects.all().delete()
        choir_settings = ChoirSettings.load()
        self.assertEqual(choir_settings.current_term, settings.CURRENT_TERM)

        ChoirSettings(current_term="Spring 2027").save()
        self.assertEqual(ChoirSettings.objects.count(), 1)
        self.assertEqual(ChoirSettings.load().current_term, "Spring 2027")

    def test_dashboard_reads_term_amount_and_bank_details_from_settings(self):
        choir_settings = ChoirSettings.load()
        choir_settings.current_term = "Spring 2027"
        choir_settings.subscription_amount = "65.00"
        choir_settings.bank_account_number = "11112222"
        choir_settings.save()

        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("members"))
        self.assertEqual(response.context["current_term"], "Spring 2027")
        self.assertContains(response, "£65.00 for Spring 2027")
        self.assertContains(response, "11112222")
        self.assertNotContains(response, "58234028")

    def test_ledger_uses_the_settings_term(self):
        choir_settings = ChoirSettings.load()
        choir_settings.current_term = "Spring 2027"
        choir_settings.save()
        SubscriptionPayment.objects.create(
            member=self.member.profile, amount=50, date_paid=timezone.now().date(), term_reference="Autumn 2026"
        )

        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_financials"))
        row = next(r for r in response.context["roster"] if r["user"] == self.member)
        self.assertIsNone(row["payment"])  # paid last term, not this one
        self.assertEqual(response.context["selected_term"], "Spring 2027")

        self.client.post(
            reverse("committee_financials"),
            {"member_id": self.member.profile.id, "amount": "50.00", "payment_method": "BACS"},
        )
        self.assertTrue(
            SubscriptionPayment.objects.filter(member=self.member.profile, term_reference="Spring 2027").exists()
        )

    def test_ledger_term_selector_shows_an_earlier_term(self):
        SubscriptionPayment.objects.create(
            member=self.member.profile, amount=50, date_paid=timezone.now().date(), term_reference="Summer 2026"
        )
        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_financials"), {"term": "Summer 2026"})
        self.assertEqual(response.context["earlier_terms"], ["Summer 2026"])
        row = next(r for r in response.context["roster"] if r["user"] == self.member)
        self.assertEqual(row["payment"].term_reference, "Summer 2026")

    def test_settings_page_saves_and_is_committee_only(self):
        self.client.login(username="member", password="pw")
        self.assertEqual(self.client.get(reverse("committee_settings")).status_code, 302)

        self.client.login(username="committee", password="pw")
        response = self.client.post(
            reverse("committee_settings"),
            {
                "current_term": "Spring 2027",
                "subscription_amount": "55.00",
                "bank_account_name": "Clent Consort",
                "bank_sort_code": "23-05-80",
                "bank_account_number": "58234028",
                "instagram_url": "https://instagram.com/clentconsort",
            },
        )
        self.assertRedirects(response, reverse("committee_settings"))
        choir_settings = ChoirSettings.load()
        self.assertEqual(choir_settings.current_term, "Spring 2027")
        self.assertEqual(str(choir_settings.subscription_amount), "55.00")

    def test_invalid_settings_post_rerenders(self):
        self.client.login(username="committee", password="pw")
        response = self.client.post(
            reverse("committee_settings"),
            {"current_term": "", "subscription_amount": "lots", "youtube_url": "not a url"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(ChoirSettings.load().current_term, settings.CURRENT_TERM)

    def test_footer_shows_only_the_social_icons_that_are_set(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "social-icon")

        choir_settings = ChoirSettings.load()
        choir_settings.instagram_url = "https://instagram.com/clentconsort"
        choir_settings.save()
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'href="https://instagram.com/clentconsort"')
        self.assertContains(response, "social-icon", count=1)
        self.assertNotContains(response, "on YouTube")


class CommitteeInboxTests(TestCase):
    """Build Order Phase 4b: contact-form enquiries and audition
    applications in one committee inbox, each markable as handled."""

    def setUp(self):
        self.committee = User.objects.create_user(username="committee", password="pw", is_staff=True)
        User.objects.create_user(username="member", password="pw")
        self.enquiry = Enquiry.objects.create(name="Ann", email="ann@example.com", message="Can you sing at our wedding?")
        self.application = AuditionApplication.objects.create(
            name="Ben", email="ben@example.com", voice_part="tenor"
        )

    def test_lists_both_kinds_unhandled_first(self):
        self.enquiry.handled = True
        self.enquiry.save()

        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_inbox"))
        objects = [item["obj"] for item in response.context["items"]]
        self.assertEqual(objects, [self.application, self.enquiry])
        self.assertContains(response, "Can you sing at our wedding?")

    def test_mark_handled_records_who_and_can_be_undone(self):
        self.client.login(username="committee", password="pw")
        response = self.client.post(reverse("committee_inbox_toggle", args=["enquiry", self.enquiry.id]))
        self.assertRedirects(response, reverse("committee_inbox"))
        self.enquiry.refresh_from_db()
        self.assertTrue(self.enquiry.handled)
        self.assertEqual(self.enquiry.handled_by, self.committee)

        self.client.post(reverse("committee_inbox_toggle", args=["enquiry", self.enquiry.id]))
        self.enquiry.refresh_from_db()
        self.assertFalse(self.enquiry.handled)
        self.assertIsNone(self.enquiry.handled_by)

    def test_unknown_kind_is_404_and_toggle_is_post_only(self):
        self.client.login(username="committee", password="pw")
        self.assertEqual(
            self.client.post(reverse("committee_inbox_toggle", args=["parcel", 1])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("committee_inbox_toggle", args=["audition", self.application.id])).status_code,
            405,
        )

    def test_nav_badge_counts_unhandled_items(self):
        self.client.login(username="committee", password="pw")
        response = self.client.get(reverse("committee_hub"))
        self.assertContains(response, 'members-nav__count">2<')

        self.client.post(reverse("committee_inbox_toggle", args=["audition", self.application.id]))
        response = self.client.get(reverse("committee_hub"))
        self.assertContains(response, 'members-nav__count">1<')

    def test_inbox_is_committee_only(self):
        self.client.login(username="member", password="pw")
        self.assertEqual(self.client.get(reverse("committee_inbox")).status_code, 302)
        response = self.client.post(reverse("committee_inbox_toggle", args=["enquiry", self.enquiry.id]))
        self.assertEqual(response.status_code, 302)
        self.enquiry.refresh_from_db()
        self.assertFalse(self.enquiry.handled)

        response = self.client.get(reverse("members"))
        self.assertNotContains(response, "members-nav__count")

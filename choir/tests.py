import importlib
import json
import re
import tempfile
from io import StringIO
from unittest import mock
from datetime import datetime, timedelta

from allauth.account.models import EmailAddress
from anymail.message import AnymailRecipientStatus
from django.apps import apps as django_apps
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from invitations.utils import get_invitation_model

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
from .permissions import COMMITTEE_GROUP, is_committee

Invitation = get_invitation_model()


def create_committee_user(**kwargs):
    """A committee member: a user in the Committee group (choir.permissions
    .is_committee), which is all committee access depends on."""
    user = User.objects.create_user(**kwargs)
    user.groups.add(Group.objects.get_or_create(name=COMMITTEE_GROUP)[0])
    return user


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
        self.staff = create_committee_user(username="committee", password="pw")
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
        self.staff = create_committee_user(username="committee", password="pw")
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
    def test_send_does_not_crash_with_no_matching_recipients(self):
        # No users have voice_part "S" assigned, so recipients is empty.
        broadcast = ChoirCommunication.objects.create(
            audience="SOP",
            subject="Test subject",
            message="<p>Hello</p>",
        )
        self.assertEqual(broadcast.send(), (0, 0))
        self.assertEqual(broadcast.status, "SENT")


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
        self.staff = create_committee_user(username="committee", password="pw")
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
        broadcast = ChoirCommunication.objects.latest("id")
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
        self.staff = create_committee_user(username="committee", password="pw")
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
        self.staff = create_committee_user(username="committee", password="pw")
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
        create_committee_user(username="committee", password="pw")
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
        self.staff = create_committee_user(username="committee", password="pw")
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
        create_committee_user(username="committee", password="pw")
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
        create_committee_user(username="committee", password="pw")

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
        create_committee_user(username="committee", password="pw")
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
        create_committee_user(username="committee", password="pw")
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
        create_committee_user(username="committee", password="pw")
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
        create_committee_user(username="committee", password="pw")
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
        create_committee_user(username="committee", password="pw")
        self.member = User.objects.create_user(username="member", password="pw", last_name="Singer")

    def test_load_returns_the_seeded_row(self):
        # The data migration (0022) seeds pk=1 from the old hard-coded values
        choir_settings = ChoirSettings.load()
        self.assertEqual(choir_settings.pk, 1)
        self.assertEqual(choir_settings.current_term, "Autumn 2026")
        self.assertEqual(choir_settings.bank_sort_code, "23-05-80")
        self.assertEqual(ChoirSettings.objects.count(), 1)

    def test_load_recreates_a_missing_row_and_save_keeps_one_row(self):
        ChoirSettings.objects.all().delete()
        choir_settings = ChoirSettings.load()
        self.assertEqual(choir_settings.pk, 1)
        self.assertEqual(choir_settings.current_term, "")

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
        self.assertEqual(ChoirSettings.load().current_term, "Autumn 2026")

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
        self.committee = create_committee_user(username="committee", password="pw")
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


class CommitteeInboxBulkTests(TestCase):
    """The inbox's bulk actions: tick several items, then Mark handled or
    Delete as spam (added after the first deploy showed 143 spam enquiries)."""

    def setUp(self):
        self.committee = create_committee_user(username="committee", password="pw")
        User.objects.create_user(username="member", password="pw")
        self.spam = [
            Enquiry.objects.create(name=f"Spammer {n}", email=f"s{n}@example.com", message="Cheap SEO")
            for n in range(3)
        ]
        self.real = Enquiry.objects.create(name="Ann", email="ann@example.com", message="Wedding in June?")
        self.application = AuditionApplication.objects.create(
            name="Ben", email="ben@example.com", voice_part="tenor"
        )
        self.client.login(username="committee", password="pw")

    def bulk(self, action, items):
        return self.client.post(reverse("committee_inbox_bulk"), {"action": action, "items": items})

    def test_delete_removes_only_the_selected_items(self):
        response = self.client.post(
            reverse("committee_inbox_bulk"),
            {"action": "delete", "items": [f"enquiry:{e.id}" for e in self.spam]},
            follow=True,
        )
        self.assertRedirects(response, reverse("committee_inbox"))
        self.assertContains(response, "3 items deleted as spam.")
        self.assertEqual(list(Enquiry.objects.all()), [self.real])
        self.assertTrue(AuditionApplication.objects.exists())

    def test_mark_handled_covers_both_kinds_and_records_who(self):
        self.bulk("handled", [f"enquiry:{self.real.id}", f"audition:{self.application.id}"])
        self.real.refresh_from_db()
        self.application.refresh_from_db()
        self.assertTrue(self.real.handled and self.application.handled)
        self.assertEqual(self.real.handled_by, self.committee)
        self.assertFalse(Enquiry.objects.filter(id=self.spam[0].id, handled=True).exists())

    def test_malformed_or_unknown_items_are_ignored(self):
        self.bulk("delete", ["parcel:1", "enquiry:abc", "enquiry", f"audition:{self.application.id}:x"])
        self.assertEqual(Enquiry.objects.count(), 4)
        self.assertTrue(AuditionApplication.objects.exists())

    def test_unknown_action_changes_nothing(self):
        response = self.bulk("archive", [f"enquiry:{self.real.id}"])
        self.assertRedirects(response, reverse("committee_inbox"), fetch_redirect_response=False)
        self.assertTrue(Enquiry.objects.filter(id=self.real.id).exists())

    def test_inbox_renders_checkboxes_and_the_delete_confirmation(self):
        page = self.client.get(reverse("committee_inbox"))
        self.assertContains(page, f'value="enquiry:{self.real.id}" form="inbox-bulk"')
        self.assertContains(page, 'data-confirm="Delete the selected items for good?')
        self.assertContains(page, "js/select-all")

    def test_bulk_is_committee_only_and_post_only(self):
        self.assertEqual(self.client.get(reverse("committee_inbox_bulk")).status_code, 405)

        self.client.login(username="member", password="pw")
        response = self.bulk("delete", [f"enquiry:{e.id}" for e in self.spam])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Enquiry.objects.count(), 4)


COMMITTEE_VIEW_NAMES = [
    "committee_projects",
    "committee_polling",
    "committee_rsvps",
    "committee_broadcast",
    "committee_emergency",
    "committee_schedule",
    "committee_financials",
    "committee_settings",
    "committee_inbox",
]


class CommitteeAccessModelTests(TestCase):
    """Build Order Phase 5: committee access comes from the Committee group
    (or superuser), not Django's is_staff flag - with is_staff still
    honoured for this release so nobody is locked out mid-transition."""

    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name=COMMITTEE_GROUP)

    def assert_reaches_every_committee_view(self, username):
        self.client.login(username=username, password="pw")
        for name in COMMITTEE_VIEW_NAMES:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_group_member_who_is_not_staff_reaches_every_committee_view(self):
        user = User.objects.create_user(username="grouped", password="pw")
        user.groups.add(self.group)
        self.assertFalse(user.is_staff)
        self.assert_reaches_every_committee_view("grouped")

    def test_migration_0030_keeps_every_staff_users_access(self):
        migration = importlib.import_module("choir.migrations.0030_staff_into_committee_group")
        staffer = User.objects.create_user(username="staffer", password="pw", is_staff=True)
        member = User.objects.create_user(username="member", password="pw")
        self.assertFalse(is_committee(staffer))  # what would happen without it

        migration.add_staff(django_apps, None)
        migration.add_staff(django_apps, None)  # idempotent

        self.assertTrue(is_committee(User.objects.get(id=staffer.id)))
        self.assertFalse(is_committee(member))

    def test_staff_user_outside_the_group_gets_no_committee_access(self):
        # is_staff is Django admin access only; the Phase 5 transition is over
        User.objects.create_user(username="staffer", password="pw", is_staff=True)
        self.client.login(username="staffer", password="pw")
        for name in COMMITTEE_VIEW_NAMES:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_superuser_gets_in(self):
        User.objects.create_superuser(username="root", password="pw", email="root@example.com")
        self.assert_reaches_every_committee_view("root")

    def test_ordinary_member_and_inactive_group_member_are_refused(self):
        member = User.objects.create_user(username="member", password="pw")
        inactive = User.objects.create_user(username="gone", password="pw", is_active=False)
        inactive.groups.add(self.group)

        self.assertFalse(is_committee(member))
        self.assertFalse(is_committee(inactive))

        self.client.login(username="member", password="pw")
        self.assertEqual(self.client.get(reverse("committee_financials")).status_code, 302)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_group_member_sees_the_committee_nav_and_can_manage_the_vault(self):
        user = User.objects.create_user(username="grouped", password="pw")
        user.groups.add(self.group)
        self.client.login(username="grouped", password="pw")

        response = self.client.get(reverse("committee_documents"))
        self.assertContains(response, reverse("committee_financials"))
        self.assertContains(response, 'enctype="multipart/form-data"')

        document = CommitteeDocument.objects.create(
            title="Minutes", file=SimpleUploadedFile("m.pdf", b"%PDF-1.4")
        )
        self.client.post(reverse("committee_document_delete", args=[document.id]))
        self.assertFalse(CommitteeDocument.objects.filter(id=document.id).exists())

    def test_migration_puts_every_staff_user_in_the_group(self):
        migration = importlib.import_module("choir.migrations.0024_committee_group")
        staff = User.objects.create_user(username="staffer", password="pw", is_staff=True)
        member = User.objects.create_user(username="member", password="pw")
        Group.objects.filter(name=COMMITTEE_GROUP).delete()

        migration.create_group(django_apps, None)
        migration.create_group(django_apps, None)  # idempotent

        group = Group.objects.get(name=COMMITTEE_GROUP)
        self.assertEqual(list(group.user_set.all()), [staff])
        self.assertNotIn(member, group.user_set.all())


class NonSingerTests(TestCase):
    """Build Order Phase 5: a member with a login who doesn't sing gets no
    RSVPs and is left out of the ledger, RSVP report, Duty of Care roster,
    broadcasts and poll reminders - but can still log in and use the vault."""

    def setUp(self):
        self.committee = create_committee_user(username="committee", password="pw")
        self.singer = User.objects.create_user(username="singer", password="pw", email="singer@example.com")
        self.organist = User.objects.create_user(username="organist", password="pw", email="organist@example.com")
        self.organist.profile.is_singer = False
        self.organist.profile.save()
        self.project = Project.objects.create(name="Clent 2026", status="ACTIVE")

    def test_new_profiles_are_singers_by_default(self):
        self.assertTrue(User.objects.create_user(username="new", password="pw").profile.is_singer)

    def test_non_singer_gets_no_attendance_for_a_new_event(self):
        event = Event.objects.create(
            project=self.project, date_time=timezone.now() + timedelta(days=7), location="Hall"
        )
        self.assertTrue(Attendance.objects.filter(event=event, user=self.singer).exists())
        self.assertFalse(Attendance.objects.filter(event=event, user=self.organist).exists())

    def test_non_singers_dashboard_neither_backfills_rsvps_nor_asks_for_subs(self):
        Event.objects.create(project=self.project, date_time=timezone.now() + timedelta(days=7), location="Hall")
        self.client.login(username="organist", password="pw")
        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Attendance.objects.filter(user=self.organist).exists())
        self.assertNotContains(response, "Subscriptions Due")

    def test_non_singer_is_left_out_of_the_committee_lists(self):
        Event.objects.create(project=self.project, date_time=timezone.now() + timedelta(days=7), location="Hall")
        poll = AvailabilityPoll.objects.create(
            project=Project.objects.create(name="Easter 2027", status="PLANNING"), question="March?"
        )
        self.client.login(username="committee", password="pw")

        ledger = self.client.get(reverse("committee_financials"))
        self.assertNotIn(self.organist, [row["user"] for row in ledger.context["roster"]])
        self.assertIn(self.singer, [row["user"] for row in ledger.context["roster"]])

        roster = self.client.get(reverse("committee_emergency"))
        self.assertNotIn(self.organist, list(roster.context["roster"]))

        report = self.client.get(reverse("committee_rsvps"))
        self.assertNotIn(self.organist, [row["user"] for row in report.context["member_stats"]])
        pending = [rsvp.user for row in report.context["report_data"] for rsvp in row["pending"]]
        self.assertNotIn(self.organist, pending)

        polling = self.client.get(reverse("committee_polling"))
        row = next(r for r in polling.context["poll_data"] if r["poll"] == poll)
        self.assertNotIn(self.organist, list(row["non_responders"]))

    def test_broadcasts_go_to_singers_only(self):
        ChoirCommunication.objects.create(audience="ALL", subject="Rehearsal moved", message="<p>Hi</p>").send()
        recipients = [address for message in mail.outbox for address in message.to]
        self.assertIn("singer@example.com", recipients)
        self.assertNotIn("organist@example.com", recipients)

    def test_non_singer_can_still_use_the_vault(self):
        self.client.login(username="organist", password="pw")
        self.assertEqual(self.client.get(reverse("committee_documents")).status_code, 200)


class RepertoireLibraryTests(TestCase):
    """Build Order Phase 6: the committee adds pieces and uploads their
    scores and tracks on the site."""

    def setUp(self):
        create_committee_user(username="committee", password="pw")
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="committee", password="pw")
        self.piece = Repertoire.objects.create(composer="Byrd", title="Ave verum corpus")

    def upload(self, **data):
        payload = {"upload": "1", "voice_part": "SOP", "asset_name": "", "external_url": ""}
        payload.update(data)
        return self.client.post(reverse("committee_repertoire_detail", args=[self.piece.id]), payload)

    def pdf(self, name="Ave verum - Soprano.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")

    def test_create_piece_goes_to_its_upload_page(self):
        response = self.client.post(reverse("committee_repertoire"), {"composer": "Tallis", "title": "If ye love me"})
        piece = Repertoire.objects.get(title="If ye love me")
        self.assertRedirects(response, reverse("committee_repertoire_detail", args=[piece.id]))

    def test_adding_from_a_project_attaches_the_piece(self):
        project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.client.post(
            reverse("committee_repertoire"),
            {"composer": "Tallis", "title": "If ye love me", "project": project.id},
        )
        self.assertIn(Repertoire.objects.get(title="If ye love me"), project.repertoire.all())

    def test_library_lists_counts_and_searches(self):
        LearningAsset.objects.create(repertoire=self.piece, voice_part="SOP", asset_name="Sop", external_url="https://example.com")
        Repertoire.objects.create(composer="Tallis", title="If ye love me")

        response = self.client.get(reverse("committee_repertoire"))
        row = next(r for r in response.context["rows"] if r["piece"] == self.piece)
        self.assertEqual(row["counts"], [("Soprano", 1)])

        response = self.client.get(reverse("committee_repertoire"), {"q": "tallis"})
        self.assertEqual([r["piece"].title for r in response.context["rows"]], ["If ye love me"])

    def test_upload_pdf_creates_asset_named_after_the_file(self):
        response = self.upload(files=self.pdf(), voice_part="ALT")
        self.assertRedirects(response, reverse("committee_repertoire_detail", args=[self.piece.id]))
        asset = LearningAsset.objects.get(repertoire=self.piece)
        self.assertEqual(asset.voice_part, "ALT")
        self.assertEqual(asset.asset_name, "Ave verum - Soprano")
        self.assertIsNotNone(asset.uploaded_at)

    def test_single_file_uses_the_given_name(self):
        self.upload(files=self.pdf(), asset_name="Full score")
        self.assertEqual(LearningAsset.objects.get(repertoire=self.piece).asset_name, "Full score")

    def test_several_files_make_one_asset_each(self):
        self.upload(files=[self.pdf("Soprano.mp3"), self.pdf("Alto.m4a"), self.pdf("Score.pdf")], asset_name="Ignored")
        self.assertEqual(
            sorted(LearningAsset.objects.values_list("asset_name", flat=True)), ["Alto", "Score", "Soprano"]
        )

    def test_external_link_needs_a_name(self):
        response = self.upload(external_url="https://youtube.com/watch?v=x")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LearningAsset.objects.exists())

        self.upload(external_url="https://youtube.com/watch?v=x", asset_name="Recording")
        self.assertTrue(LearningAsset.objects.filter(asset_name="Recording").exists())

    def test_file_and_link_together_rejected(self):
        response = self.upload(files=self.pdf(), external_url="https://example.com", asset_name="X")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LearningAsset.objects.exists())

    def test_neither_file_nor_link_rejected(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["upload_form"].non_field_errors())

    def test_wrong_file_type_rejected(self):
        response = self.upload(files=SimpleUploadedFile("virus.exe", b"MZ"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LearningAsset.objects.exists())

    def test_oversize_file_rejected(self):
        with mock.patch("choir.forms.ASSET_MAX_BYTES", 5):
            response = self.upload(files=self.pdf())
        self.assertContains(response, "over 50 MB")
        self.assertFalse(LearningAsset.objects.exists())

    def test_delete_removes_the_row_and_the_stored_file(self):
        self.upload(files=self.pdf())
        asset = LearningAsset.objects.get()
        stored_name = asset.file_upload.name
        storage = asset.file_upload.storage
        self.assertTrue(storage.exists(stored_name))

        response = self.client.post(reverse("committee_asset_delete", args=[asset.id]))
        self.assertRedirects(response, reverse("committee_repertoire_detail", args=[self.piece.id]))
        self.assertFalse(LearningAsset.objects.exists())
        self.assertFalse(storage.exists(stored_name))

    def test_rename_piece(self):
        self.client.post(
            reverse("committee_repertoire_detail", args=[self.piece.id]),
            {"composer": "William Byrd", "title": "Ave verum corpus"},
        )
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.composer, "William Byrd")

    def test_project_edit_links_to_its_pieces_and_add_piece(self):
        project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        project.repertoire.add(self.piece)
        response = self.client.get(reverse("committee_project_edit", args=[project.id]))
        self.assertContains(response, reverse("committee_repertoire_detail", args=[self.piece.id]))
        self.assertContains(response, f"{reverse('committee_repertoire')}?project={project.id}")

    def test_hub_shows_the_upload_date_when_known(self):
        project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        project.repertoire.add(self.piece)
        LearningAsset.objects.create(repertoire=self.piece, voice_part="SOP", asset_name="New", external_url="https://example.com")
        old = LearningAsset.objects.create(repertoire=self.piece, voice_part="SOP", asset_name="Old", external_url="https://example.com")
        LearningAsset.objects.filter(id=old.id).update(uploaded_at=None)  # predates the field

        self.client.login(username="member", password="pw")
        response = self.client.get(reverse("hub", args=["soprano", project.id]))
        # Only the asset with a known upload date shows one
        self.assertContains(response, "· added", count=1)

    def test_library_urls_are_committee_only(self):
        asset = LearningAsset.objects.create(repertoire=self.piece, voice_part="SOP", asset_name="A", external_url="https://example.com")
        self.client.login(username="member", password="pw")
        for method, url in [
            ("get", reverse("committee_repertoire")),
            ("get", reverse("committee_repertoire_detail", args=[self.piece.id])),
            ("post", reverse("committee_asset_delete", args=[asset.id])),
        ]:
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, method)(url).status_code, 302)
        self.assertTrue(LearningAsset.objects.filter(id=asset.id).exists())


class PracticePlayerTests(TestCase):
    """Build Order Phase 7 (Learning Hub P1): the voice-part hub embeds the
    practice player's track list, and hub_tracks serves fresh URLs."""

    def setUp(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")
        self.project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.other = Project.objects.create(name="Ewelme 2027", status="ACTIVE")
        self.piece = Repertoire.objects.create(composer="Byrd", title="Ave verum")
        self.other_piece = Repertoire.objects.create(composer="Tallis", title="If ye love me")
        self.project.repertoire.add(self.piece)
        self.other.repertoire.add(self.other_piece)

        def asset(piece, part, name, filename=None, url=None):
            return LearningAsset.objects.create(
                repertoire=piece,
                voice_part=part,
                asset_name=name,
                file_upload=SimpleUploadedFile(filename, b"ID3") if filename else None,
                external_url=url,
            )

        self.sop_track = asset(self.piece, "SOP", "Soprano track", "sop.mp3")
        self.full_track = asset(self.piece, "ALL", "Full choir", "full.m4a")
        self.alto_track = asset(self.piece, "ALT", "Alto track", "alto.mp3")
        self.score = asset(self.piece, "ALL", "Score", "score.pdf")
        self.youtube = asset(self.piece, "SOP", "YouTube", url="https://youtube.com/x")
        self.elsewhere = asset(self.other_piece, "SOP", "Other project", "other.mp3")

    def player_ids(self, response):
        return sorted(track["id"] for track in response.context["player_data"]["tracks"])

    def test_hub_embeds_only_this_projects_audio_for_this_part(self):
        response = self.client.get(reverse("hub", args=["soprano", self.project.id]))
        self.assertEqual(self.player_ids(response), sorted([self.sop_track.id, self.full_track.id]))
        self.assertContains(response, 'id="player-data"')
        self.assertContains(response, "js/practice-player")
        self.assertContains(response, f'data-player-load="{self.sop_track.id}"')
        # The PDF and the link keep their own buttons
        self.assertContains(response, "Open Score")
        self.assertContains(response, "External Link")

    def test_track_entries_carry_what_the_player_shows(self):
        response = self.client.get(reverse("hub", args=["soprano", self.project.id]))
        track = next(t for t in response.context["player_data"]["tracks"] if t["id"] == self.sop_track.id)
        self.assertEqual(track["name"], "Soprano track")
        self.assertEqual(track["piece"], "Ave verum")
        self.assertTrue(track["url"])
        self.assertEqual(
            response.context["player_data"]["refreshUrl"],
            reverse("hub_tracks", args=["soprano", self.project.id]),
        )

    def test_no_player_without_audio(self):
        LearningAsset.objects.filter(file_upload__endswith=".mp3").delete()
        LearningAsset.objects.filter(file_upload__endswith=".m4a").delete()
        response = self.client.get(reverse("hub", args=["soprano", self.project.id]))
        self.assertNotContains(response, 'id="player-data"')
        self.assertNotContains(response, "practice-player")

    def test_tracks_endpoint_returns_this_projects_tracks_for_the_part(self):
        response = self.client.get(reverse("hub_tracks", args=["alto", self.project.id]))
        self.assertEqual(response.status_code, 200)
        ids = sorted(track["id"] for track in response.json()["tracks"])
        self.assertEqual(ids, sorted([self.alto_track.id, self.full_track.id]))

    def test_tracks_endpoint_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("hub_tracks", args=["soprano", self.project.id]))
        self.assertEqual(response.status_code, 302)

    def test_tracks_endpoint_404s_for_a_project_that_isnt_active(self):
        archived = Project.objects.create(name="Old", status="ARCHIVED")
        response = self.client.get(reverse("hub_tracks", args=["soprano", archived.id]))
        self.assertEqual(response.status_code, 404)

    def test_unknown_part_gets_no_tracks(self):
        response = self.client.get(reverse("hub_tracks", args=["kazoo", self.project.id]))
        self.assertEqual(response.json()["tracks"], [])


class MemberInvitationTests(TestCase):
    """Build Order Phase 8: the committee invites new members from the site,
    and what they knew about them (name, voice part) is applied when the
    invitee signs up."""

    def setUp(self):
        self.committee = create_committee_user(username="committee", password="pw", email="committee@example.com")
        User.objects.create_user(username="member", password="pw", email="member@example.com")
        self.client.login(username="committee", password="pw")

    def invite(self, **data):
        payload = {"email": "new.singer@example.com", "first_name": "", "last_name": "", "voice_part": ""}
        payload.update(data)
        return self.client.post(reverse("committee_members"), payload)

    def test_invite_creates_an_invitation_and_sends_one_email(self):
        response = self.invite(first_name="Nia", last_name="Newsinger", voice_part="A")
        self.assertRedirects(response, reverse("committee_members"))

        invitation = Invitation.objects.get(email="new.singer@example.com")
        self.assertEqual(invitation.inviter, self.committee)
        self.assertIsNotNone(invitation.sent)
        self.assertEqual(invitation.choir_profile.voice_part, "A")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new.singer@example.com"])
        self.assertIn(invitation.key, mail.outbox[0].body + "".join(a[0] for a in getattr(mail.outbox[0], "alternatives", [])))

    def test_existing_account_or_repeat_invite_is_refused(self):
        response = self.invite(email="MEMBER@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already has an account")

        self.invite()
        response = self.invite()
        self.assertContains(response, "already been invited")
        self.assertEqual(Invitation.objects.count(), 1)

    def test_pending_invitation_is_listed_and_can_be_resent(self):
        self.invite()
        invitation = Invitation.objects.get()
        Invitation.objects.filter(id=invitation.id).update(sent=timezone.now() - timedelta(days=10))

        page = self.client.get(reverse("committee_members"))
        self.assertContains(page, "new.singer@example.com")
        self.assertContains(page, "Expired")

        self.client.post(reverse("committee_invitation_resend", args=[invitation.id]))
        invitation.refresh_from_db()
        self.assertFalse(invitation.key_expired())
        self.assertEqual(len(mail.outbox), 2)

    def test_accepting_creates_a_user_with_the_chosen_voice_part_and_name(self):
        self.invite(first_name="Nia", last_name="Newsinger", voice_part="A")
        invitation = Invitation.objects.get()
        self.client.logout()

        self.client.get(reverse("invitations:accept-invite", args=[invitation.key]))
        response = self.client.post(
            reverse("account_signup"),
            {"email": "new.singer@example.com", "password1": "a-Long-pass-phrase-9", "password2": "a-Long-pass-phrase-9"},
        )
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="new.singer@example.com")
        self.assertEqual(user.profile.voice_part, "A")
        self.assertEqual((user.first_name, user.last_name), ("Nia", "Newsinger"))
        self.assertTrue(user.profile.is_singer)
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)

    def test_invitation_pages_are_committee_only(self):
        self.invite()
        invitation = Invitation.objects.get()
        self.client.login(username="member", password="pw")
        self.assertEqual(self.client.get(reverse("committee_members")).status_code, 302)
        response = self.client.post(reverse("committee_members"), {"email": "x@example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.post(reverse("committee_invitation_resend", args=[invitation.id])).status_code, 302)
        self.assertEqual(Invitation.objects.count(), 1)


class MemberManagementTests(TestCase):
    """Build Order Phase 8: editing members, roles and leavers."""

    def setUp(self):
        self.committee = create_committee_user(username="committee", password="pw")
        self.committee.groups.add(Group.objects.get_or_create(name=COMMITTEE_GROUP)[0])
        self.singer = User.objects.create_user(username="singer", password="pw", first_name="Sam")
        self.client.login(username="committee", password="pw")

    def edit_payload(self, **overrides):
        payload = {
            "first_name": "Sam",
            "last_name": "Singer",
            "voice_part": "T",
            "is_singer": "on",
            "is_active": "on",
        }
        payload.update(overrides)
        return {k: v for k, v in payload.items() if v is not None}

    def test_members_list_and_filters(self):
        self.singer.profile.voice_part = "T"
        self.singer.profile.save()
        gone = User.objects.create_user(username="gone", password="pw", is_active=False)

        response = self.client.get(reverse("committee_members"))
        users = [row["user"] for row in response.context["rows"]]
        self.assertIn(self.singer, users)
        self.assertNotIn(gone, users)

        response = self.client.get(reverse("committee_members"), {"status": "inactive"})
        self.assertEqual([row["user"] for row in response.context["rows"]], [gone])

        response = self.client.get(reverse("committee_members"), {"part": "T"})
        self.assertEqual([row["user"] for row in response.context["rows"]], [self.singer])

    def test_edit_saves_details_flags_and_committee(self):
        response = self.client.post(
            reverse("committee_member_edit", args=[self.singer.id]),
            self.edit_payload(is_under_18="on", committee="on", is_singer=None),
        )
        self.assertRedirects(response, reverse("committee_members"))
        self.singer.refresh_from_db()
        self.assertEqual(self.singer.last_name, "Singer")
        self.assertEqual(self.singer.profile.voice_part, "T")
        self.assertTrue(self.singer.profile.is_under_18)
        self.assertFalse(self.singer.profile.is_singer)
        self.assertTrue(is_committee(self.singer))

        self.client.post(reverse("committee_member_edit", args=[self.singer.id]), self.edit_payload())
        self.assertFalse(is_committee(self.singer))

    def test_committee_cant_deactivate_themselves_or_drop_their_own_committee_access(self):
        response = self.client.post(
            reverse("committee_member_edit", args=[self.committee.id]),
            self.edit_payload(is_active=None, committee=None),
        )
        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        self.assertIn("can't deactivate your own account", " ".join(errors["is_active"]))
        self.assertIn("can't remove your own committee access", " ".join(errors["committee"]))
        self.committee.refresh_from_db()
        self.assertTrue(self.committee.is_active)
        self.assertTrue(self.committee.groups.filter(name=COMMITTEE_GROUP).exists())

    def test_deactivated_member_is_signed_out_and_redirected_to_login(self):
        member_client = self.client_class()
        member_client.login(username="singer", password="pw")
        self.assertEqual(member_client.get(reverse("members")).status_code, 200)

        self.client.post(reverse("committee_member_edit", args=[self.singer.id]), self.edit_payload(is_active=None))
        self.singer.refresh_from_db()
        self.assertFalse(self.singer.is_active)

        response = member_client.get(reverse("members"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_unticking_committee_removes_access_even_for_a_staff_user(self):
        staffer = create_committee_user(username="staffer", password="pw", is_staff=True)
        self.client.post(reverse("committee_member_edit", args=[staffer.id]), self.edit_payload())
        self.assertFalse(is_committee(User.objects.get(id=staffer.id)))

    def test_edit_page_is_committee_only(self):
        self.client.login(username="singer", password="pw")
        response = self.client.post(
            reverse("committee_member_edit", args=[self.committee.id]), self.edit_payload(is_active=None)
        )
        self.assertEqual(response.status_code, 302)
        self.committee.refresh_from_db()
        self.assertTrue(self.committee.is_active)


class PublicEventsPageTests(TestCase):
    """Build Order Phase 9: the public Events page from public residency
    events, behind ChoirSettings.events_page_from_db."""

    def setUp(self):
        self.project = Project.objects.create(name="Ewelme 2027", status="ACTIVE", public_summary="Passion Sunday at Ewelme.")
        self.piece = Repertoire.objects.create(composer="Lotti", title="Crucifixus")
        self.project.repertoire.add(self.piece)

    def public_event(self, days, **kwargs):
        defaults = {
            "project": self.project,
            "event_type": "RES",
            "is_public": True,
            "date_time": timezone.now() + timedelta(days=days),
            "location": f"Venue {days}",
        }
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def switch_on(self):
        choir_settings = ChoirSettings.load()
        choir_settings.events_page_from_db = True
        choir_settings.save()

    def test_flag_off_renders_the_static_page(self):
        self.public_event(10, public_title="Should not show")
        response = self.client.get(reverse("events"))
        self.assertTemplateUsed(response, "choir/events.html")
        self.assertNotContains(response, "Should not show")

    def test_flag_on_puts_events_in_the_right_places(self):
        self.switch_on()
        later = self.public_event(40, public_title="Later concert")
        soon = self.public_event(10, public_title="Next concert")
        past = [self.public_event(-30 * n, public_title=f"Past {n}") for n in range(1, 6)]

        response = self.client.get(reverse("events"))
        self.assertTemplateUsed(response, "choir/events_db.html")
        self.assertEqual(response.context["next_event"], soon)
        self.assertEqual(response.context["recent_events"], past[:3])
        self.assertEqual(response.context["archive_events"], past[3:])
        self.assertContains(response, "Next concert")
        self.assertContains(response, "Lotti: Crucifixus")  # recent cards list repertoire
        self.assertNotIn(later, response.context["recent_events"])

    def test_rehearsals_and_non_public_events_never_appear(self):
        self.switch_on()
        self.public_event(5, event_type="REH", public_title="Secret rehearsal")
        self.public_event(6, is_public=False, public_title="Not announced")
        self.public_event(-5, event_type="REH", public_title="Old rehearsal")

        response = self.client.get(reverse("events"))
        self.assertIsNone(response.context["next_event"])
        self.assertEqual(response.context["recent_events"], [])
        for text in ("Secret rehearsal", "Not announced", "Old rehearsal"):
            self.assertNotContains(response, text)
        self.assertContains(response, "being confirmed")

    def test_midnight_start_shows_time_tbc_and_summary_falls_back_to_project(self):
        self.switch_on()
        midnight = timezone.localtime(timezone.now() + timedelta(days=20)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.public_event(20, date_time=midnight)
        response = self.client.get(reverse("events"))
        self.assertContains(response, "time TBC")
        self.assertContains(response, "Passion Sunday at Ewelme.")


class EventArchiveImportTests(TestCase):
    """import_event_archive brings the static page's past performances in
    as public events, without RSVPs, and can be re-run safely."""

    def setUp(self):
        User.objects.create_user(username="singer", password="pw")

    def test_import_creates_public_past_events_without_rsvps(self):
        call_command("import_event_archive", stdout=StringIO())
        events = Event.objects.all()
        self.assertEqual(events.count(), 29)
        self.assertTrue(all(e.is_public and e.event_type == "RES" for e in events))
        self.assertFalse(Attendance.objects.exists())

        ludlow = Event.objects.get(location="St Lawrence's Church, Ludlow")
        self.assertEqual((ludlow.date_time.year, ludlow.date_time.month), (2026, 3))  # visible date, not the tag
        self.assertEqual(ludlow.project.status, "ARCHIVED")
        self.assertEqual(ludlow.project.repertoire.count(), 6)
        self.assertEqual(Event.objects.get(location="Rochester Cathedral").project.name, "Performance archive 2024")

    def test_import_is_idempotent_and_dry_run_saves_nothing(self):
        call_command("import_event_archive", "--dry-run", stdout=StringIO())
        self.assertFalse(Event.objects.exists())

        call_command("import_event_archive", stdout=StringIO())
        out = StringIO()
        call_command("import_event_archive", stdout=out)
        self.assertEqual(Event.objects.count(), 29)
        self.assertIn("29 already present", out.getvalue())


class EventPublicFieldsAndCalendarTests(TestCase):
    """The event edit form's public listing fields, the settings switch,
    and calendar files using end_time."""

    def setUp(self):
        create_committee_user(username="committee", password="pw")
        self.client.login(username="committee", password="pw")
        self.project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.event = Event.objects.create(
            project=self.project,
            event_type="RES",
            date_time=timezone.make_aware(datetime(2026, 12, 6, 18, 0)),
            location="St Leonard's Church, Clent",
            additional_notes="<p>Bring folders, black dress</p>",
        )

    def test_edit_saves_the_public_listing(self):
        response = self.client.post(
            reverse("committee_event_edit", args=[self.event.id]),
            {
                "project": self.project.id,
                "event_type": "RES",
                "date_time": "2026-12-06T18:00",
                "location": "St Leonard's Church, Clent",
                "is_public": "on",
                "public_title": "Advent Carols",
                "public_blurb": "Readings and carols by candlelight.",
                "ticket_url": "https://tickets.example.com",
                "end_time": "2026-12-06T19:30",
            },
        )
        self.assertRedirects(response, reverse("committee_schedule"))
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_public)
        self.assertEqual(self.event.public_title, "Advent Carols")
        self.assertEqual(timezone.localtime(self.event.end_time).strftime("%H:%M"), "19:30")

    def test_end_before_start_is_refused(self):
        response = self.client.post(
            reverse("committee_event_edit", args=[self.event.id]),
            {
                "project": self.project.id,
                "event_type": "RES",
                "date_time": "2026-12-06T18:00",
                "location": "Clent",
                "end_time": "2026-12-06T17:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("end_time", response.context["form"].errors)

    def test_settings_switch_turns_the_database_page_on(self):
        choir_settings = ChoirSettings.load()
        self.client.post(
            reverse("committee_settings"),
            {
                "current_term": choir_settings.current_term,
                "subscription_amount": "50.00",
                "events_page_from_db": "on",
            },
        )
        self.assertTrue(ChoirSettings.load().events_page_from_db)

    def test_calendar_file_uses_end_time_and_escapes_text(self):
        self.event.end_time = self.event.date_time + timedelta(minutes=90)
        self.event.save()
        response = self.client.get(reverse("download_ics", args=[self.event.id]))
        body = response.content.decode()
        self.assertIn("DTSTART:20261206T180000Z", body)
        self.assertIn("DTEND:20261206T193000Z", body)
        self.assertIn("LOCATION:St Leonard's Church\\, Clent", body)
        self.assertIn("\r\nEND:VCALENDAR\r\n", body)

    def test_calendar_file_defaults_to_two_hours(self):
        body = self.client.get(reverse("download_ics", args=[self.event.id])).content.decode()
        self.assertIn("DTEND:20261206T200000Z", body)

    def test_project_feed_lists_every_event_and_needs_login(self):
        Event.objects.create(project=self.project, date_time=self.event.date_time + timedelta(days=7), location="Hall")
        response = self.client.get(reverse("project_calendar_ics", args=[self.project.id]))
        body = response.content.decode()
        self.assertEqual(body.count("BEGIN:VEVENT"), 2)
        self.assertIn("X-WR-CALNAME:Clent Consort: Clent 2026", body)

        self.client.logout()
        response = self.client.get(reverse("project_calendar_ics", args=[self.project.id]))
        self.assertEqual(response.status_code, 302)


class PublicMobilePassTests(TestCase):
    """Build Order Phase 10: the markup behind the public pages' phone
    layout (the layout itself was checked in a browser at 375/768/1366)."""

    def test_home_intro_shows_the_next_public_performance_when_the_events_page_is_built_from_events(self):
        project = Project.objects.create(name="Ewelme 2027", status="ACTIVE")
        Event.objects.create(
            project=project,
            event_type="RES",
            is_public=True,
            public_title="Choral Evensong",
            date_time=timezone.now() + timedelta(days=30),
            location="St Mary the Virgin, Ewelme",
        )

        response = self.client.get(reverse("home"))
        self.assertContains(response, 'class="home-intro')
        self.assertIsNone(response.context["next_event"])  # switch off: no event

        choir_settings = ChoirSettings.load()
        choir_settings.events_page_from_db = True
        choir_settings.save()
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Choral Evensong")
        self.assertContains(response, "St Mary the Virgin, Ewelme")

    def test_about_videos_dont_autoplay_or_preload(self):
        response = self.client.get(reverse("about"))
        content = response.content.decode()
        self.assertEqual(content.count("<video"), 3)
        self.assertNotIn("<video autoplay", content)
        self.assertEqual(content.count('preload="none"'), 3)
        self.assertEqual(content.count("data-rhythm-play"), 3)
        self.assertContains(response, '<h1 class="visually-hidden">About Clent Consort</h1>', html=True)
        self.assertContains(response, 'title="Clent Consort repertoire playlist on Spotify"')

    def test_every_page_has_the_menu_backdrop_and_the_events_cta_shortens(self):
        response = self.client.get(reverse("events"))
        self.assertContains(response, "data-nav-backdrop")
        self.assertContains(response, 'Enquire<span class="cta-more"> for More Information</span>')


class BroadcastWorkflowTests(TestCase):
    """Build Order Phase 11: broadcasts are drafted, previewed, tested on
    the author, then sent once - in one batch API call that gives each
    singer a private copy - with a delivery record per recipient."""

    def setUp(self):
        self.committee = create_committee_user(username="committee", password="pw", email="committee@example.com")
        # Not a singer, so the recipients are just the three singers below
        self.committee.profile.is_singer = False
        self.committee.profile.save()
        self.singers = []
        for name, part in [("sop", "S"), ("alto", "A"), ("alto2", "A")]:
            user = User.objects.create_user(username=name, password="pw", email=f"{name}@example.com")
            user.profile.voice_part = part
            user.profile.save()
            self.singers.append(user)
        User.objects.create_user(username="noemail", password="pw")  # singer without an address
        self.client.login(username="committee", password="pw")

    def draft(self, **kwargs):
        defaults = {"audience": "ALL", "subject": "Rehearsal moved", "message": "<p>Tuesday this week.</p>", "author": self.committee}
        defaults.update(kwargs)
        return ChoirCommunication.objects.create(**defaults)

    def test_saving_a_draft_sends_nothing_and_goes_to_the_preview(self):
        response = self.client.post(
            reverse("committee_broadcast"),
            {"audience": "ALL", "subject": "Rehearsal moved", "message": "<p>Tuesday this week.</p>"},
        )
        draft = ChoirCommunication.objects.get()
        self.assertRedirects(response, reverse("committee_broadcast_preview", args=[draft.id]))
        self.assertEqual(draft.status, "DRAFT")
        self.assertIsNone(draft.sent_at)
        self.assertEqual(mail.outbox, [])

    def test_preview_shows_the_email_and_who_it_goes_to(self):
        draft = self.draft(audience="ALT")
        response = self.client.get(reverse("committee_broadcast_preview", args=[draft.id]))
        self.assertEqual(response.context["recipient_count"], 2)  # the two altos
        self.assertContains(response, "<p>Tuesday this week.</p>", html=True)
        self.assertContains(response, "Send to 2 Singers")

    def test_send_a_test_to_me(self):
        draft = self.draft()
        self.client.post(reverse("committee_broadcast_test", args=[draft.id]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["committee@example.com"])
        self.assertEqual(mail.outbox[0].subject, "[Test] Rehearsal moved")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "DRAFT")

    def test_sending_needs_the_confirmation_box(self):
        draft = self.draft()
        self.client.post(reverse("committee_broadcast_send", args=[draft.id]))
        draft.refresh_from_db()
        self.assertEqual(draft.status, "DRAFT")
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_BACKEND="anymail.backends.test.EmailBackend")
    def test_send_is_one_private_batch_with_a_delivery_record_each(self):
        draft = self.draft()
        self.client.post(reverse("committee_broadcast_send", args=[draft.id]), {"confirm": "yes"})

        draft.refresh_from_db()
        self.assertEqual(draft.status, "SENT")
        self.assertIsNotNone(draft.sent_at)

        self.assertEqual(len(mail.outbox), 1)  # one API call...
        message = mail.outbox[0]
        self.assertTrue(message.anymail_test_params["is_batch_send"])  # ...a private copy each
        self.assertEqual(sorted(message.to), sorted(u.email for u in self.singers))
        self.assertEqual(message.alternatives[0][1], "text/html")

        deliveries = draft.deliveries.all()
        self.assertEqual(sorted(d.user.username for d in deliveries), ["alto", "alto2", "sop"])
        self.assertTrue(all(d.sent_ok for d in deliveries))

    def test_a_broadcast_is_never_sent_twice(self):
        draft = self.draft()
        self.client.post(reverse("committee_broadcast_send", args=[draft.id]), {"confirm": "yes"})
        self.client.post(reverse("committee_broadcast_send", args=[draft.id]), {"confirm": "yes"})
        self.assertEqual(len(mail.outbox), 1)
        with self.assertRaises(ValueError):
            ChoirCommunication.objects.get(id=draft.id).send()

    def test_a_failed_send_is_recorded_per_recipient_not_raised(self):
        draft = self.draft()
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=ConnectionError("Brevo down")):
            response = self.client.post(
                reverse("committee_broadcast_send", args=[draft.id]), {"confirm": "yes"}, follow=True
            )
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "SENT")  # marked first, so it can't go twice
        deliveries = draft.deliveries.all()
        self.assertEqual(deliveries.count(), 3)
        self.assertTrue(all(not d.sent_ok and "Brevo down" in d.error for d in deliveries))
        self.assertContains(response, "t be delivered (listed below)")

    @override_settings(
        EMAIL_BACKEND="anymail.backends.test.EmailBackend",
        ANYMAIL={"TEST_RECIPIENT_STATUS": "rejected"},
    )
    def test_rejected_recipients_are_marked_failed(self):
        draft = self.draft(audience="SOP")
        with mock.patch(
            "anymail.backends.test.EmailBackend.parse_recipient_status",
            return_value={"sop@example.com": AnymailRecipientStatus(message_id="x", status="rejected")},
        ):
            sent_ok, failed = draft.send()
        self.assertEqual((sent_ok, failed), (0, 1))
        self.assertIn("rejected", draft.deliveries.get().error)

    def test_drafts_can_be_edited_and_deleted_but_sent_ones_cant(self):
        draft = self.draft()
        response = self.client.post(
            reverse("committee_broadcast_edit", args=[draft.id]),
            {"audience": "SOP", "subject": "Rehearsal moved (again)", "message": "<p>Wednesday.</p>"},
        )
        self.assertRedirects(response, reverse("committee_broadcast_preview", args=[draft.id]))
        draft.refresh_from_db()
        self.assertEqual(draft.subject, "Rehearsal moved (again)")

        draft.send()
        self.client.post(
            reverse("committee_broadcast_edit", args=[draft.id]),
            {"audience": "ALL", "subject": "Changed after sending", "message": "<p>x</p>"},
        )
        self.client.post(reverse("committee_broadcast_delete", args=[draft.id]))
        draft.refresh_from_db()
        self.assertEqual(draft.subject, "Rehearsal moved (again)")

        other = self.draft(subject="Never mind")
        self.client.post(reverse("committee_broadcast_delete", args=[other.id]))
        self.assertFalse(ChoirCommunication.objects.filter(id=other.id).exists())

    def test_list_shows_drafts_and_sent_with_delivery_counts(self):
        self.draft(subject="Still a draft")
        sent = self.draft(subject="Gone out")
        sent.send()
        response = self.client.get(reverse("committee_broadcasts"))
        self.assertEqual([b.subject for b in response.context["drafts"]], ["Still a draft"])
        row = response.context["sent"].get(id=sent.id)
        self.assertEqual((row.delivered, row.failed), (3, 0))

    def test_migration_marks_older_broadcasts_sent(self):
        migration = importlib.import_module("choir.migrations.0029_mark_existing_broadcasts_sent")
        old = self.draft()
        ChoirCommunication.objects.filter(id=old.id).update(sent_at=timezone.now())
        fresh_draft = self.draft(subject="A real draft")
        migration.mark_sent(django_apps, None)
        self.assertEqual(ChoirCommunication.objects.get(id=old.id).status, "SENT")
        self.assertEqual(ChoirCommunication.objects.get(id=fresh_draft.id).status, "DRAFT")

    def test_broadcast_pages_are_committee_only(self):
        draft = self.draft()
        self.client.login(username="sop", password="pw")
        for method, name in [
            ("get", "committee_broadcasts"),
            ("get", "committee_broadcast_preview"),
            ("post", "committee_broadcast_test"),
            ("post", "committee_broadcast_send"),
            ("post", "committee_broadcast_delete"),
        ]:
            with self.subTest(view=name):
                args = [] if name == "committee_broadcasts" else [draft.id]
                response = getattr(self.client, method)(reverse(name, args=args), {"confirm": "yes"} if method == "post" else None)
                self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "DRAFT")
        self.assertEqual(mail.outbox, [])


class RsvpReportQueryCountTests(TestCase):
    """Phase 11 clean-up: the RSVP report runs a fixed number of queries,
    however many events and singers there are."""

    def setUp(self):
        create_committee_user(username="committee", password="pw")
        self.client.login(username="committee", password="pw")
        self.project = Project.objects.create(name="Clent 2026", status="ACTIVE")

    def add(self, events, singers):
        for n in range(singers):
            User.objects.create_user(username=f"singer{User.objects.count()}", password="pw", email=f"s{n}@example.com")
        for n in range(events):
            Event.objects.create(project=self.project, date_time=timezone.now() + timedelta(days=n + 1), location="Hall")

    def queries_for_report(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(reverse("committee_rsvps")).status_code, 200)
        return len(queries)

    def test_query_count_doesnt_grow_with_events_or_singers(self):
        self.add(events=2, singers=2)
        small = self.queries_for_report()
        self.add(events=6, singers=8)
        self.assertEqual(self.queries_for_report(), small)


class TemplateAccessibilityRulesTests(TestCase):
    """Phase 11 clean-up rules every template keeps: links opening a new tab
    carry rel="noopener", and data tables have a caption and column scope."""

    def templates(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent / "templates"
        for path in root.rglob("*.html"):
            yield path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")

    def test_new_tab_links_use_noopener(self):
        offenders = []
        for name, text in self.templates():
            for tag in re.findall(r"<a\b[^>]*>", text, re.S):
                if 'target="_blank"' in tag and "noopener" not in tag:
                    offenders.append(f"{name}: {tag[:80]}")
        self.assertEqual(offenders, [])

    def test_data_tables_have_a_caption_and_scoped_headers(self):
        offenders = []
        for name, text in self.templates():
            for table in re.findall(r'<table class="data-table">.*?</table>', text, re.S):
                if "<caption" not in table:
                    offenders.append(f"{name}: no caption")
                if re.search(r"<th(?=[ >])(?![^>]*scope=)", table):
                    offenders.append(f"{name}: <th> without scope")
        self.assertEqual(offenders, [])


class CommitteeNavPanelTests(TestCase):
    """On phones the committee links sit in their own panel, opened by a
    Committee button at the end of the members nav reel."""

    def test_committee_links_sit_in_the_panel_not_the_reel(self):
        create_committee_user(username="committee", password="pw")
        self.client.login(username="committee", password="pw")
        html = self.client.get(reverse("committee_financials")).content.decode()

        reel = re.search(r'<ul class="members-nav__list reel".*?</ul>', html, re.S).group(0)
        panel = re.search(r"<div class=\"members-nav__committee\".*?</div>", html, re.S).group(0)
        self.assertIn("data-committee-toggle", reel)
        self.assertNotIn(reverse("committee_financials"), reel)
        self.assertIn(reverse("committee_financials"), panel)
        self.assertIn(reverse("committee_settings"), panel)
        self.assertIn('aria-controls="members-nav-committee"', reel)

    def test_members_get_no_committee_button_or_panel(self):
        User.objects.create_user(username="member", password="pw")
        self.client.login(username="member", password="pw")
        html = self.client.get(reverse("members")).content.decode()
        self.assertNotIn("data-committee-toggle", html)
        self.assertNotIn("data-committee-panel", html)
        self.assertIn("Document Vault", html)


class RsvpOverviewNoRepliesTests(TestCase):
    """A singer who hasn't answered any RSVP has no attendance rate yet,
    rather than a 0% that reads as never attending."""

    def setUp(self):
        create_committee_user(username="committee", password="pw")
        self.client.login(username="committee", password="pw")
        project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        self.keen = User.objects.create_user(username="keen", password="pw", first_name="Keen")
        self.new = User.objects.create_user(username="new", password="pw", first_name="New")
        self.away = User.objects.create_user(username="away", password="pw", first_name="Away")
        Event.objects.create(project=project, date_time=timezone.now() + timedelta(days=1), location="Hall")
        Attendance.objects.filter(user=self.keen).update(status="ATTENDING")
        Attendance.objects.filter(user=self.away).update(status="ABSENT")

    def stats(self):
        response = self.client.get(reverse("committee_rsvps"))
        return {stat["user"].username: stat for stat in response.context["member_stats"]}, response

    def test_no_replies_gives_no_rate(self):
        stats, response = self.stats()
        self.assertIsNone(stats["new"]["rate"])
        self.assertEqual(stats["keen"]["rate"], 100)
        self.assertEqual(stats["away"]["rate"], 0)
        self.assertContains(response, "No replies yet")

    def test_singers_without_replies_sort_last(self):
        response = self.client.get(reverse("committee_rsvps"))
        order = [stat["user"].username for stat in response.context["member_stats"]]
        self.assertEqual(order[0], "away")
        self.assertEqual(order[-1], "new")


class CommitteeEventsNavLabelTests(TestCase):
    """The committee's schedule link is called Events, so the members nav
    doesn't have two links called Schedule."""

    def test_only_one_schedule_link(self):
        create_committee_user(username="committee", password="pw")
        self.client.login(username="committee", password="pw")
        html = self.client.get(reverse("committee_hub")).content.decode()
        nav = re.search(r'<nav class="members-nav".*?</nav>', html, re.S).group(0)
        self.assertEqual(nav.count(">Schedule</a>"), 1)
        self.assertRegex(nav, r'href="%s"[^>]*>Events</a>' % reverse("committee_schedule"))


class ValidatorFindingsTests(TestCase):
    """Regressions for bugs the W3C validator found."""

    def test_date_inputs_render_iso_values(self):
        # type="date" inputs only accept YYYY-MM-DD. With en-gb localisation
        # Django rendered 26/11/2026, which browsers show as an empty field.
        create_committee_user(username="committee", password="pw")
        self.client.login(username="committee", password="pw")
        choir_settings = ChoirSettings.load()
        choir_settings.subscription_deadline = datetime(2026, 11, 26).date()
        choir_settings.save()
        html = self.client.get(reverse("committee_settings")).content.decode()
        self.assertIn('value="2026-11-26"', html)
        self.assertNotIn("26/11/2026", html)

    def test_contact_page_ids_are_unique_and_labels_match(self):
        html = self.client.get(reverse("contact")).content.decode()
        ids = re.findall(r'\sid="([^"]+)"', html)
        self.assertEqual([i for i in set(ids) if ids.count(i) > 1], [])
        for target in re.findall(r'<label[^>]*\sfor="([^"]+)"', html):
            self.assertIn(target, ids)


class HelpTextReferenceTests(TestCase):
    """Every aria-describedby on a form page points at an element on that
    page: help texts are shown with the id Django refers to, or cleared."""

    def test_described_by_targets_exist(self):
        committee = create_committee_user(username="committee", password="pw")
        self.client.login(username="committee", password="pw")
        project = Project.objects.create(name="Clent 2026", status="ACTIVE")
        planning = Project.objects.create(name="Easter 2027", status="PLANNING")
        event = Event.objects.create(project=project, event_type="RES", date_time=timezone.now() + timedelta(days=3), location="Hall")
        poll = AvailabilityPoll.objects.create(project=planning, question="Free?")
        payment = SubscriptionPayment.objects.create(
            member=committee.profile, amount="50.00", date_paid=timezone.now().date(), term_reference="Autumn 2026"
        )
        urls = [
            reverse("settings"),
            reverse("contact"),
            reverse("committee_projects"),
            reverse("committee_project_edit", args=[project.id]),
            reverse("committee_polling"),
            reverse("committee_poll_edit", args=[poll.id]),
            reverse("committee_settings"),
            reverse("committee_broadcast"),
            reverse("committee_event_edit", args=[event.id]),
            reverse("committee_documents"),
            reverse("committee_financials_edit", args=[payment.id]),
        ]
        missing = []
        for url in urls:
            html = self.client.get(url).content.decode()
            ids = set(re.findall(r'\sid="([^"]+)"', html))
            for target in re.findall(r'aria-describedby="([^"]+)"', html):
                missing += [f"{url}: {t}" for t in target.split() if t not in ids]
        self.assertEqual(missing, [])

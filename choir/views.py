import json
from datetime import timedelta
from datetime import timezone as py_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from .forms import (
    AuditionForm,
    CommitteeDocumentForm,
    EnquiryForm,
    GiftAidForm,
    ProfileUpdateForm,
    UserUpdateForm,
)
from .models import (
    Attendance,
    AvailabilityPoll,
    AvailabilityResponse,
    CommitteeDocument,
    Event,
    GiftAidDeclaration,
    LearningAsset,
    Project,
    SubscriptionPayment,  # <-- Added for the new financial logic
)

# ==============================================================================
# 1. PUBLIC VIEWS (No login required)
# ==============================================================================


def home_view(request):
    """Renders the public-facing landing page."""
    return render(request, "choir/index.html")


def about_view(request):
    """Renders the public 'About Us' and director biography page."""
    return render(request, "choir/about.html")


def events_view(request):
    """Renders the public concert and events schedule."""
    return render(request, "choir/events.html")


def contact_view(request):
    """
    Traffic controller handling both public contact enquiries and
    audition applications from a unified frontend view.
    """
    if request.method == "POST":
        # Route the POST data to the correct form based on the presence of 'voice_part'
        if "voice_part" in request.POST:
            form = AuditionForm(request.POST)
            is_audition = True
        else:
            form = EnquiryForm(request.POST)
            is_audition = False

        if form.is_valid():
            submission = form.save()

            # Construct the appropriate email payload based on the form type
            if is_audition:
                email_subject = f"New Audition Request: {submission.name} ({submission.get_voice_part_display()})"
                email_body = f"Name: {submission.name}\nEmail: {submission.email}\nVoice Part: {submission.get_voice_part_display()}\n\nExperience:\n{submission.experience}"
            else:
                email_subject = f"Website Enquiry: {submission.get_subject_display()} - {submission.name}"
                email_body = f"Name: {submission.name}\nEmail: {submission.email}\n\nMessage:\n{submission.message}"

            # Dispatch via configured SMTP (Brevo)
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CHOIR_CONTACT_EMAIL],
                fail_silently=False,
            )

            messages.success(
                request, "Thank you! Your details have been securely recorded."
            )
            return redirect("contact")

        else:
            # Re-render with the bound (invalid) form instead of redirecting -
            # a redirect starts a fresh GET, which meant the user lost every
            # field they'd typed and never saw *which* field was wrong, only
            # a generic banner. The other form on the page still gets a
            # clean, empty instance since it wasn't the one submitted.
            messages.error(
                request, "There was an error with your submission. Please check the highlighted fields."
            )
            if is_audition:
                enquiry_form = EnquiryForm()
                audition_form = form
            else:
                enquiry_form = form
                audition_form = AuditionForm()

    else:
        # GET Request: Initialize fresh, empty forms to send to the template
        enquiry_form = EnquiryForm()
        audition_form = AuditionForm()

    context = {
        "enquiry_form": enquiry_form,
        "audition_form": audition_form,
    }
    return render(request, "choir/contact.html", context)


# ==============================================================================
# 2. SECURE MEMBER VIEWS (Requires active authentication)
# ==============================================================================


@login_required
def dashboard_view(request):
    """
    The primary member command center - "Schedule & Logistics" on the
    subnav. Scoped to the current ACTIVE project only; Repertoire &
    Learning lives on its own page now (member_repertoire_view).
    """
    active_project = Project.get_active()

    if active_project is None:
        # No project is currently ACTIVE - a real, reachable state (right
        # after a fresh deploy, or any handoff gap between archiving one
        # project and activating the next), not an edge case to hand-wave.
        context = {"active_project": None, "user_attendances": []}
        return render(request, "choir/members.html", context)

    # --- A. THE AUTO-HEALING MATRIX ---
    # Backfill missing Attendance rows for the active project's events
    # only - not every Event ever, which used to mean a member visiting
    # the dashboard silently created RSVP rows for events belonging to
    # long-archived projects too.
    project_events = Event.objects.filter(project=active_project)

    existing_rsvp_event_ids = Attendance.objects.filter(
        user=request.user, event__in=project_events
    ).values_list("event_id", flat=True)

    missing_events = project_events.exclude(id__in=existing_rsvp_event_ids)

    if missing_events.exists():
        new_attendances = [
            Attendance(user=request.user, event=event, status="PENDING")
            for event in missing_events
        ]
        Attendance.objects.bulk_create(new_attendances)

    # --- B. FETCH DASHBOARD DATA ---
    user_attendances = (
        Attendance.objects.filter(user=request.user, event__project=active_project)
        .select_related("event")
        .order_by("event__date_time")
    )

    # --- C. FINANCIAL TRACKING (Progressive Disclosure) ---
    current_term = settings.CURRENT_TERM

    # Check if a payment record exists for this user for this specific term
    has_paid_current_term = SubscriptionPayment.objects.filter(
        member=request.user.profile, term_reference=current_term
    ).exists()

    context = {
        "active_project": active_project,
        "user_attendances": user_attendances,
        "current_term": current_term,
        "has_paid_current_term": has_paid_current_term,
    }

    return render(request, "choir/members.html", context)


@login_required
def member_repertoire_view(request):
    """"Repertoire & Learning" on the subnav - the active project's music
    library. Voice-part hub links stay unscoped (see hub_view) - a member
    may legitimately want an older term's audio track, and that's a
    separate, deliberately deferred enhancement, not part of this page."""
    active_project = Project.get_active()
    repertoire = (
        active_project.repertoire.all().order_by("title") if active_project else []
    )

    context = {
        "active_project": active_project,
        "current_repertoire": repertoire,
    }
    return render(request, "choir/member_repertoire.html", context)


@login_required
def member_polling_view(request):
    """"Looking Ahead" on the subnav. PLANNING projects are otherwise
    committee-only (see the Project docstring), but their open polls are
    the one deliberate exception - members answer question/proposed_date/
    notes here, never that project's repertoire or description, which
    this view's context never includes."""
    open_polls = list(
        AvailabilityPoll.objects.filter(
            project__status="PLANNING", is_open=True
        ).select_related("project")
    )

    existing_responses = {
        response.poll_id: response.response
        for response in AvailabilityResponse.objects.filter(
            user=request.user, poll__in=open_polls
        )
    }
    # Django templates can't do a dict lookup with a variable key
    # ({{ dict.some_var }} only works for literal keys) - attach each
    # poll's response directly as an attribute instead, so the template
    # can just read {{ poll.user_response }}.
    for poll in open_polls:
        poll.user_response = existing_responses.get(poll.id)

    context = {"open_polls": open_polls}
    return render(request, "choir/member_polling.html", context)


@login_required
@require_POST
def member_poll_respond_view(request, poll_id):
    """API endpoint updating a member's response to one poll, mirroring
    update_rsvp_view's fetch+CSRF-header AJAX pattern rather than a full
    page reload."""
    poll = get_object_or_404(AvailabilityPoll, id=poll_id, is_open=True)

    try:
        data = json.loads(request.body)
        response_value = data.get("response")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid payload"}, status=400)

    valid_choices = [choice[0] for choice in AvailabilityResponse.RESPONSE_CHOICES]
    if response_value not in valid_choices:
        return JsonResponse({"success": False, "error": "Invalid response"}, status=400)

    AvailabilityResponse.objects.update_or_create(
        poll=poll,
        user=request.user,
        defaults={"response": response_value},
    )
    return JsonResponse({"success": True, "response": response_value})


@login_required
def giftaid_view(request):
    """Handles secure submission of a member's Gift Aid declaration."""
    user_profile = request.user.profile

    existing_declaration = GiftAidDeclaration.objects.filter(
        member=user_profile
    ).first()

    if request.method == "POST":
        # GiftAidDeclaration.member is a OneToOneField - the template only
        # ever shows this form when no declaration exists yet, but a stale
        # tab, double-click, or replayed request could still POST here with
        # one already on file. Without this guard, form.save() below builds
        # a brand-new GiftAidDeclaration and hits that uniqueness
        # constraint directly - an uncaught IntegrityError (500 page)
        # instead of a graceful message.
        if existing_declaration:
            messages.info(
                request, "You already have a Gift Aid declaration on file."
            )
            return redirect("giftaid")

        form = GiftAidForm(request.POST)
        if form.is_valid():
            # commit=False builds the object in memory to allow appending the user profile
            declaration = form.save(commit=False)
            declaration.member = user_profile
            declaration.save()
            return redirect("members")
    else:
        form = GiftAidForm()

    context = {
        "form": form,
        "existing_declaration": existing_declaration,
    }
    return render(request, "choir/giftaid.html", context)


@login_required
def hub_view(request, voice_part):
    """Renders the learning hub dynamically based on the requested voice part."""
    part_map = {
        "soprano": "SOP",
        "alto": "ALT",
        "tenor": "TEN",
        "baritone": "BAS",  # Grouping baritones with basses for assets
        "bass": "BAS",
    }

    db_part = part_map.get(voice_part.lower())

    if db_part:
        # select_related optimizes the database hit when fetching foreign keys
        assets = LearningAsset.objects.filter(
            voice_part__in=[db_part, "ALL"]
        ).select_related("repertoire")
    else:
        assets = []

    context = {
        "voice_part_name": voice_part.title(),
        "assets": assets,
    }
    return render(request, "choir/hub.html", context)


@login_required
def settings_view(request):
    """Allows members to update their base User and Profile details simultaneously."""
    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("settings")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
    }
    return render(request, "choir/settings.html", context)


def custom_logout_view(request):
    """Safely logs the user out and redirects to the home page."""
    logout(request)
    messages.info(request, "You have been securely logged out.")
    return redirect("home")


# ==============================================================================
# 3. UTILITY & API VIEWS (Background processes)
# ==============================================================================


@login_required
@require_POST
def update_rsvp_view(request, attendance_id):
    """Asynchronous API endpoint to update RSVP status without page reloads."""
    attendance = get_object_or_404(Attendance, id=attendance_id, user=request.user)

    try:
        data = json.loads(request.body)
        new_status = data.get("status")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid payload"}, status=400)

    valid_choices = [choice[0] for choice in Attendance.STATUS_CHOICES]
    if new_status in valid_choices:
        attendance.status = new_status
        attendance.save()
        return JsonResponse({"success": True, "new_status": new_status})

    return JsonResponse({"success": False, "error": "Invalid status"}, status=400)


@login_required
def download_ics(request, event_id):
    """Generates an iCalendar (.ics) file for one-click calendar syncing."""
    event = get_object_or_404(Event, id=event_id)

    # Format timestamps strictly into UTC strings (YYYYMMDDThhmmssZ)
    start_utc = event.date_time.astimezone(py_timezone.utc)
    start_str = start_utc.strftime("%Y%m%dT%H%M%SZ")

    end_utc = start_utc + timedelta(hours=2)
    end_str = end_utc.strftime("%Y%m%dT%H%M%SZ")

    clean_notes = (
        strip_tags(event.additional_notes)
        if event.additional_notes
        else "Clent Consort Rehearsal/Event"
    )

    # ICS file strings cannot contain arbitrary indentation
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Clent Consort//Members Portal//EN
BEGIN:VEVENT
UID:event-{event.id}@clentconsort.org
DTSTAMP:{start_str}
DTSTART:{start_str}
DTEND:{end_str}
SUMMARY:Clent Consort: {event.get_event_type_display()}
LOCATION:{event.location}
DESCRIPTION:{clean_notes}
END:VEVENT
END:VCALENDAR"""

    response = HttpResponse(ics_content, content_type="text/calendar")
    response["Content-Disposition"] = (
        f'attachment; filename="clent_consort_{start_utc.strftime("%b%d")}.ics"'
    )

    return response


# ==============================================================================
# 4. COMMITTEE / ADMIN VIEWS (Requires Staff Privileges)
# ==============================================================================


def is_committee(user):
    """
    Helper gatekeeper: checks for committee/administrative privileges.

    Single source of truth for "is this user committee staff" - this used
    to also exist as a second, inconsistent predicate (is_committee_staff)
    that a couple of views used instead. Gates the genuinely sensitive
    committee views (financials, emergency roster, broadcast, scheduling,
    RSVP overrides). committee_hub and committee_documents_view are
    deliberately NOT gated by this - see the comment on those views.
    """
    return user.is_active and (user.is_staff or user.is_superuser)


# =============================================================================
# 4.0 COMMITTEE PROJECT MANAGEMENT
# =============================================================================
@login_required
@user_passes_test(is_committee)
def committee_projects_view(request):
    """List existing Projects (most recent first, per Project.Meta.ordering)
    and handle creating a new one. Editing an existing Project - including
    the PLANNING -> ACTIVE -> ARCHIVED status transition - happens on
    committee_project_edit_view, not here."""
    from .forms import ProjectForm

    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            new_project = form.save()
            messages.success(request, f"'{new_project.name}' created.")
            return redirect("committee_projects")
    else:
        form = ProjectForm()

    context = {
        "form": form,
        "projects": Project.objects.all(),
    }
    return render(request, "choir/committee_projects.html", context)


@login_required
@user_passes_test(is_committee)
def committee_project_edit_view(request, project_id):
    """Edit an existing Project's details, status, and repertoire list."""
    from .forms import ProjectForm

    project = get_object_or_404(Project, id=project_id)

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{project.name}' updated.")
            return redirect("committee_projects")
    else:
        form = ProjectForm(instance=project)

    context = {
        "form": form,
        "project": project,
    }
    return render(request, "choir/committee_project_edit.html", context)


@login_required
@user_passes_test(is_committee)
def committee_poll_manage_view(request):
    """Create availability polls (tied to a PLANNING project) and view
    aggregate YES/NO/MAYBE results + a non-responder list per poll -
    mirrors committee_rsvp_report's pending-list-with-mailto pattern."""
    from .forms import AvailabilityPollForm

    if request.method == "POST":
        form = AvailabilityPollForm(request.POST)
        if form.is_valid():
            poll = form.save(commit=False)
            poll.created_by = request.user
            poll.save()
            messages.success(request, "Poll created.")
            return redirect("committee_polling")
    else:
        form = AvailabilityPollForm()

    active_users = User.objects.filter(is_active=True)
    poll_data = []
    for poll in AvailabilityPoll.objects.select_related("project"):
        responses = poll.responses.select_related("user")
        responded_user_ids = responses.values_list("user_id", flat=True)
        non_responders = active_users.exclude(id__in=responded_user_ids)
        non_responder_emails = ",".join(
            [user.email for user in non_responders if user.email]
        )

        poll_data.append(
            {
                "poll": poll,
                "yes_count": responses.filter(response="YES").count(),
                "no_count": responses.filter(response="NO").count(),
                "maybe_count": responses.filter(response="MAYBE").count(),
                "non_responders": non_responders,
                "non_responder_emails": non_responder_emails,
            }
        )

    context = {
        "form": form,
        "poll_data": poll_data,
    }
    return render(request, "choir/committee_polling.html", context)


@login_required
@user_passes_test(is_committee)
def committee_rsvp_report(request):
    """A dual-panel dashboard showing Event RSVPs and Member Attendance Stats."""

    # --- DATASET 1: EVENT-BY-EVENT DATA ---
    # Fetch ALL events, ordered backwards so the latest are at the top
    all_events = Event.objects.all().order_by("-date_time")

    all_attendances = (
        Attendance.objects.filter(event__in=all_events, user__is_active=True)
        .select_related("event", "user")
        .order_by("user__first_name")
    )

    report_data = []
    for event in all_events:
        event_rsvps = all_attendances.filter(event=event)

        attending = event_rsvps.filter(status="ATTENDING")
        absent = event_rsvps.filter(status="ABSENT")
        pending = event_rsvps.filter(status="PENDING")

        pending_emails = ",".join(
            [rsvp.user.email for rsvp in pending if rsvp.user.email]
        )

        report_data.append(
            {
                "event": event,
                "attending": attending,
                "absent": absent,
                "pending": pending,
                "pending_emails": pending_emails,
            }
        )

    # --- DATASET 2: INDIVIDUAL MEMBER STATISTICS ---
    active_users = User.objects.filter(is_active=True).prefetch_related("attendances")
    member_stats = []

    for user in active_users:
        if hasattr(user, "profile"):
            user_rsvps = user.attendances.all()
            total_events = user_rsvps.count()

            # Calculate all-time totals
            total_attending = user_rsvps.filter(status="ATTENDING").count()
            total_absent = user_rsvps.filter(status="ABSENT").count()
            total_pending = user_rsvps.filter(status="PENDING").count()

            # Calculate an "All Time Attendance Rate" (ignoring pending events)
            resolved_events = total_attending + total_absent
            attendance_rate = (
                int((total_attending / resolved_events) * 100)
                if resolved_events > 0
                else 0
            )

            member_stats.append(
                {
                    "user": user,
                    "profile": user.profile,
                    "total": total_events,
                    "attending": total_attending,
                    "absent": total_absent,
                    "pending": total_pending,
                    "rate": attendance_rate,
                }
            )

    # Sort the stats so the lowest attendance rates appear at the top for committee review
    member_stats = sorted(member_stats, key=lambda k: k["rate"])

    context = {
        "report_data": report_data,
        "member_stats": member_stats,
    }

    return render(request, "choir/committee_rsvps.html", context)


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_update_rsvp_override(request, attendance_id):
    """
    API endpoint allowing staff to manually override any member's RSVP status
    for post-rehearsal reconciliation.
    """
    # Notice we removed the user=request.user check here so staff can edit anyone
    attendance = get_object_or_404(Attendance, id=attendance_id)

    try:
        data = json.loads(request.body)
        new_status = data.get("status")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid payload"}, status=400)

    valid_choices = [choice[0] for choice in Attendance.STATUS_CHOICES]
    if new_status in valid_choices:
        attendance.status = new_status
        attendance.save()
        return JsonResponse({"success": True, "new_status": new_status})

    return JsonResponse({"success": False, "error": "Invalid status"}, status=400)


# =============================================================================
# 4.2 COMMITTEE DOCUMENTS
# =============================================================================
@login_required
# Intentionally open to any active member, not just committee/staff: the
# committee asked for the hub and the document vault (read access) to be
# available to all choir members, not staff-only. Do not add
# @user_passes_test(is_committee) back here - that was tried and reverted.
def committee_hub(request):
    """The central command center dashboard, now acting as a shared workspace."""
    return render(request, "choir/committee_hub.html")


@login_required
# Intentionally open to any active member for read access - see the comment
# on committee_hub above. Uploading (POST) is still staff-only, enforced
# in-body below.
def committee_documents_view(request):
    """Unified vault to view secure documents. Uploading restricted to staff."""
    if request.method == "POST":
        # HARD STOP: If they aren't staff, block the upload attempt
        if not request.user.is_staff:
            messages.error(request, "Only committee members have upload permissions.")
            return redirect("committee_documents")

        form = CommitteeDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.uploaded_by = request.user
            document.save()
            messages.success(request, f"'{document.title}' uploaded successfully.")
            return redirect("committee_documents")
    else:
        form = CommitteeDocumentForm()

    documents = CommitteeDocument.objects.all()

    context = {
        "form": form,
        "documents": documents,
    }
    return render(request, "choir/committee_documents.html", context)


@login_required
@user_passes_test(is_committee)
def committee_emergency_roster(request):
    """
    A highly restricted view displaying medical, emergency, and safeguarding
    information for active choir members only.
    """
    # The database now exclusively fetches active users who actually have a profile mapped to them
    roster = (
        User.objects.filter(
            is_active=True,
            profile__isnull=False,  # <-- THIS IS THE FIX
        )
        .select_related("profile")
        .order_by("first_name")
    )

    return render(request, "choir/committee_emergency.html", {"roster": roster})


# =============================================================================
# 4.2 COMMITTEE FINANCIALS
# =============================================================================
@login_required
@user_passes_test(is_committee)
def committee_financials_view(request):
    """Unified ledger to track and log termly subscriptions."""
    from .forms import SubscriptionPaymentForm
    from .models import MemberProfile

    current_term = settings.CURRENT_TERM

    # --- 1. HANDLE INCOMING PAYMENTS (POST) ---
    if request.method == "POST":
        member_id = request.POST.get("member_id")
        profile = get_object_or_404(MemberProfile, id=member_id)

        # date_paid/term_reference are stamped server-side rather than left
        # editable in the quick-log row - matches the old behaviour, but now
        # goes through the ModelForm so amount is actually validated instead
        # of being handed straight to the DB (a non-numeric amount used to
        # 500 the whole view).
        post_data = request.POST.copy()
        post_data.setdefault("date_paid", timezone.now().date().isoformat())
        post_data.setdefault("term_reference", current_term)
        form = SubscriptionPaymentForm(post_data)

        if form.is_valid():
            payment = form.save(commit=False)
            payment.member = profile
            payment.save()
            messages.success(
                request,
                f"Payment successfully logged for {profile.user.get_full_name()}.",
            )
        else:
            messages.error(
                request,
                f"Could not log payment for {profile.user.get_full_name()}: "
                f"{form.errors.as_text()}",
            )
        return redirect("committee_financials")

    # --- 2. BUILD THE ROSTER DISPLAY (GET) ---
    # Fetch all active singers and pre-fetch their profiles to save database hits
    active_users = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name")
    )

    # Build a clean data structure for the template
    roster = []
    for user in active_users:
        # 1. ONLY include users that actually have a profile (Fixes the empty rows)
        if hasattr(user, "profile"):
            # 2. Check for exemption
            is_exempt = user.profile.is_exempt_from_subs

            payment = SubscriptionPayment.objects.filter(
                member=user.profile, term_reference=current_term
            ).first()

            has_gift_aid = GiftAidDeclaration.objects.filter(
                member=user.profile
            ).exists()

            roster.append(
                {
                    "user": user,
                    "profile": user.profile,
                    "payment": payment,
                    "has_gift_aid": has_gift_aid,
                    "is_exempt": is_exempt,  # Pass this to the template
                }
            )

    context = {
        "roster": roster,
        "current_term": current_term,
    }
    return render(request, "choir/committee_financials.html", context)


@login_required
@user_passes_test(is_committee)
def committee_financials_edit_view(request, payment_id):
    """Lets the committee correct a logged payment - amount, date, term,
    method, or notes - after the fact, e.g. a mis-keyed amount or a cash
    payment later reconciled to a specific date."""
    from .forms import SubscriptionPaymentForm

    payment = get_object_or_404(SubscriptionPayment, id=payment_id)

    if request.method == "POST":
        form = SubscriptionPaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Payment for {payment.member.user.get_full_name()} updated.",
            )
            return redirect("committee_financials")
    else:
        form = SubscriptionPaymentForm(instance=payment)

    return render(
        request,
        "choir/committee_financials_edit.html",
        {"form": form, "payment": payment},
    )


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_financials_delete_view(request, payment_id):
    """Removes a mistakenly logged payment (e.g. duplicate entry)."""
    payment = get_object_or_404(SubscriptionPayment, id=payment_id)
    member_name = payment.member.user.get_full_name()
    payment.delete()
    messages.success(request, f"Payment for {member_name} deleted.")
    return redirect("committee_financials")


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_toggle_exempt_view(request, profile_id):
    """Manually flips a member's exempt-from-subs status - e.g. scholars,
    bursaries, or staff who don't appear in the financial ledger."""
    from .models import MemberProfile

    profile = get_object_or_404(MemberProfile, id=profile_id)
    profile.is_exempt_from_subs = not profile.is_exempt_from_subs
    profile.save()

    status = "exempted from" if profile.is_exempt_from_subs else "re-added to"
    messages.success(request, f"{profile.user.get_full_name()} {status} the subs ledger.")
    return redirect("committee_financials")


# ==============================================================================
# 4.1 COMMITTEE EVENT SCHEDULING
# =============================================================================


@login_required
@user_passes_test(is_committee)
def committee_schedule_event(request):
    """Processes frontend form submissions to schedule new rehearsals or residencies."""
    from .forms import QuickEventScheduleForm  # Local import to prevent circular traps

    if request.method == "POST":
        form = QuickEventScheduleForm(request.POST)
        if form.is_valid():
            new_event = form.save()
            messages.success(
                request,
                f"Successfully scheduled {new_event.get_event_type_display()} for {new_event.date_time.strftime('%A, %d %B')}.",
            )
            return redirect("committee_hub")
    else:
        form = QuickEventScheduleForm()

    context = {
        "form": form,
    }
    return render(request, "choir/committee_schedule.html", context)


@login_required
def login_redirect_router(request):
    """
    Traffic controller that routes users to the correct dashboard
    immediately upon successful authentication.
    """
    return redirect("members")


# ==============================================================================
# 4.3 COMMITTEE BROADCASTS
# =============================================================================


@login_required
@user_passes_test(is_committee)
def committee_broadcast(request):
    """Processes frontend mass-email dispatch."""
    from .forms import BroadcastForm

    if request.method == "POST":
        form = BroadcastForm(request.POST)
        if form.is_valid():
            broadcast = form.save(commit=False)
            broadcast.author = request.user
            broadcast.save()
            messages.success(request, "Communication broadcasted to the ensemble.")
            return redirect("committee_hub")
    else:
        form = BroadcastForm()

    return render(request, "choir/committee_broadcast.html", {"form": form})


# ==============================================================================
# 5. SYSTEM ERROR HANDLERS
# ==============================================================================


def custom_404(request, exception):
    """Overrides the default 404 page with a branded template."""
    return render(request, "404.html", status=404)

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
    The primary member command center.
    """
    # --- A. THE AUTO-HEALING MATRIX ---
    # Fetch ALL events, past and future, to ensure late-joiners get complete records
    all_events = Event.objects.all()

    existing_rsvp_event_ids = Attendance.objects.filter(
        user=request.user, event__in=all_events
    ).values_list("event_id", flat=True)

    missing_events = all_events.exclude(id__in=existing_rsvp_event_ids)

    if missing_events.exists():
        new_attendances = [
            Attendance(user=request.user, event=event, status="PENDING")
            for event in missing_events
        ]
        Attendance.objects.bulk_create(new_attendances)

    # --- B. FETCH DASHBOARD DATA ---
    # Remove the time filter and fetch everything chronologically
    user_attendances = (
        Attendance.objects.filter(user=request.user)
        .select_related("event")
        .order_by("event__date_time")
    )

    # Repertoire is attached at the Project level now, not per-event - see
    # Project.repertoire. Full active-project scoping of this view (auto-
    # heal, empty state, subnav) lands in a later phase; this is the
    # minimal fix so the view doesn't break now that Event.pieces is gone.
    active_project = Project.get_active()
    current_repertoire = (
        active_project.repertoire.all().order_by("title")
        if active_project
        else []
    )

    # --- C. FINANCIAL TRACKING (Progressive Disclosure) ---
    current_term = settings.CURRENT_TERM

    # Check if a payment record exists for this user for this specific term
    has_paid_current_term = SubscriptionPayment.objects.filter(
        member=request.user.profile, term_reference=current_term
    ).exists()

    context = {
        "user_attendances": user_attendances,
        "current_repertoire": current_repertoire,
        "current_term": current_term,
        "has_paid_current_term": has_paid_current_term,
    }

    return render(request, "choir/members.html", context)


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

    current_term = settings.CURRENT_TERM

    # --- 1. HANDLE INCOMING PAYMENTS (POST) ---
    if request.method == "POST":
        member_id = request.POST.get("member_id")
        amount = request.POST.get("amount")
        method = request.POST.get("method", "BACS")
        notes = request.POST.get("notes", "")

        # Fetch the specific member's profile
        from .models import MemberProfile

        profile = get_object_or_404(MemberProfile, id=member_id)

        # Log the payment into the database
        SubscriptionPayment.objects.create(
            member=profile,
            amount=amount,
            date_paid=timezone.now().date(),
            term_reference=current_term,
            payment_method=method,
            notes=notes,
        )

        messages.success(
            request, f"Payment successfully logged for {profile.user.get_full_name()}."
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

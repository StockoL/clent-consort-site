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
from django.urls import reverse
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
            print("🛑 FORM FAILED VALIDATION! Errors:", form.errors)
            messages.error(
                request, "There was an error with your submission. Please try again."
            )
            return redirect(reverse("contact") + "#form-section")

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
    Handles the auto-healing RSVP matrix, repertoire loading, and subscription status.
    """
    # --- A. THE AUTO-HEALING MATRIX ---
    # Fetch all events happening from right now into the future
    upcoming_events = Event.objects.filter(date_time__gte=timezone.now())

    # Flatten the IDs of events this user ALREADY has an RSVP row for
    existing_rsvp_event_ids = Attendance.objects.filter(
        user=request.user, event__in=upcoming_events
    ).values_list("event_id", flat=True)

    # Isolate the events that are completely missing from their profile
    missing_events = upcoming_events.exclude(id__in=existing_rsvp_event_ids)

    # Bulk-create 'PENDING' rows instantly for any missing events
    if missing_events.exists():
        new_attendances = [
            Attendance(user=request.user, event=event, status="PENDING")
            for event in missing_events
        ]
        Attendance.objects.bulk_create(new_attendances)

    # --- B. FETCH DASHBOARD DATA ---
    user_attendances = (
        Attendance.objects.filter(
            user=request.user, event__date_time__gte=timezone.now()
        )
        .select_related("event")
        .prefetch_related("event__pieces")
        .order_by("event__date_time")[:5]
    )

    # Extract unique repertoire across all upcoming events
    repertoire_set = set()
    for attendance in user_attendances:
        for piece in attendance.event.pieces.all():
            repertoire_set.add(piece)

    current_repertoire = sorted(list(repertoire_set), key=lambda x: x.title)

    # --- C. FINANCIAL TRACKING (Progressive Disclosure) ---
    current_term = "Autumn 2026"  # Update this string at the start of each new term

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
        form = GiftAidForm(request.POST)
        if form.is_valid():
            # commit=False builds the object in memory to allow appending the user profile
            declaration = form.save(commit=False)
            declaration.member = user_profile
            declaration.save()
            return redirect("dashboard")
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
    """Helper gatekeeper: Checks for administrative privileges."""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_committee)
def committee_hub(request):
    """The central command center dashboard for choir administration."""
    return render(request, "choir/committee_hub.html")


@login_required
@user_passes_test(is_committee)
def committee_rsvp_report(request):
    """A high-level dashboard showing complete attendance data for all upcoming events."""

    today = timezone.now()

    # 1. Fetch all upcoming events, ordered chronologically
    upcoming_events = Event.objects.filter(date_time__gte=today).order_by("date_time")

    # 2. Fetch all attendances for these events in one fast query
    all_attendances = (
        Attendance.objects.filter(event__in=upcoming_events, user__is_active=True)
        .select_related("event", "user")
        .order_by("user__first_name")
    )

    # 3. Process the data into a clean list for the template
    report_data = []
    for event in upcoming_events:
        event_rsvps = all_attendances.filter(event=event)

        # Group by status (Ensure these strings match your Attendance.STATUS_CHOICES exactly!)
        attending = event_rsvps.filter(status="ATTENDING")
        declined = event_rsvps.filter(status="ABSENT")
        pending = event_rsvps.filter(status="PENDING")

        # Create a comma-separated list of emails for the "BCC" mailto link
        pending_emails = ",".join(
            [rsvp.user.email for rsvp in pending if rsvp.user.email]
        )

        report_data.append(
            {
                "event": event,
                "attending": attending,
                "declined": declined,
                "pending": pending,
                "pending_emails": pending_emails,
            }
        )

    context = {
        "report_data": report_data,
    }

    return render(request, "choir/committee_rsvps.html", context)


@login_required
@user_passes_test(is_committee)
def committee_documents_view(request):
    """Unified vault to upload and view secure committee documents."""
    if request.method == "POST":
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
def committee_financials_view(request):
    """Unified ledger to track and log termly subscriptions."""

    current_term = "Autumn 2026"  # Must match the string in dashboard_view!

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
# 5. SYSTEM ERROR HANDLERS
# ==============================================================================


def custom_404(request, exception):
    """Overrides the default 404 page with a branded template."""
    return render(request, "404.html", status=404)

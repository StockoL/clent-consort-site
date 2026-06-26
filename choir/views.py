import json  # <-- Added here
from datetime import timedelta
from datetime import timezone as py_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import (  # Imports the security lock
    login_required,
    user_passes_test,
)
from django.core.mail import send_mail
from django.http import (
    HttpResponse,
    JsonResponse,  # <-- Added here
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from .forms import (
    AuditionForm,
    EnquiryForm,
    GiftAidForm,
    ProfileUpdateForm,
    UserUpdateForm,
)
from .models import Attendance, Event, GiftAidDeclaration, LearningAsset

# ==============================================================================
# PUBLIC VIEWS
# ==============================================================================


def home_view(request):
    return render(request, "choir/index.html")


def about_view(request):
    return render(request, "choir/about.html")


def events_view(request):
    return render(request, "choir/events.html")


def contact_view(request):
    """
    Traffic controller handling both public contact enquiries and
    audition applications from a unified frontend view.
    """
    if request.method == "POST":
        if "voice_part" in request.POST:
            form = AuditionForm(request.POST)
            is_audition = True
        else:
            form = EnquiryForm(request.POST)
            is_audition = False

        if form.is_valid():
            submission = form.save()

            if is_audition:
                email_subject = f"New Audition Request: {submission.name} ({submission.get_voice_part_display()})"
                email_body = f"Name: {submission.name}\nEmail: {submission.email}\nVoice Part: {submission.get_voice_part_display()}\n\nExperience:\n{submission.experience}"
            else:
                email_subject = f"Website Enquiry: {submission.get_subject_display()} - {submission.name}"
                email_body = f"Name: {submission.name}\nEmail: {submission.email}\n\nMessage:\n{submission.message}"

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
# SECURE MEMBER VIEWS
# ==============================================================================


@login_required
def dashboard_view(request):
    """
    Renders the dashboard with the upcoming schedule (via Attendance RSVPs)
    and the active repertoire list, featuring an auto-healing matrix.
    """
    # ==========================================================================
    # 1. THE AUTO-HEALING MATRIX
    # ==========================================================================
    # Get all events happening from right now into the future
    upcoming_events = Event.objects.filter(date_time__gte=timezone.now())

    # Get a flat list of the IDs for events this user ALREADY has an RSVP row for
    existing_rsvp_event_ids = Attendance.objects.filter(
        user=request.user, event__in=upcoming_events
    ).values_list("event_id", flat=True)

    # Find the gap: isolate the events that are missing from their profile
    missing_events = upcoming_events.exclude(id__in=existing_rsvp_event_ids)

    # If there are missing events, create the 'PENDING' rows instantly
    if missing_events.exists():
        new_attendances = [
            Attendance(user=request.user, event=event, status="PENDING")
            for event in missing_events
        ]
        # bulk_create writes them all to the database in a single, lightning-fast SQL query
        Attendance.objects.bulk_create(new_attendances)

    # ==========================================================================
    # 2. FETCH THE DASHBOARD DATA (Business as usual)
    # ==========================================================================
    user_attendances = (
        Attendance.objects.filter(
            user=request.user, event__date_time__gte=timezone.now()
        )
        .select_related("event")
        .prefetch_related("event__pieces")
        .order_by("event__date_time")[:5]
    )

    repertoire_set = set()
    for attendance in user_attendances:
        for piece in attendance.event.pieces.all():
            repertoire_set.add(piece)

    current_repertoire = sorted(list(repertoire_set), key=lambda x: x.title)

    context = {
        "user_attendances": user_attendances,
        "current_repertoire": current_repertoire,
    }

    return render(request, "choir/members.html", context)


@login_required  # Protects the view; redirects to login page if logged out
def giftaid_view(request):
    """
    Handles secure submission of a member's Gift Aid declaration.
    """
    user_profile = request.user.profile  # Fetches the loggged-in user's profile

    # Check if this member has already signed a declaration
    existing_declaration = GiftAidDeclaration.objects.filter(
        member=user_profile
    ).first()

    if request.method == "POST":
        # Feed the incoming POST data into the form
        form = GiftAidForm(request.POST)

        if form.is_valid():
            # Crucial Pattern: commit=False builds the database object in memory
            # without writing it to the actual SQL disk yet.
            declaration = form.save(commit=False)

            # Programmatically attach the logged-in member's profile
            declaration.member = user_profile

            # Now commit it safely to the database!
            declaration.save()

            # Send them back to the members area with a clean success state
            return redirect("dashboard")
    else:
        # If it's a GET request, pass a completely blank form to the template
        form = GiftAidForm()

    context = {
        "form": form,
        "existing_declaration": existing_declaration,
    }
    return render(request, "choir/giftaid.html", context)


@login_required
def hub_view(request, voice_part):
    """
    Renders the learning hub dynamically based on the requested voice part.
    """
    # Translate the URL parameter (e.g., 'tenor') to match our Database codes ('TEN')
    part_map = {
        "soprano": "SOP",
        "alto": "ALT",
        "tenor": "TEN",
        "baritone": "BAS",  # Grouping baritones with basses for assets
        "bass": "BAS",
    }

    # Grab the correct database code, default to None if someone types a weird URL
    db_part = part_map.get(voice_part.lower())

    if db_part:
        # Fetch all assets matching this specific part OR 'ALL' (like a full PDF score)
        # We use 'select_related' as a performance boost to grab the Repertoire title at the same time
        assets = LearningAsset.objects.filter(
            voice_part__in=[db_part, "ALL"]
        ).select_related("repertoire")
    else:
        assets = []  # Failsafe for an invalid URL

    context = {
        "voice_part_name": voice_part.title(),  # Sends "Tenor" to the template for the header
        "assets": assets,
    }

    return render(request, "choir/hub.html", context)


def custom_logout_view(request):
    """Safely logs the user out and redirects to the home page."""
    logout(request)
    messages.info(request, "You have been securely logged out.")
    return redirect("home")


@login_required
def settings_view(request):
    """Allows members to update their personal details."""
    if request.method == "POST":
        # We pass the POST data AND the specific user instance to update
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)

        # If BOTH forms pass validation, save them both to the database
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect(
                "settings"
            )  # Reload the page to show the green success message

    else:
        # GET request: Load the forms pre-filled with the user's current data
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
    }
    return render(request, "choir/settings.html", context)


@login_required
@require_POST  # Security: Forbids people from typing the URL directly to change RSVPs
def update_rsvp_view(request, attendance_id):
    """Catches the silent JS fetch request and updates the database without a page reload."""

    # Securely fetch the record, ensuring it actually belongs to the logged-in user
    attendance = get_object_or_404(Attendance, id=attendance_id, user=request.user)

    # 1. Parse the JSON packet sent by our JavaScript in the template
    try:
        data = json.loads(request.body)
        new_status = data.get("status")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid payload"}, status=400)

    # 2. Validate the data against our allowed choices
    valid_choices = [choice[0] for choice in Attendance.STATUS_CHOICES]
    if new_status in valid_choices:
        attendance.status = new_status
        attendance.save()

        # 3. Return a silent success signal instead of a page redirect
        return JsonResponse({"success": True, "new_status": new_status})

    return JsonResponse({"success": False, "error": "Invalid status"}, status=400)


@login_required
def download_ics(request, event_id):
    """Generates an iCalendar (.ics) file for a specific event."""

    # 1. Securely fetch the requested event
    event = get_object_or_404(Event, id=event_id)

    # 2. Format timestamps into strict UTC strings (YYYYMMDDThhmmssZ)
    start_utc = event.date_time.astimezone(py_timezone.utc)
    start_str = start_utc.strftime("%Y%m%dT%H%M%SZ")

    # We assume a 2-hour default duration since there is no end_time field
    end_utc = start_utc + timedelta(hours=2)
    end_str = end_utc.strftime("%Y%m%dT%H%M%SZ")

    # Clean the HTML from TinyMCE so the calendar description looks neat
    clean_notes = (
        strip_tags(event.additional_notes)
        if event.additional_notes
        else "Clent Consort Rehearsal/Event"
    )

    # 3. Build the raw iCalendar text string
    # The lack of indentation here is intentional! ICS files hate leading spaces.
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

    # 4. Package it into a custom HTTP Response
    # This tells the browser "This is a calendar file, please download it"
    response = HttpResponse(ics_content, content_type="text/calendar")
    response["Content-Disposition"] = (
        f'attachment; filename="clent_consort_{start_utc.strftime("%b%d")}.ics"'
    )

    return response


# --- 1. The Security Test ---
def is_committee(user):
    """Checks if the user has been granted 'Staff' status in the admin panel."""
    return user.is_staff or user.is_superuser


# --- 2. The View ---
@login_required
@user_passes_test(is_committee)  # Bounces anyone who isn't on the committee
def committee_rsvp_report(request):
    """A high-level dashboard showing missing RSVPs for the next 30 days."""

    today = timezone.now()
    window_end = today + timedelta(days=30)

    # The Query: Find pending RSVPs for active members within the next 30 days
    # We use select_related to grab the user and event data in a single, fast SQL hit
    pending_rsvps = (
        Attendance.objects.filter(
            event__date_time__range=(today, window_end),
            status="PENDING",
            user__is_active=True,
        )
        .select_related("event", "user")
        .order_by("event__date_time", "user__first_name")
    )

    context = {
        "pending_rsvps": pending_rsvps,
    }

    return render(request, "choir/committee_rsvps.html", context)


# ==============================================================================
# SYSTEM ERROR HANDLERS
# ==============================================================================


def custom_404(request, exception):
    return render(request, "404.html", status=404)

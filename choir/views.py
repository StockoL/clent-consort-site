import json
from datetime import timedelta
from urllib.parse import urlencode
from datetime import timezone as py_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from .forms import (
    AuditionForm,
    CommitteeDocumentForm,
    EnquiryForm,
    ProfileUpdateForm,
    UserUpdateForm,
)
from .models import (
    Attendance,
    AuditionApplication,
    AvailabilityPoll,
    AvailabilityResponse,
    ChoirSettings,
    CommitteeDocument,
    Enquiry,
    Event,
    LearningAsset,
    Project,
    Repertoire,
    SubscriptionPayment,  # <-- Added for the new financial logic
)
from .permissions import is_committee, is_singer

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
    subnav. Scoped to every currently-ACTIVE project (shown as tabs when
    there's more than one - a deliberate handoff overlap between projects
    is a real, supported state, not an edge case); Repertoire & Learning
    lives on its own page now (member_repertoire_view).
    """
    active_projects = list(Project.get_active_projects())

    current_term = ChoirSettings.load().current_term
    # Non-singers aren't in the ledger, so they're never asked to pay.
    has_paid_current_term = not is_singer(request.user) or SubscriptionPayment.objects.filter(
        member=request.user.profile, term_reference=current_term
    ).exists()

    if not active_projects:
        # No project is currently ACTIVE - a real, reachable state (right
        # after a fresh deploy, or any handoff gap between archiving one
        # project and activating the next), not an edge case to hand-wave.
        context = {
            "active_project": None,
            "active_projects": [],
            "projects_data": [],
            "user_attendances": [],
            "current_term": current_term,
            "has_paid_current_term": has_paid_current_term,
        }
        return render(request, "choir/members.html", context)

    # --- A. THE AUTO-HEALING MATRIX ---
    # Backfill missing Attendance rows for the active projects' events
    # only - not every Event ever, which used to mean a member visiting
    # the dashboard silently created RSVP rows for events belonging to
    # long-archived projects too.
    project_events = Event.objects.filter(project__in=active_projects)

    existing_rsvp_event_ids = Attendance.objects.filter(
        user=request.user, event__in=project_events
    ).values_list("event_id", flat=True)

    missing_events = project_events.exclude(id__in=existing_rsvp_event_ids)

    # Non-singers get no RSVPs (Build Order Phase 5), so don't backfill any.
    if is_singer(request.user) and missing_events.exists():
        new_attendances = [
            Attendance(user=request.user, event=event, status="PENDING")
            for event in missing_events
        ]
        Attendance.objects.bulk_create(new_attendances)

    # --- B. FETCH DASHBOARD DATA ---
    # One bulk query across every active project, then grouped in Python
    # per-project below - cheaper than a separate query per tab.
    all_attendances = (
        Attendance.objects.filter(user=request.user, event__project__in=active_projects)
        .select_related("event", "event__project")
        .order_by("event__date_time")
    )

    # Upcoming events keep their RSVP select; past ones move to a collapsed
    # "Earlier this project" list, most recent first.
    now = timezone.now()
    projects_data = []
    for project in active_projects:
        attendances = [a for a in all_attendances if a.event.project_id == project.id]
        projects_data.append(
            {
                "project": project,
                "user_attendances": [a for a in attendances if a.event.date_time >= now],
                "past_attendances": [
                    a for a in reversed(attendances) if a.event.date_time < now
                ],
            }
        )

    context = {
        # Backward-compat aliases: the first (soonest) active project's data,
        # for anything still reading the old single-project context shape.
        "active_project": active_projects[0],
        "user_attendances": projects_data[0]["user_attendances"],
        "active_projects": active_projects,
        "projects_data": projects_data,
        "current_term": current_term,
        "has_paid_current_term": has_paid_current_term,
    }

    return render(request, "choir/members.html", context)


@login_required
def member_repertoire_view(request):
    """"Repertoire & Learning" on the subnav - shown as one tab per
    currently-ACTIVE project. Each project's voice-part hub links (see
    hub_view) are scoped to that project's own repertoire."""
    active_projects = list(Project.get_active_projects())
    projects_data = [
        {"project": project, "repertoire": project.repertoire.all().order_by("title")}
        for project in active_projects
    ]

    context = {
        # Backward-compat aliases: the first (soonest) active project's data.
        "active_project": active_projects[0] if active_projects else None,
        "current_repertoire": projects_data[0]["repertoire"] if projects_data else [],
        "active_projects": active_projects,
        "projects_data": projects_data,
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
        response.poll_id: response
        for response in AvailabilityResponse.objects.filter(
            user=request.user, poll__in=open_polls
        )
    }
    # Django templates can't do a dict lookup with a variable key
    # ({{ dict.some_var }} only works for literal keys) - attach each
    # poll's response directly as an attribute instead, so the template
    # can just read {{ poll.user_response }}.
    for poll in open_polls:
        existing = existing_responses.get(poll.id)
        poll.user_response = existing.response if existing else None
        poll.user_notes = existing.notes if existing else ""

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
        notes = data.get("notes")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"success": False, "error": "Invalid payload"}, status=400)

    valid_choices = [choice[0] for choice in AvailabilityResponse.RESPONSE_CHOICES]
    if response_value not in valid_choices:
        return JsonResponse({"success": False, "error": "Invalid response"}, status=400)

    defaults = {"response": response_value}
    # Notes are optional in the payload; when present they replace the old
    # ones (an empty string clears them).
    if notes is not None:
        if not isinstance(notes, str):
            return JsonResponse({"success": False, "error": "Invalid notes"}, status=400)
        max_length = AvailabilityResponse._meta.get_field("notes").max_length
        defaults["notes"] = notes.strip()[:max_length]

    AvailabilityResponse.objects.update_or_create(
        poll=poll,
        user=request.user,
        defaults=defaults,
    )
    return JsonResponse({"success": True, "response": response_value})


HUB_PARTS = {
    "soprano": "SOP",
    "alto": "ALT",
    "tenor": "TEN",
    "baritone": "BAS",  # Grouping baritones with basses for assets
    "bass": "BAS",
}

# Uploaded files the practice player can play (Build Order Phase 7).
PLAYER_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav")


def _hub_assets(project, voice_part):
    """One project's assets for one voice part (plus full-choir ones)."""
    db_part = HUB_PARTS.get(voice_part.lower())
    if not db_part:
        return LearningAsset.objects.none()
    # select_related optimizes the database hit when fetching foreign keys
    return LearningAsset.objects.filter(
        voice_part__in=[db_part, "ALL"], repertoire__in=project.repertoire.all()
    ).select_related("repertoire")


def _player_tracks(assets):
    """The practice player's track list: uploaded audio only (PDFs and
    external links keep their own buttons on the hub). URLs are presigned
    and expire (AWS_QUERYSTRING_EXPIRE), which is why hub_tracks_view
    exists to hand the player fresh ones."""
    return [
        {
            "id": asset.id,
            "name": asset.asset_name,
            "piece": asset.repertoire.title,
            "composer": asset.repertoire.composer,
            "url": asset.file_upload.url,
        }
        for asset in assets
        if asset.file_upload and asset.file_upload.name.lower().endswith(PLAYER_AUDIO_EXTENSIONS)
    ]


@login_required
def hub_view(request, voice_part, project_id):
    """Renders the learning hub dynamically based on the requested voice
    part, scoped to one project's repertoire - a member picking a voice
    part from Project A's tab shouldn't see Project B's assets mixed in.
    Audio tracks open in the practice player (js/practice-player.js),
    whose track list is embedded in the page as JSON."""
    project = get_object_or_404(Project, id=project_id, status="ACTIVE")
    assets = _hub_assets(project, voice_part)

    context = {
        "voice_part_name": voice_part.title(),
        "assets": assets,
        "project": project,
        "player_data": {
            "tracks": _player_tracks(assets),
            "refreshUrl": reverse("hub_tracks", args=[voice_part, project.id]),
            "storageKey": f"{project.id}:{voice_part.lower()}",
        },
    }
    return render(request, "choir/hub.html", context)


@login_required
def hub_tracks_view(request, voice_part, project_id):
    """The practice player's track list as JSON, with freshly presigned
    URLs - the player calls this when a track's URL has expired."""
    project = get_object_or_404(Project, id=project_id, status="ACTIVE")
    return JsonResponse({"tracks": _player_tracks(_hub_assets(project, voice_part))})


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


# =============================================================================
# 4.0b COMMITTEE REPERTOIRE LIBRARY
# =============================================================================
@login_required
@user_passes_test(is_committee)
def committee_repertoire_view(request):
    """Every piece in the library (searchable by ?q= on composer or title),
    with its asset count per voice part and the projects using it, plus a
    form to add a piece. Adding from a project's edit page passes
    ?project=<id>: the new piece joins that project and the committee goes
    straight to the piece's upload page."""
    from .forms import RepertoireForm

    project = None
    project_id = request.POST.get("project") or request.GET.get("project")
    if project_id and str(project_id).isdigit():
        project = Project.objects.filter(id=project_id).first()

    if request.method == "POST":
        form = RepertoireForm(request.POST)
        if form.is_valid():
            piece = form.save()
            if project:
                project.repertoire.add(piece)
                messages.success(request, f"'{piece.title}' added to {project.name}. Now upload its scores and tracks.")
            else:
                messages.success(request, f"'{piece.title}' added. Now upload its scores and tracks.")
            return redirect("committee_repertoire_detail", piece_id=piece.id)
    else:
        form = RepertoireForm()

    query = request.GET.get("q", "").strip()
    pieces = Repertoire.objects.prefetch_related("assets", "projects").order_by("composer", "title")
    if query:
        pieces = pieces.filter(Q(composer__icontains=query) | Q(title__icontains=query))

    rows = []
    for piece in pieces:
        counts = {code: 0 for code, _ in LearningAsset.PART_CHOICES}
        for asset in piece.assets.all():
            counts[asset.voice_part] = counts.get(asset.voice_part, 0) + 1
        rows.append(
            {
                "piece": piece,
                # (label, count) per voice part that has any assets
                "counts": [
                    (label, counts[code])
                    for code, label in LearningAsset.PART_CHOICES
                    if counts[code]
                ],
                "projects": list(piece.projects.all()),
            }
        )

    context = {
        "form": form,
        "rows": rows,
        "query": query,
        "project": project,
    }
    return render(request, "choir/committee_repertoire.html", context)


@login_required
@user_passes_test(is_committee)
def committee_repertoire_detail_view(request, piece_id):
    """One piece: rename it, see its assets by voice part, delete any, and
    upload more (several files at once, or one external link)."""
    from .forms import AssetUploadForm, RepertoireForm

    piece = get_object_or_404(Repertoire, id=piece_id)
    piece_form = RepertoireForm(instance=piece)
    upload_form = AssetUploadForm()

    if request.method == "POST":
        if "upload" in request.POST:
            upload_form = AssetUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                added = upload_form.save(piece)
                messages.success(
                    request, f"{len(added)} asset{'s' if len(added) != 1 else ''} added to '{piece.title}'."
                )
                return redirect("committee_repertoire_detail", piece_id=piece.id)
        else:
            piece_form = RepertoireForm(request.POST, instance=piece)
            if piece_form.is_valid():
                piece_form.save()
                messages.success(request, "Piece details saved.")
                return redirect("committee_repertoire_detail", piece_id=piece.id)

    assets = piece.assets.order_by("voice_part", "asset_name")
    context = {
        "piece": piece,
        "piece_form": piece_form,
        "upload_form": upload_form,
        "assets": assets,
        "projects": piece.projects.all(),
    }
    return render(request, "choir/committee_repertoire_detail.html", context)


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_asset_delete_view(request, asset_id):
    """Deletes a learning asset and its stored file (from S3 in production),
    so a removed score doesn't linger in the bucket."""
    asset = get_object_or_404(LearningAsset, id=asset_id)
    piece_id = asset.repertoire_id
    name = asset.asset_name

    if asset.file_upload:
        asset.file_upload.delete(save=False)
    asset.delete()

    messages.success(request, f"'{name}' deleted.")
    return redirect("committee_repertoire_detail", piece_id=piece_id)


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

    active_users = User.objects.filter(is_active=True, profile__is_singer=True)
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
                "noted_responses": [r for r in responses if r.notes],
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
def committee_poll_edit_view(request, poll_id):
    """Edit a poll's question, date, notes or open state."""
    from .forms import AvailabilityPollForm

    poll = get_object_or_404(AvailabilityPoll, id=poll_id)

    if request.method == "POST":
        form = AvailabilityPollForm(request.POST, instance=poll)
        if form.is_valid():
            form.save()
            messages.success(request, "Poll updated.")
            return redirect("committee_polling")
    else:
        form = AvailabilityPollForm(instance=poll)

    return render(
        request, "choir/committee_poll_edit.html", {"form": form, "poll": poll}
    )


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_poll_toggle_view(request, poll_id):
    """Closes an open poll or reopens a closed one. A closed poll drops off
    members' Looking Ahead page (member_polling_view only shows open ones)."""
    poll = get_object_or_404(AvailabilityPoll, id=poll_id)
    poll.is_open = not poll.is_open
    poll.save(update_fields=["is_open"])
    messages.success(request, f"Poll {'reopened' if poll.is_open else 'closed'}.")
    return redirect("committee_polling")


@login_required
@user_passes_test(is_committee)
def committee_rsvp_report(request):
    """
    A dual-panel dashboard showing Event RSVPs and Member Attendance Stats.

    This is the concrete dual-axis attendance implementation: the "Event
    Logistics" panel is project-scoped (Axis 1 - defaults to whichever
    Project is currently ACTIVE, switchable via ?project=<id>), while
    "Member Overview" stays deliberately all-time/unfiltered (Axis 2) -
    a member's overall standing shouldn't reset every time a project
    wraps up.
    """
    # --- PROJECT SCOPING (Event Logistics panel only) ---
    # Distinguish "no ?project= at all" (default to the active project) from
    # "?project= explicitly empty" (the committee chose "All Projects").
    if "project" in request.GET:
        selected_project_id = request.GET.get("project", "")
    else:
        selected_project_id = ""
        active_project = Project.get_active()
        if active_project:
            selected_project_id = str(active_project.id)

    # --- DATASET 1: EVENT-BY-EVENT DATA ---
    # Fetch events, ordered backwards so the latest are at the top. An empty
    # selection (no active project, or "All Projects" explicitly chosen)
    # falls back to every event, preserving the dashboard's original
    # behaviour rather than showing nothing.
    all_events = Event.objects.all().order_by("-date_time")
    if selected_project_id.isdigit():
        all_events = all_events.filter(project_id=selected_project_id)

    # The dropdown/wrapper list stays newest-first (matches the rest of the
    # site), but the *default* selection should be the next upcoming event,
    # not whichever happens to sort first in that list (which, for a
    # project with several future dates already scheduled, was the last
    # one in the cycle rather than the next rehearsal). Falls back to the
    # most recent past event if nothing is upcoming.
    default_event = (
        all_events.filter(date_time__gte=timezone.now())
        .order_by("date_time")
        .first()
        or all_events.first()
    )
    default_event_id = default_event.id if default_event else None

    all_attendances = (
        Attendance.objects.filter(
            event__in=all_events, user__is_active=True, user__profile__is_singer=True
        )
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
    active_users = User.objects.filter(
        is_active=True, profile__is_singer=True
    ).prefetch_related("attendances")
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
        "projects": Project.objects.all(),
        "selected_project_id": selected_project_id,
        "default_event_id": default_event_id,
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
# on committee_hub above. Uploading (POST) is committee-only, enforced
# in-body below.
def committee_documents_view(request):
    """Unified vault to view secure documents. Uploading restricted to committee."""
    if request.method == "POST":
        # HARD STOP: If they aren't committee, block the upload attempt
        if not is_committee(request.user):
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
@require_POST
def committee_document_delete_view(request, document_id):
    """Deletes a document from the vault. Committee-gated in-body rather
    than via @user_passes_test(is_committee) - matches
    committee_documents_view's "open read, committee write" split just
    above: any active member can view the vault, but only committee can
    change what's in it."""
    if not is_committee(request.user):
        messages.error(request, "Only committee members can delete documents.")
        return redirect("committee_documents")

    document = get_object_or_404(CommitteeDocument, id=document_id)
    title = document.title
    document.delete()
    messages.success(request, f"'{title}' deleted from the vault.")
    return redirect("committee_documents")


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
            profile__is_singer=True,  # also guarantees a profile exists
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

    current_term = ChoirSettings.load().current_term
    # ?term= shows an earlier term's ledger; payments logged from that view
    # are logged against that term (the hidden term_reference field).
    selected_term = request.GET.get("term") or current_term
    terms = sorted(
        set(SubscriptionPayment.objects.values_list("term_reference", flat=True))
        - {current_term}
    )

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
        logged_term = post_data["term_reference"]
        if logged_term != current_term:
            return redirect(f"{reverse('committee_financials')}?{urlencode({'term': logged_term})}")
        return redirect("committee_financials")

    # --- 2. BUILD THE ROSTER DISPLAY (GET) ---
    # Fetch all active singers and pre-fetch their profiles to save database hits
    active_users = (
        User.objects.filter(is_active=True, profile__is_singer=True)
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
                member=user.profile, term_reference=selected_term
            ).first()

            roster.append(
                {
                    "user": user,
                    "profile": user.profile,
                    "payment": payment,
                    "is_exempt": is_exempt,  # Pass this to the template
                }
            )

    context = {
        "roster": roster,
        "current_term": current_term,
        "selected_term": selected_term,
        "earlier_terms": terms,
        "subscription_amount": ChoirSettings.load().subscription_amount,
    }
    return render(request, "choir/committee_financials.html", context)


# =============================================================================
# 4.3 COMMITTEE SETTINGS & INBOX
# =============================================================================
@login_required
@user_passes_test(is_committee)
def committee_settings_view(request):
    """Edit the ChoirSettings row: current term, subscription amount and
    deadline, bank details, footer social links."""
    from .forms import ChoirSettingsForm

    choir_settings = ChoirSettings.load()

    if request.method == "POST":
        form = ChoirSettingsForm(request.POST, instance=choir_settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Choir settings saved.")
            return redirect("committee_settings")
    else:
        form = ChoirSettingsForm(instance=choir_settings)

    return render(request, "choir/committee_settings.html", {"form": form})


INBOX_MODELS = {"enquiry": Enquiry, "audition": AuditionApplication}


@login_required
@user_passes_test(is_committee)
def committee_inbox_view(request):
    """Contact-form enquiries and audition applications in one list:
    unhandled first, newest first within each group."""
    items = [
        {"kind": "enquiry", "obj": enquiry}
        for enquiry in Enquiry.objects.select_related("handled_by")
    ] + [
        {"kind": "audition", "obj": application}
        for application in AuditionApplication.objects.select_related("handled_by")
    ]
    items.sort(key=lambda item: item["obj"].created_at, reverse=True)
    items.sort(key=lambda item: item["obj"].handled)  # stable: keeps newest first

    return render(request, "choir/committee_inbox.html", {"items": items})


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_inbox_toggle_view(request, kind, item_id):
    """Marks an enquiry or audition application handled (recording who), or
    back to unhandled if it was marked by mistake."""
    model = INBOX_MODELS.get(kind)
    if model is None:
        raise Http404
    item = get_object_or_404(model, id=item_id)

    item.handled = not item.handled
    item.handled_by = request.user if item.handled else None
    item.save(update_fields=["handled", "handled_by"])

    messages.success(
        request,
        f"{item.name}'s {'enquiry' if kind == 'enquiry' else 'application'} "
        f"marked {'handled' if item.handled else 'not handled'}.",
    )
    return redirect("committee_inbox")


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_inbox_bulk_view(request):
    """Applies one action to the ticked inbox items: "handled" marks them
    handled by the current user; "delete" removes them for good (the
    "Delete as spam" button). Items arrive as "<kind>:<id>" values;
    anything malformed or unknown is ignored."""
    action = request.POST.get("action")
    if action not in ("handled", "delete"):
        messages.error(request, "Choose an action for the selected items.")
        return redirect("committee_inbox")

    ids_by_kind = {kind: [] for kind in INBOX_MODELS}
    for value in request.POST.getlist("items"):
        kind, _, item_id = value.partition(":")
        if kind in ids_by_kind and item_id.isdigit():
            ids_by_kind[kind].append(int(item_id))

    count = 0
    for kind, ids in ids_by_kind.items():
        selected = INBOX_MODELS[kind].objects.filter(id__in=ids)
        if action == "delete":
            count += selected.delete()[0]
        else:
            count += selected.update(handled=True, handled_by=request.user)

    if count == 0:
        messages.info(request, "No items were selected.")
    elif action == "delete":
        messages.success(request, f"{count} item{'s' if count != 1 else ''} deleted as spam.")
    else:
        messages.success(request, f"{count} item{'s' if count != 1 else ''} marked handled.")
    return redirect("committee_inbox")


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
    """The committee's calendar: upcoming events for every non-archived
    project (grouped by project, the project with the soonest event
    first), each with Edit and Delete, plus the form to schedule a new
    rehearsal or residency."""
    from .forms import QuickEventScheduleForm  # Local import to prevent circular traps

    if request.method == "POST":
        form = QuickEventScheduleForm(request.POST)
        if form.is_valid():
            new_event = form.save()
            messages.success(
                request,
                f"Successfully scheduled {new_event.get_event_type_display()} for {new_event.date_time.strftime('%A, %d %B')}.",
            )
            return redirect("committee_schedule")
    else:
        form = QuickEventScheduleForm()

    upcoming = (
        Event.objects.filter(date_time__gte=timezone.now())
        .exclude(project__status="ARCHIVED")
        .select_related("project")
        .order_by("date_time")
    )
    # Dicts keep insertion order, so projects come out ordered by their
    # soonest upcoming event.
    events_by_project = {}
    for event in upcoming:
        events_by_project.setdefault(event.project, []).append(event)

    context = {
        "form": form,
        "events_by_project": events_by_project.items(),
    }
    return render(request, "choir/committee_schedule.html", context)


@login_required
@user_passes_test(is_committee)
def committee_event_edit_view(request, event_id):
    """Edit an event's date, place and type, and write its rehearsal plan
    (additional_notes), which members see on their dashboard."""
    from .forms import EventEditForm

    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        form = EventEditForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save()
            messages.success(
                request,
                f"{event.get_event_type_display()} on {event.date_time.strftime('%A, %d %B')} updated.",
            )
            return redirect("committee_schedule")
    else:
        form = EventEditForm(instance=event)

    return render(
        request, "choir/committee_event_edit.html", {"form": form, "event": event}
    )


@login_required
@user_passes_test(is_committee)
@require_POST
def committee_event_delete_view(request, event_id):
    """Deletes an event and, by cascade, its members' RSVPs. Events in an
    archived project are kept: they're the attendance history."""
    event = get_object_or_404(Event, id=event_id)
    label = f"{event.get_event_type_display()} on {event.date_time.strftime('%A, %d %B %Y')}"

    if event.project.status == "ARCHIVED":
        messages.error(
            request, f"{label} belongs to an archived project, so it can't be deleted."
        )
    else:
        event.delete()
        messages.success(request, f"{label} deleted.")
    return redirect("committee_schedule")


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

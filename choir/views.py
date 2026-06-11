from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required  # Imports the security lock
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import AuditionApplicationForm, EnquiryForm, GiftAidForm
from .models import Event, GiftAidDeclaration, LearningAsset

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
    if request.method == "POST":
        # 1. Traffic control: Check for 'voice_part' instead of 'voice'
        if "voice_part" in request.POST:
            form = AuditionApplicationForm(request.POST)
            is_audition = True
        else:
            form = EnquiryForm(request.POST)
            is_audition = False

        # 2. Validation Check
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
            # THIS IS THE MAGIC DEBUG LINE:
            print("🛑 FORM FAILED VALIDATION! Errors:", form.errors)
            messages.error(
                request, "There was an error with your submission. Please try again."
            )
            # 3. Redirect cleanly WITH an anchor tag
            messages.success(
                request, "Thank you! Your details have been securely recorded."
            )

            # This forces the browser to load /contact/#form-section
            return redirect(reverse("contact") + "#form-section")

    return render(request, "choir/contact.html")


# ==============================================================================
# SECURE MEMBER VIEWS
# ==============================================================================


@login_required
def dashboard_view(request):
    """
    Renders the dashboard with the upcoming schedule and the active repertoire list.
    """
    # 1. Fetch the next 5 upcoming events (both Rehearsals and Performances)
    upcoming_events = (
        Event.objects.filter(date_time__gte=timezone.now())
        .prefetch_related("pieces")
        .order_by("date_time")[:5]
    )

    # 2. Build the "Active Music Library"
    # We use a Python 'set()' to automatically remove any duplicate songs
    current_repertoire = set()
    for event in upcoming_events:
        for piece in event.pieces.all():
            current_repertoire.add(piece)

    context = {
        "upcoming_events": upcoming_events,
        "current_repertoire": current_repertoire,  # Pass the unique list to the template
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


# ==============================================================================
# SYSTEM ERROR HANDLERS
# ==============================================================================


def custom_404(request, exception):
    return render(request, "404.html", status=404)

from django.conf import settings
from django.contrib.auth.models import User  # Django's built-in secure login model
from django.core.mail import send_mail
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.html import strip_tags
from tinymce.models import HTMLField

# ==============================================================================
# 0. PROJECTS
# ==============================================================================


class Project(models.Model):
    """
    The central container for a choir season or concert cycle (e.g.
    "Christmas 2026", "Summer Tour 2028"). Every Event hangs off a Project
    (see Event.project), and Repertoire is attached at the Project level
    (see Project.repertoire, added once Event.project is wired up) rather
    than per-event, so a piece can be reused across projects without
    duplicating rows. Status drives what's exposed to members vs.
    committee - see get_active().
    """

    STATUS_CHOICES = [
        ("PLANNING", "Planning"),
        ("ACTIVE", "Active"),
        ("ARCHIVED", "Archived"),
    ]

    name = models.CharField(
        max_length=150, help_text="e.g., Christmas 2026 or Summer Tour 2028"
    )
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="PLANNING")
    description = models.TextField(blank=True)

    # Optional - a Project can exist (PLANNING) before firm dates are known.
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @classmethod
    def get_active(cls):
        """
        Soft convention, not DB-enforced: if more than one Project is
        ACTIVE at once (a deliberate handoff overlap between projects),
        the one with the most recent start_date wins (see Meta.ordering).
        Returns None if no Project is currently ACTIVE.
        """
        return cls.objects.filter(status="ACTIVE").first()


# ==============================================================================
# 1. PEOPLE & FINANCE
# ==============================================================================


class MemberProfile(models.Model):
    """
    Extends the built-in Django User model to hold choir-specific data,
    including duty of care and legal consents.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    VOICE_CHOICES = [
        ("S", "Soprano"),
        ("A", "Alto"),
        ("T", "Tenor"),
        ("B", "Bass"),
    ]
    voice_part = models.CharField(
        max_length=1, choices=VOICE_CHOICES, blank=True, null=True
    )
    phone_number = models.CharField(max_length=20, blank=True)

    # --- 1. Duty of Care (Emergency Contacts) ---
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    # --- 2. Media & Publicity Permissions ---
    # Defaulting to False protects you under GDPR; they must actively opt-in.
    consent_audio_video = models.BooleanField(
        default=False,
        help_text="I consent to being included in audio and video recordings for promotional purposes.",
    )
    consent_photography = models.BooleanField(
        default=False,
        help_text="I consent to being photographed for social media and website use.",
    )

    # --- 3. Medical and Accessibility Requirements ---
    medical_accessibility_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Optional: Please share any health, medical, or accessibility requirements (e.g., mobility needs, severe allergies) that the committee should be aware of to support you during rehearsals and events.",
    )
    # Safeguarding Flag
    is_under_18 = models.BooleanField(
        default=False,
        help_text="Flags member for safeguarding and duty of care protocols.",
    )

    # Financial Flag
    is_exempt_from_subs = models.BooleanField(
        default=False,
        help_text="Exempts member from the termly financial ledger (e.g., scholars, bursaries, staff).",
    )

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_voice_part_display()})"


class GiftAidDeclaration(models.Model):
    """
    Stores financial compliance data.
    """

    member = models.OneToOneField(MemberProfile, on_delete=models.CASCADE)

    # Snapshot of the data at the time of signing, exactly as HMRC requires
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    address_line_1 = models.CharField(max_length=200)
    town_city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=20)

    consent_given = models.BooleanField(default=False)
    date_signed = models.DateTimeField(
        auto_now_add=True
    )  # Automatically records exact timestamp

    def __str__(self):
        return f"Gift Aid: {self.first_name} {self.last_name}"


class SubscriptionPayment(models.Model):
    """
    Ledger for tracking who has paid what and when.
    Prepared for both manual entry and automated Stripe webhooks.
    """

    PAYMENT_METHODS = [
        ("CARD", "Online (Stripe/Card)"),
        ("CASH", "Cash"),
        ("BACS", "Bank Transfer (BACS)"),
        ("MIX", "Mixed / Other"),
    ]

    member = models.ForeignKey(
        MemberProfile, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    date_paid = models.DateField()
    term_reference = models.CharField(
        max_length=100, help_text="e.g., Autumn 2026 or Annual 26/27"
    )

    # --- NEW FIELDS FOR THE UPGRADED LEDGER ---
    payment_method = models.CharField(
        max_length=4, choices=PAYMENT_METHODS, default="BACS"
    )

    # Stripe will eventually pass a unique "pi_..." token here.
    # It is blank=True because cash payments won't have one!
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stripe PaymentIntent ID or Cheque Number",
    )

    # For manual administrative context
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="e.g., 'Paid half in cash, remainder to be transferred'",
    )

    def __str__(self):
        return f"£{self.amount} - {self.member.user.get_full_name()} ({self.term_reference})"


# ==============================================================================
# 2. MUSIC & ASSETS
# ==============================================================================


class Repertoire(models.Model):
    """
    The core musical works.
    """

    composer = models.CharField(max_length=100)
    title = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.composer}: {self.title}"


class LearningAsset(models.Model):
    """
    The PDFs, MP3s, and YouTube links tied to specific repertoire.
    """

    # Many-to-1: One Repertoire piece (Mozart Requiem) has many Assets (Soprano track, PDF score)
    repertoire = models.ForeignKey(
        Repertoire, on_delete=models.CASCADE, related_name="assets"
    )

    PART_CHOICES = [
        ("SOP", "Soprano"),
        ("ALT", "Alto"),
        ("TEN", "Tenor"),
        ("BAS", "Bass"),
        ("ALL", "Full Choir / PDF Score"),
    ]
    voice_part = models.CharField(max_length=3, choices=PART_CHOICES)

    asset_name = models.CharField(
        max_length=150, help_text="e.g., YouTube Practice Track or PDF Score"
    )

    # We provide two options: a direct file upload or an external URL (like YouTube)
    file_upload = models.FileField(upload_to="learning_assets/", blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.repertoire.title} - {self.get_voice_part_display()} Asset"


# ==============================================================================
# 3. LOGISTICS
# ==============================================================================


class Attendance(models.Model):
    """
    Intermediate model tracking the RSVP status of individual choir members for specific events.
    """

    STATUS_CHOICES = [
        ("PENDING", "No Response"),
        ("ATTENDING", "Attending"),
        ("ABSENT", "Absent"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="attendances")
    event = models.ForeignKey("Event", on_delete=models.CASCADE, related_name="rsvps")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Prevents a user from having duplicate RSVP records for a single event
        unique_together = ("user", "event")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.event}: {self.get_status_display()}"


class Event(models.Model):
    """
    Unifies Rehearsals and Performances into a single timeline.
    """

    EVENT_TYPES = [
        ("REH", "Standard Rehearsal"),
        ("RES", "Cathedral Residency / Performance"),
    ]
    event_type = models.CharField(max_length=3, choices=EVENT_TYPES, default="REH")

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="events")

    date_time = models.DateTimeField()
    location = models.CharField(max_length=200, default="St Laurence's Church")
    additional_notes = HTMLField(blank=True)

    # Many-to-Many: An event features multiple pieces, a piece is sung at multiple events.
    pieces = models.ManyToManyField(Repertoire, blank=True, related_name="events")

    # The clean link to your members via the intermediate model
    attendees = models.ManyToManyField(
        User, through=Attendance, related_name="events_attending", blank=True
    )

    def __str__(self):
        return (
            f"{self.get_event_type_display()}: {self.date_time.strftime('%A %d %B %Y')}"
        )


class CommitteeDocument(models.Model):
    """Secure vault for committee-only files and meeting minutes."""

    DOC_TYPES = [
        ("MIN", "Meeting Minutes"),
        ("POL", "Policy / Governance"),
        ("FIN", "Financial Report"),
        ("GEN", "General Document"),
    ]

    title = models.CharField(max_length=200, help_text="e.g., AGM Minutes - June 2026")
    doc_type = models.CharField(max_length=3, choices=DOC_TYPES, default="MIN")

    # Files will securely upload to a dedicated folder in your cloud bucket
    file = models.FileField(upload_to="committee_docs/")

    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]  # Automatically sorts newest first

    def __str__(self):
        return f"{self.title} ({self.get_doc_type_display()})"


# ==============================================================================
# 4. CONTACT
# ==============================================================================


class Enquiry(models.Model):
    """Stores general contact submissions and booking requests."""

    SUBJECT_CHOICES = [
        ("general", "General Enquiry"),
        ("booking", "Concert Booking"),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(
        max_length=20, choices=SUBJECT_CHOICES, default="general"
    )
    message = models.TextField()
    created_at = models.DateTimeField(
        auto_now_add=True
    )  # Automatically timestamps the entry

    class Meta:
        verbose_name_plural = (
            "Enquiries"  # Fixes Django's default "Enquitys" spelling typo
        )

    def __str__(self):
        return f"{self.subject.title()} from {self.name}"


class AuditionApplication(models.Model):
    """Stores prospective singer applications."""

    VOICE_CHOICES = [
        ("soprano", "Soprano"),
        ("alto", "Alto"),
        ("tenor", "Tenor"),
        ("baritone", "Baritone"),
        ("bass", "Bass"),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    voice_part = models.CharField(max_length=20, choices=VOICE_CHOICES)
    experience = models.TextField(blank=True, null=True)  # Optional field
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Audition application: {self.name} ({self.voice_part.title()})"


class ChoirCommunication(models.Model):
    """An outbox for official choir broadcasts and headed letters."""

    AUDIENCE_CHOICES = [
        ("ALL", "All Active Members"),
        ("SOP", "Sopranos Only"),
        ("ALT", "Altos Only"),
        ("TEN", "Tenors Only"),
        ("BAS", "Basses Only"),
    ]

    audience = models.CharField(max_length=3, choices=AUDIENCE_CHOICES, default="ALL")
    subject = models.CharField(max_length=200)

    # UPGRADED: This tells the admin panel to render the TinyMCE editor
    message = HTMLField(help_text="The body of your email.")

    sent_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"[{self.get_audience_display()}] {self.subject} ({self.sent_at.strftime('%d %b %Y')})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        super().save(*args, **kwargs)

        if is_new:
            # 1. Gather the recipients
            if self.audience == "ALL":
                recipients = User.objects.filter(is_active=True)
            else:
                recipients = User.objects.filter(
                    is_active=True, profile__voice_part=self.audience[0]
                )

            # 2. Fire the email via Brevo - one send per recipient, not one
            # shared recipient_list, so members' addresses stay private from
            # each other.
            # Create a clean, stripped-down version of the email for older email clients
            # or strict spam filters that reject HTML.
            plain_message = strip_tags(self.message)

            for user in recipients:
                if not user.email:
                    continue
                send_mail(
                    subject=self.subject,
                    message=plain_message,  # The plain-text fallback
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=self.message,  # THE MAGIC: Injects your TinyMCE formatting!
                    fail_silently=False,
                )


# ==============================================================================
# SIGNALS: Automate Profile Creation
# ==============================================================================


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Listens for a new User being created. When it hears one,
    it automatically generates a blank MemberProfile linked to it.
    """
    if created:
        MemberProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensures the profile saves whenever the core User object saves.
    """
    instance.profile.save()


# NOTE: the "new Event -> backfill Attendance for every active user" receiver
# lives in choir/signals.py (auto_add_existing_users_to_new_event), not here.
# It used to be defined in both places, which raced against the same
# Attendance.unique_together=("user", "event") constraint and raised
# IntegrityError on every new Event. Keep it in exactly one place.

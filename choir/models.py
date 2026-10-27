from django.conf import settings
from django.contrib.auth.models import User  # Django's built-in secure login model
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.html import strip_tags
from tinymce.models import HTMLField

# ==============================================================================
# 00. CHOIR SETTINGS
# ==============================================================================


class ChoirSettings(models.Model):
    """
    The choir's site-wide settings, edited by the committee on the site
    (committee_settings) instead of in code: the current subscription term
    and what it costs, the bank details members pay into, the footer's
    social links, and the switch for the database-driven Events page.

    Exactly one row (pk=1). Always read it through ChoirSettings.load().
    Changing current_term is what starts a new subscription period: the
    ledger and the member dashboard look up payments for that term only,
    so everyone shows as Unpaid again while earlier terms' payments stay.
    """

    current_term = models.CharField(
        max_length=100, help_text="e.g., Autumn 2026. Payments are logged against this."
    )
    subscription_amount = models.DecimalField(
        max_digits=6, decimal_places=2, default=50, help_text="Per term, in pounds."
    )
    subscription_deadline = models.DateField(
        blank=True, null=True, help_text="Optional. Shown to members when set."
    )

    bank_account_name = models.CharField(max_length=100, blank=True)
    bank_sort_code = models.CharField(max_length=8, blank=True)
    bank_account_number = models.CharField(max_length=8, blank=True)

    # Build Order Phase 9: the public Events page reads Event rows when on.
    events_page_from_db = models.BooleanField(default=False)

    # Footer icons; each one only shows once its URL is filled in.
    youtube_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)

    class Meta:
        verbose_name = "Choir settings"
        verbose_name_plural = "Choir settings"

    def __str__(self):
        return "Choir settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """
        The settings row, created if it's missing. settings.CURRENT_TERM is
        the fallback term for one release only; Build Order Phase 11
        removes it once this row is the single source of truth.
        """
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"current_term": getattr(settings, "CURRENT_TERM", "")},
        )
        return obj


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
    # Shown with the project's public performances on the Events page
    # (Build Order Phase 9); description stays committee-only.
    public_summary = models.TextField(blank=True)

    # Optional - a Project can exist (PLANNING) before firm dates are known.
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    # Many-to-Many: a piece is a permanent organisational asset, reusable
    # across projects without duplicating Repertoire rows. "Repertoire" is
    # a forward string reference since that class is defined later in this
    # file (section 2. MUSIC & ASSETS) - Django resolves it at app-loading
    # time, not at this class's definition time, so the ordering is fine.
    repertoire = models.ManyToManyField(
        "Repertoire", blank=True, related_name="projects"
    )

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

    @classmethod
    def get_active_projects(cls):
        """
        All ACTIVE projects, soonest start_date first (nulls last) - for
        contexts that support the deliberate overlap get_active() only
        picks one winner from (the member dashboard's project tabs),
        rather than a single "primary" project.
        """
        return cls.objects.filter(status="ACTIVE").order_by(
            models.F("start_date").asc(nulls_last=True), "created_at"
        )


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

    # Unticked for people with a login who don't sing (see
    # choir.permissions.is_singer): they get no RSVPs and are left out of
    # the ledger, RSVP report, Duty of Care roster and broadcasts.
    is_singer = models.BooleanField(
        default=True,
        help_text="Untick for members who have a login but don't sing (e.g. an accompanist or administrator).",
    )

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


class InvitationProfile(models.Model):
    """
    What the committee knew about someone when inviting them (name, voice
    part), kept with the django-invitations Invitation and copied onto the
    new member's User and MemberProfile when they accept by signing up
    (choir.signals.apply_invitation_profile).
    """

    invitation = models.OneToOneField(
        "invitations.Invitation", on_delete=models.CASCADE, related_name="choir_profile"
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    voice_part = models.CharField(max_length=1, choices=MemberProfile.VOICE_CHOICES, blank=True)

    def __str__(self):
        return f"Invitation details for {self.invitation.email}"


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

    # When the asset was added; shown on the member hub. Null for assets
    # that predate the field (deliberately not auto_now_add, which would
    # stamp every existing row with the migration's run time).
    uploaded_at = models.DateTimeField(null=True, blank=True, editable=False)

    def __str__(self):
        return f"{self.repertoire.title} - {self.get_voice_part_display()} Asset"

    def save(self, *args, **kwargs):
        if self._state.adding and self.uploaded_at is None:
            self.uploaded_at = timezone.now()
        super().save(*args, **kwargs)


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

    # --- Public listing (Build Order Phase 9) ---
    # Only residencies/performances (event_type "RES") with is_public set
    # ever appear on the public Events page; rehearsals never do.
    is_public = models.BooleanField(
        default=False, help_text="Show this performance on the public Events page."
    )
    public_title = models.CharField(
        max_length=200, blank=True, help_text="e.g., Choral Evensong. Defaults to the event type."
    )
    public_blurb = models.TextField(blank=True, help_text="A sentence or two for the public listing.")
    ticket_url = models.URLField(blank=True, help_text="Optional link for tickets or booking.")
    end_time = models.DateTimeField(
        blank=True, null=True, help_text="Optional. Used for calendar files; otherwise two hours."
    )

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


class AvailabilityPoll(models.Model):
    """
    A committee-created question tied to a PLANNING-phase Project, used to
    gauge ensemble availability before committing to a venue or date.
    Member-facing surface is deliberately narrow: question/proposed_date/
    notes only, never the parent Project's repertoire or description.
    """

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="polls")
    question = models.CharField(
        max_length=200,
        help_text="e.g., Are you available the weekend of 14-15 March 2027?",
    )
    proposed_date = models.DateField(
        blank=True, null=True, help_text="Optional - the specific date being tested."
    )
    notes = models.TextField(
        blank=True, help_text="Extra context for members, e.g. venue under consideration."
    )
    is_open = models.BooleanField(
        default=True,
        help_text="Closes the poll to new or changed responses once the committee has decided.",
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["proposed_date", "created_at"]

    def __str__(self):
        return f"{self.project.name}: {self.question}"


class AvailabilityResponse(models.Model):
    """A member's answer to a single AvailabilityPoll."""

    RESPONSE_CHOICES = [
        ("YES", "Available"),
        ("NO", "Not Available"),
        ("MAYBE", "Maybe"),
    ]

    poll = models.ForeignKey(
        AvailabilityPoll, on_delete=models.CASCADE, related_name="responses"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="availability_responses"
    )
    response = models.CharField(max_length=5, choices=RESPONSE_CHOICES)
    notes = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional - e.g. 'Away until the 10th, fine after that.'",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("poll", "user")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.poll.question}: {self.get_response_display()}"


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

    # Committee inbox (committee_inbox): who dealt with it, if anyone has.
    handled = models.BooleanField(default=False)
    handled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

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

    # Committee inbox (committee_inbox): who dealt with it, if anyone has.
    handled = models.BooleanField(default=False)
    handled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    def __str__(self):
        return f"Audition application: {self.name} ({self.voice_part.title()})"


class ChoirCommunication(models.Model):
    """
    A broadcast email to the choir (all singers or one voice part).

    Written as a DRAFT on the committee's Broadcast page, previewed, tested
    on the author's own inbox, then sent once with send(). Saving never
    sends anything; sending is explicit. Each recipient gets a
    BroadcastDelivery row recording whether Brevo accepted their copy.
    """

    AUDIENCE_CHOICES = [
        ("ALL", "All Active Members"),
        ("SOP", "Sopranos Only"),
        ("ALT", "Altos Only"),
        ("TEN", "Tenors Only"),
        ("BAS", "Basses Only"),
    ]
    STATUS_CHOICES = [("DRAFT", "Draft"), ("SENT", "Sent")]

    audience = models.CharField(max_length=3, choices=AUDIENCE_CHOICES, default="ALL")
    subject = models.CharField(max_length=200)

    # UPGRADED: This tells the admin panel to render the TinyMCE editor
    message = HTMLField(help_text="The body of your email.")

    status = models.CharField(max_length=5, choices=STATUS_CHOICES, default="DRAFT")
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-sent_at", "-id"]

    def __str__(self):
        when = self.sent_at.strftime("%d %b %Y") if self.sent_at else "draft"
        return f"[{self.get_audience_display()}] {self.subject} ({when})"

    @property
    def is_sent(self):
        return self.status == "SENT"

    def recipients(self):
        """Active singers (MemberProfile.is_singer) in the audience, with an
        email address."""
        users = User.objects.filter(is_active=True, profile__is_singer=True).exclude(email="")
        if self.audience != "ALL":
            users = users.filter(profile__voice_part=self.audience[0])
        return users.order_by("first_name", "last_name")

    def _email(self, to, subject=None):
        message = EmailMultiAlternatives(
            subject=subject or self.subject,
            body=strip_tags(self.message),  # plain-text fallback
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
        )
        message.attach_alternative(self.message, "text/html")
        return message

    def send_test(self, user):
        """Send this broadcast to one person (its author, checking it),
        marked as a test. Records nothing and changes nothing."""
        self._email([user.email], subject=f"[Test] {self.subject}").send()

    def send(self):
        """
        Send to every recipient, once. One API call: with merge_data set,
        Anymail's Brevo backend sends a separate copy to each address
        (batch sending), so members never see each other's addresses.

        Marked SENT before sending, so a failure part-way can never lead to
        a second send. Any error is recorded per recipient in
        BroadcastDelivery rather than raised. Returns (sent_ok, failed).
        """
        if self.is_sent:
            raise ValueError("This broadcast has already been sent.")

        users = list(self.recipients())
        self.status = "SENT"
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

        if not users:
            return 0, 0

        message = self._email([user.email for user in users])
        message.merge_data = {}  # batch send: one private copy per recipient
        try:
            message.send()
            statuses = getattr(getattr(message, "anymail_status", None), "recipients", {}) or {}
            deliveries = []
            for user in users:
                status = statuses.get(user.email)
                ok = status is None or status.status in ("sent", "queued", "scheduled")
                deliveries.append(
                    BroadcastDelivery(
                        communication=self,
                        user=user,
                        sent_ok=ok,
                        error="" if ok else f"Brevo status: {status.status}",
                    )
                )
        except Exception as error:  # never raise after the row is saved
            deliveries = [
                BroadcastDelivery(communication=self, user=user, sent_ok=False, error=str(error)[:500])
                for user in users
            ]

        BroadcastDelivery.objects.bulk_create(deliveries)
        sent_ok = sum(1 for delivery in deliveries if delivery.sent_ok)
        return sent_ok, len(deliveries) - sent_ok


class BroadcastDelivery(models.Model):
    """One recipient's copy of a sent broadcast: whether Brevo accepted it,
    and the error if not."""

    communication = models.ForeignKey(ChoirCommunication, on_delete=models.CASCADE, related_name="deliveries")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    sent_ok = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    def __str__(self):
        return f"{self.communication.subject} to {self.user}: {'ok' if self.sent_ok else 'failed'}"


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
def save_user_profile(sender, instance, created, **kwargs):
    """
    Makes sure an existing user has a profile (accounts that predate
    profiles). Deliberately never re-saves one that exists: this used to
    call instance.profile.save() on every User save, so any later save of
    a User object (allauth recording a login, say) wrote its stale
    in-memory copy of the profile over changes made since - it wiped the
    voice part an invitation had just set. Code that changes a profile
    saves the profile itself.
    """
    if not created:
        MemberProfile.objects.get_or_create(user=instance)


# NOTE: the "new Event -> backfill Attendance for every active user" receiver
# lives in choir/signals.py (auto_add_existing_users_to_new_event), not here.
# It used to be defined in both places, which raced against the same
# Attendance.unique_together=("user", "event") constraint and raised
# IntegrityError on every new Event. Keep it in exactly one place.

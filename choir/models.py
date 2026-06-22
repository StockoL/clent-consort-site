from django.contrib.auth.models import User  # Django's built-in secure login model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from tinymce.models import HTMLField

# ==============================================================================
# 1. PEOPLE & FINANCE
# ==============================================================================


class MemberProfile(models.Model):
    """
    Extends the built-in Django User model to hold choir-specific data.
    """

    # 1-to-1: If the User is deleted, the Profile is automatically deleted (CASCADE)
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
    """

    # Many-to-1: One member can have dozens of payment records over time
    member = models.ForeignKey(
        MemberProfile, on_delete=models.CASCADE, related_name="payments"
    )

    amount = models.DecimalField(max_digits=6, decimal_places=2)  # e.g., 150.00
    date_paid = models.DateField()
    term_reference = models.CharField(
        max_length=100, help_text="e.g., Autumn 2026 or Annual 26/27"
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

    # 1. Removed unique=True for now
    # 2. Added null=True, blank=True
    slug = models.SlugField(
        max_length=200,
        null=True,
        blank=True,
        help_text="URL-friendly name (e.g., mozart-requiem)",
    )

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

    date_time = models.DateTimeField()
    location = models.CharField(max_length=200, default="St Laurence's Church")
    additional_notes = additional_notes = HTMLField(blank=True)

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


@receiver(post_save, sender=Event)
def create_attendance_records_for_new_event(sender, instance, created, **kwargs):
    """
    Automator: The absolute millisecond an admin saves a new Event,
    this loop generates a 'PENDING' RSVP placeholder for every active choir member.
    """
    if created:
        active_users = User.objects.filter(is_active=True)

        # Performance trick: bulk_create hits the database once instead of performing dozens of separate writes
        attendance_placeholders = [
            Attendance(user=user, event=instance, status="PENDING")
            for user in active_users
        ]
        Attendance.objects.bulk_create(attendance_placeholders)

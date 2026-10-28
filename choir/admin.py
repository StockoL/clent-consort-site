from django.contrib import admin

from .models import (
    Attendance,
    AuditionApplication,
    AvailabilityPoll,
    AvailabilityResponse,
    BroadcastDelivery,
    ChoirCommunication,
    ChoirSettings,
    CommitteeDocument,
    Enquiry,
    Event,
    LearningAsset,
    MemberProfile,
    Project,
    Repertoire,
    Section,
    SubscriptionPayment,
)


# ==============================================================================
# 00. CHOIR SETTINGS
# ==============================================================================
@admin.register(ChoirSettings)
class ChoirSettingsAdmin(admin.ModelAdmin):
    """Fallback for the committee Settings page. There is exactly one row
    (ChoirSettings.load() creates it), so it can't be added or deleted."""

    def has_add_permission(self, request):
        return not ChoirSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ==============================================================================
# 0. PROJECTS
# ==============================================================================
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    # Day-to-day management happens on the committee's own frontend pages
    # (committee_projects/committee_project_edit) - this registration exists
    # so admin access still works for direct DB inspection, matching every
    # other model in this app staying admin-registered regardless of
    # whether a frontend view also exists.
    list_display = ("name", "status", "start_date")
    list_filter = ("status",)

    # This single line replaces the clunky Ctrl-Click box with a beautiful
    # dual-panel UI - moved here from EventAdmin now that repertoire is
    # attached at the project level, not per-event.
    filter_horizontal = ("repertoire",)


# ==============================================================================
# 1. PEOPLE & FINANCE
# ==============================================================================
@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    # Keep is_under_18 on the main spreadsheet view for quick safeguarding checks
    list_display = (
        "get_username",
        "get_full_name",
        "voice_part",
        "is_singer",
        "phone_number",
        "is_under_18",
    )
    list_editable = ("is_under_18",)

    list_filter = (
        "is_singer",
        "voice_part",
        "is_under_18",
        "is_exempt_from_subs",
    )  # Added to filters!

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "phone_number",
    )

    fieldsets = (
        ("User Link", {"fields": ("user",)}),
        ("Choir Details", {"fields": ("voice_part", "is_singer", "phone_number")}),
        # New dedicated section for finances
        ("Financial Settings", {"fields": ("is_exempt_from_subs",)}),
        (
            "Duty of Care & Safeguarding",  # Renamed slightly for clarity
            {
                "fields": (
                    "is_under_18",
                    "emergency_contact_name",
                    "emergency_contact_relation",
                    "emergency_contact_phone",
                )
            },
        ),
        (
            "Media & Publicity Permissions",
            {"fields": ("consent_audio_video", "consent_photography")},
        ),
        (
            "Medical & Accessibility Support",
            {"fields": ("medical_accessibility_notes",)},
        ),
    )

    def get_username(self, obj):
        return obj.user.username

    get_username.short_description = "Username"

    def get_full_name(self, obj):
        return obj.user.get_full_name() or "No Name Set"

    get_full_name.short_description = "Full Name"


admin.site.register(SubscriptionPayment)


# ==============================================================================
# 2. LOGISTICS
# ==============================================================================
class AttendanceInline(admin.TabularInline):
    """
    Creates a spreadsheet-style list of RSVPs directly inside the Event page.
    """

    model = Attendance
    extra = 0  # Stops Django from adding empty blank rows at the bottom

    # We only lock 'updated_at' (because it is an auto-timestamp).
    # 'user' and 'status' are now editable so you can manually backfill records!
    readonly_fields = ("updated_at",)

    can_delete = False  # Data integrity: Prevents accidental row deletion
    ordering = ("status", "user__username")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "date_time", "location", "project")
    list_filter = ("event_type", "date_time", "project")

    # Injects the RSVP list at the bottom of the event page
    inlines = [AttendanceInline]


class AvailabilityResponseInline(admin.TabularInline):
    model = AvailabilityResponse
    extra = 0
    readonly_fields = ("updated_at",)


@admin.register(AvailabilityPoll)
class AvailabilityPollAdmin(admin.ModelAdmin):
    # Day-to-day management happens on the committee's own frontend page
    # (committee_polling) - see the note on ProjectAdmin.
    list_display = ("question", "project", "proposed_date", "is_open")
    list_filter = ("is_open", "project")
    inlines = [AvailabilityResponseInline]


# ==============================================================================
# 3. CONTACT & ENQUIRIES
# ==============================================================================
@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "created_at", "handled")
    list_filter = ("handled", "subject", "created_at")
    ordering = ("-created_at",)


@admin.register(AuditionApplication)
class AuditionApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "voice_part", "created_at", "handled")
    list_filter = ("handled", "voice_part", "created_at")
    ordering = ("-created_at",)


# ==============================================================================
# 4. MUSIC LIBRARY (With the Inline Uploads!)
# ==============================================================================
class LearningAssetInline(admin.TabularInline):
    model = LearningAsset
    extra = 2
    fields = ["asset_name", "voice_part", "part_name", "use_player", "file_upload", "external_url"]


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ["order", "label", "bar_start", "bar_end", "start_seconds", "end_seconds", "published"]


@admin.register(Repertoire)
class RepertoireAdmin(admin.ModelAdmin):
    list_display = ("composer", "title")
    inlines = [LearningAssetInline, SectionInline]


# ==============================================================================
# 5. COMMUNICATIONS HUB
# ==============================================================================
class BroadcastDeliveryInline(admin.TabularInline):
    model = BroadcastDelivery
    extra = 0
    can_delete = False
    fields = ("user", "sent_ok", "error")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChoirCommunication)
class ChoirCommunicationAdmin(admin.ModelAdmin):
    """Fallback view of broadcasts. Saving here never sends anything: a
    broadcast created here is a draft, sent from the committee's Broadcast
    page (preview, test, then send). Once sent it's locked as a record."""

    list_display = ("subject", "get_audience_display", "status", "sent_at", "author")
    list_filter = ("status", "audience", "sent_at")
    search_fields = ("subject", "message")
    inlines = [BroadcastDeliveryInline]

    # Lock a sent broadcast, so its record can't be edited after the fact.
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_sent:
            return ("audience", "subject", "message", "author", "status", "sent_at")
        return ("author", "status", "sent_at")

    # Automatically stamp the logged-in admin as the author
    def save_model(self, request, obj, form, change):
        if getattr(obj, "author", None) is None:
            obj.author = request.user
        obj.save()


# ==============================================================================
# 6. COMMITTEE DOCUMENTS
# ==============================================================================
@admin.register(CommitteeDocument)
class CommitteeDocumentAdmin(admin.ModelAdmin):
    # Day-to-day management happens on the committee's own frontend page
    # (committee_documents) - this registration exists for direct DB
    # inspection, matching every other model in this app.
    list_display = ("title", "doc_type", "uploaded_by", "uploaded_at")
    list_filter = ("doc_type", "uploaded_at")

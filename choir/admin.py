from django.contrib import admin

from .models import (
    Attendance,
    AuditionApplication,
    ChoirCommunication,
    Enquiry,
    Event,
    GiftAidDeclaration,
    LearningAsset,
    MemberProfile,
    Project,
    Repertoire,
    SubscriptionPayment,
)


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
        "phone_number",
        "is_under_18",
    )
    list_editable = ("is_under_18",)

    list_filter = (
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
        ("Choir Details", {"fields": ("voice_part", "phone_number")}),
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


admin.site.register(GiftAidDeclaration)
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

    # This single line replaces the clunky Ctrl-Click box with a beautiful dual-panel UI
    filter_horizontal = ("pieces",)

    # Injects the RSVP list at the bottom of the event page
    inlines = [AttendanceInline]


# ==============================================================================
# 3. CONTACT & ENQUIRIES
# ==============================================================================
@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "created_at")
    list_filter = ("subject", "created_at")
    ordering = ("-created_at",)


@admin.register(AuditionApplication)
class AuditionApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "voice_part", "created_at")
    list_filter = ("voice_part", "created_at")
    ordering = ("-created_at",)


# ==============================================================================
# 4. MUSIC LIBRARY (With the Inline Uploads!)
# ==============================================================================
class LearningAssetInline(admin.TabularInline):
    model = LearningAsset
    extra = 2
    fields = ["asset_name", "voice_part", "file_upload", "external_url"]


@admin.register(Repertoire)
class RepertoireAdmin(admin.ModelAdmin):
    list_display = ("composer", "title")
    inlines = [LearningAssetInline]


# ==============================================================================
# 5. COMMUNICATIONS HUB
# ==============================================================================
@admin.register(ChoirCommunication)
class ChoirCommunicationAdmin(admin.ModelAdmin):
    list_display = ("subject", "get_audience_display", "sent_at", "author")
    list_filter = ("audience", "sent_at")
    search_fields = ("subject", "message")

    # Lock the fields so you can't accidentally re-send or edit an email that
    # has already gone out to 24 people.
    def get_readonly_fields(self, request, obj=None):
        if obj:  # If the object already exists, lock everything down
            return ("audience", "subject", "message", "author", "sent_at")
        return ("author", "sent_at")  # If it's new, let them type!

    # Automatically stamp the logged-in admin as the author
    def save_model(self, request, obj, form, change):
        if getattr(obj, "author", None) is None:
            obj.author = request.user
        obj.save()

from django.contrib import admin

from .models import (
    Attendance,
    AuditionApplication,
    Enquiry,
    Event,
    GiftAidDeclaration,
    LearningAsset,
    MemberProfile,
    Repertoire,
    SubscriptionPayment,
)


# ==============================================================================
# 1. PEOPLE & FINANCE
# ==============================================================================
@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ("get_username", "get_full_name", "voice_part", "phone_number")

    # We add the new consent booleans to the filter sidebar so you can instantly
    # generate a list of "who cannot be photographed" before a concert.
    list_filter = ("voice_part", "consent_audio_video", "consent_photography")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "phone_number",
    )

    # This organizes the individual member page into clean, logical sections
    fieldsets = (
        ("User Link", {"fields": ("user",)}),
        ("Choir Details", {"fields": ("voice_part", "phone_number")}),
        (
            "Duty of Care (Emergency Contact)",
            {
                "fields": (
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
    list_display = ("event_type", "date_time", "location")
    list_filter = ("event_type", "date_time")

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
    list_display = ("composer", "title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [LearningAssetInline]

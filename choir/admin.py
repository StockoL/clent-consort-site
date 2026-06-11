from django.contrib import admin

from .models import (
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
    # This turns your list view into a beautiful multi-column table
    list_display = ("get_username", "get_full_name", "voice_part", "phone_number")

    # Adds a clickable filter sidebar on the right hand side
    list_filter = ("voice_part",)

    # Adds a powerful search bar at the top of the screen
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "phone_number",
    )

    # Helper methods to pull data cleanly from the linked User model
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
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "date_time", "location")
    list_filter = ("event_type", "date_time")

    # This single line replaces the clunky Ctrl-Click box with a beautiful dual-panel UI
    filter_horizontal = ("pieces",)


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

"""
URL configuration for clent_consort_site project.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

# 1. ADD 'committee_schedule_event' TO YOUR EXPLICIT IMPORTS TUPLE BELOW
from choir.views import (
    about_view,
    committee_broadcast,
    committee_documents_view,
    committee_financials_view,
    committee_hub,
    committee_rsvp_report,
    committee_schedule_event,  # <-- ADD THIS IMPORT LINE HERE
    contact_view,
    dashboard_view,
    download_ics,
    events_view,
    giftaid_view,
    home_view,
    hub_view,
    login_redirect_router,
    settings_view,
    update_rsvp_view,
)

urlpatterns = [
    # --- Django Admin ---
    path("admin/", admin.site.urls),
    path("tinymce/", include("tinymce.urls")),
    # --- The Allauth Security Doorman ---
    path("accounts/", include("allauth.urls")),
    # Wire in the Invitation listener
    path("invitations/", include("invitations.urls", namespace="invitations")),
    # --- Public Pages ---
    path("", home_view, name="home"),
    path("about/", about_view, name="about"),
    path("events/", events_view, name="events"),
    path("contact/", contact_view, name="contact"),
    # --- Secure Member Area ---
    path("members/", dashboard_view, name="members"),
    path("members/giftaid/", giftaid_view, name="giftaid"),
    path("members/hub/<str:voice_part>/", hub_view, name="hub"),
    path("members/settings/", settings_view, name="settings"),
    # --- Committee Area ---
    path("members/committee/", committee_hub, name="committee_hub"),
    path("members/committee/rsvps/", committee_rsvp_report, name="committee_rsvps"),
    path(
        "members/committee/broadcast/", committee_broadcast, name="committee_broadcast"
    ),
    # 2. ADD THE ROUTING PATH PATTERN EXACTLY HERE
    path("accounts/profile/", login_redirect_router, name="login_redirect"),
    path(
        "members/committee/schedule/",
        committee_schedule_event,
        name="committee_schedule",
    ),
    path(
        "members/committee/documents/",
        committee_documents_view,
        name="committee_documents",
    ),
    path(
        "members/committee/financials/",
        committee_financials_view,
        name="committee_financials",
    ),
    # --- Action Handlers ---
    path("rsvp/<int:attendance_id>/", update_rsvp_view, name="update_rsvp"),
    path("event/<int:event_id>/calendar/", download_ics, name="download_ics"),
    # --- Utilities ---
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/images/favicon.ico", permanent=True),
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path(
        "sitemap.xml",
        TemplateView.as_view(
            template_name="sitemap.xml", content_type="application/xml"
        ),
    ),
]

handler404 = "choir.views.custom_404"

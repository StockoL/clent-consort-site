"""
URL configuration for clent_consort_site project.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

# 1. ADD 'committee_schedule_event' TO YOUR EXPLICIT IMPORTS TUPLE BELOW
from choir.views import (
    about_view,
    committee_asset_delete_view,
    committee_broadcast,
    committee_broadcast_delete_view,
    committee_broadcast_preview_view,
    committee_broadcast_send_view,
    committee_broadcast_test_view,
    committee_broadcasts_view,
    committee_document_delete_view,
    committee_documents_view,
    committee_emergency_roster,
    committee_event_delete_view,
    committee_event_edit_view,
    committee_financials_delete_view,
    committee_financials_edit_view,
    committee_financials_view,
    committee_hub,
    committee_inbox_bulk_view,
    committee_invitation_resend_view,
    committee_inbox_toggle_view,
    committee_inbox_view,
    committee_member_edit_view,
    committee_members_view,
    committee_poll_edit_view,
    committee_poll_manage_view,
    committee_poll_toggle_view,
    committee_project_edit_view,
    committee_projects_view,
    committee_repertoire_detail_view,
    committee_repertoire_view,
    committee_rsvp_report,
    committee_schedule_event,  # <-- ADD THIS IMPORT LINE HERE
    committee_settings_view,
    committee_toggle_exempt_view,
    committee_update_rsvp_override,
    contact_view,
    dashboard_view,
    download_ics,
    events_view,
    home_view,
    hub_tracks_view,
    hub_view,
    login_redirect_router,
    member_poll_respond_view,
    member_polling_view,
    member_repertoire_view,
    project_calendar_ics,
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
    path("members/repertoire/", member_repertoire_view, name="member_repertoire"),
    path("members/polling/", member_polling_view, name="member_polling"),
    path(
        "members/polling/<int:poll_id>/respond/",
        member_poll_respond_view,
        name="member_poll_respond",
    ),
    path("members/hub/<str:voice_part>/<int:project_id>/", hub_view, name="hub"),
    path(
        "members/hub/<str:voice_part>/<int:project_id>/tracks.json",
        hub_tracks_view,
        name="hub_tracks",
    ),
    path("members/settings/", settings_view, name="settings"),
    # --- Committee Area ---
    path("members/committee/", committee_hub, name="committee_hub"),
    path("members/committee/projects/", committee_projects_view, name="committee_projects"),
    path(
        "members/committee/projects/<int:project_id>/edit/",
        committee_project_edit_view,
        name="committee_project_edit",
    ),
    path(
        "members/committee/repertoire/",
        committee_repertoire_view,
        name="committee_repertoire",
    ),
    path(
        "members/committee/repertoire/<int:piece_id>/",
        committee_repertoire_detail_view,
        name="committee_repertoire_detail",
    ),
    path(
        "members/committee/repertoire/assets/<int:asset_id>/delete/",
        committee_asset_delete_view,
        name="committee_asset_delete",
    ),
    path("members/committee/polling/", committee_poll_manage_view, name="committee_polling"),
    path(
        "members/committee/polling/<int:poll_id>/edit/",
        committee_poll_edit_view,
        name="committee_poll_edit",
    ),
    path(
        "members/committee/polling/<int:poll_id>/toggle/",
        committee_poll_toggle_view,
        name="committee_poll_toggle",
    ),
    path("members/committee/rsvps/", committee_rsvp_report, name="committee_rsvps"),
    path("members/committee/settings/", committee_settings_view, name="committee_settings"),
    path("members/committee/members/", committee_members_view, name="committee_members"),
    path(
        "members/committee/members/<int:user_id>/",
        committee_member_edit_view,
        name="committee_member_edit",
    ),
    path(
        "members/committee/members/invitations/<int:invitation_id>/resend/",
        committee_invitation_resend_view,
        name="committee_invitation_resend",
    ),
    path("members/committee/inbox/", committee_inbox_view, name="committee_inbox"),
    path("members/committee/inbox/bulk/", committee_inbox_bulk_view, name="committee_inbox_bulk"),
    path(
        "members/committee/inbox/<str:kind>/<int:item_id>/toggle/",
        committee_inbox_toggle_view,
        name="committee_inbox_toggle",
    ),
    path(
        "members/committee/broadcast/", committee_broadcast, name="committee_broadcast"
    ),
    path("members/committee/broadcasts/", committee_broadcasts_view, name="committee_broadcasts"),
    path(
        "members/committee/broadcast/<int:broadcast_id>/",
        committee_broadcast_preview_view,
        name="committee_broadcast_preview",
    ),
    path(
        "members/committee/broadcast/<int:broadcast_id>/edit/",
        committee_broadcast,
        name="committee_broadcast_edit",
    ),
    path(
        "members/committee/broadcast/<int:broadcast_id>/test/",
        committee_broadcast_test_view,
        name="committee_broadcast_test",
    ),
    path(
        "members/committee/broadcast/<int:broadcast_id>/send/",
        committee_broadcast_send_view,
        name="committee_broadcast_send",
    ),
    path(
        "members/committee/broadcast/<int:broadcast_id>/delete/",
        committee_broadcast_delete_view,
        name="committee_broadcast_delete",
    ),
    path(
        "members/committee/roster/",
        committee_emergency_roster,
        name="committee_emergency",
    ),
    path(
        "members/committee/rsvps/<int:attendance_id>/override/",
        committee_update_rsvp_override,
        name="committee_rsvp_override",
    ),
    # 2. ADD THE ROUTING PATH PATTERN EXACTLY HERE
    path("accounts/profile/", login_redirect_router, name="login_redirect"),
    path(
        "members/committee/schedule/",
        committee_schedule_event,
        name="committee_schedule",
    ),
    path(
        "members/committee/schedule/<int:event_id>/edit/",
        committee_event_edit_view,
        name="committee_event_edit",
    ),
    path(
        "members/committee/schedule/<int:event_id>/delete/",
        committee_event_delete_view,
        name="committee_event_delete",
    ),
    path(
        "members/committee/documents/",
        committee_documents_view,
        name="committee_documents",
    ),
    path(
        "members/committee/documents/<int:document_id>/delete/",
        committee_document_delete_view,
        name="committee_document_delete",
    ),
    path(
        "members/committee/financials/",
        committee_financials_view,
        name="committee_financials",
    ),
    path(
        "members/committee/financials/<int:payment_id>/edit/",
        committee_financials_edit_view,
        name="committee_financials_edit",
    ),
    path(
        "members/committee/financials/<int:payment_id>/delete/",
        committee_financials_delete_view,
        name="committee_financials_delete",
    ),
    path(
        "members/committee/financials/<int:profile_id>/toggle-exempt/",
        committee_toggle_exempt_view,
        name="committee_toggle_exempt",
    ),
    # --- Action Handlers ---
    path("rsvp/<int:attendance_id>/", update_rsvp_view, name="update_rsvp"),
    path("event/<int:event_id>/calendar/", download_ics, name="download_ics"),
    path(
        "members/project/<int:project_id>/calendar.ics",
        project_calendar_ics,
        name="project_calendar_ics",
    ),
    # --- Utilities ---
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/images/favicon-clent.png", permanent=True),
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

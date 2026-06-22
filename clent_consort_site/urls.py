"""
URL configuration for clent_consort_site project.
"""

from django import views
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

# Explicitly import all custom view functions
from choir.views import (
    about_view,
    contact_view,
    dashboard_view,
    events_view,
    giftaid_view,
    home_view,
    hub_view,
    settings_view,
)

urlpatterns = [
    # --- Django Admin ---
    path("admin/", admin.site.urls),
    # --- The Allauth Security Doorman ---
    # This automatically handles login, logout, password resets, and email verification
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
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/images/favicon.ico", permanent=True),
    ),
    path("rsvp/<int:attendance_id>/", views.update_rsvp_view, name="update_rsvp"),
]

handler404 = "choir.views.custom_404"

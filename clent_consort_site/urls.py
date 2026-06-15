"""
URL configuration for clent_consort_site project.
"""

from django.contrib import admin
from django.urls import include, path

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
]

handler404 = "choir.views.custom_404"

"""
URL configuration for clent_consort_site project.
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

# Explicitly import all your custom view functions here
from choir import views
from choir.views import (
    about_view,
    contact_view,
    custom_logout_view,  # <-- 1. Added your custom logout view to the import list
    dashboard_view,
    events_view,
    giftaid_view,
    home_view,
    hub_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    # --- Public Pages ---
    path("about/", about_view, name="about"),
    path("events/", events_view, name="events"),
    path("contact/", contact_view, name="contact"),
    # --- Secure Area ---
    path("members/", dashboard_view, name="members"),
    path("members/giftaid/", giftaid_view, name="giftaid"),
    path("members/hub/<str:voice_part>/", hub_view, name="hub"),
    # --- Auth Paths ---
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="choir/login.html"),
        name="login",
    ),
    # 2. Changed views.custom_logout_view to just custom_logout_view to match your style
    path("logout/", custom_logout_view, name="logout"),
    path("members/settings/", views.settings_view, name="settings"),
]

handler404 = "choir.views.custom_404"

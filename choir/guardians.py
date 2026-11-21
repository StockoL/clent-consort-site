"""
Under-18 singers and their parents or guardians (Build Order Phase 15).

An under-18 singer is a member in their own right, with a User and a
MemberProfile but usually no login, and their parents or guardians are
linked to them through MemberProfile.guardians: the people the choir
contacts about them. This module makes the child's record and splits an
account where a parent has been standing in for their child.
"""

import secrets

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Attendance, AvailabilityResponse, SubscriptionPayment

# The child's own details, copied from the parent's profile on a split.
# Their singing history moves with them (split_parent_record).
CHILD_FIELDS = [
    "voice_part",
    "is_exempt_from_subs",
    "consent_audio_video",
    "consent_photography",
    "medical_accessibility_notes",
    "emergency_contact_name",
    "emergency_contact_relation",
    "emergency_contact_phone",
]


def unique_username(first_name, last_name):
    """A username nobody has, from the name ("alexsmith-3f9a"). Children
    without a login never use it; Django just needs one."""
    base = slugify(f"{first_name}{last_name}")[:120] or "singer"
    while True:
        username = f"{base}-{secrets.token_hex(2)}"
        if not User.objects.filter(username=username).exists():
            return username


def create_child(first_name, last_name, voice_part, email=""):
    """A new under-18 singer with no login: an unusable password and,
    unless they have one of their own, no email address. Their profile
    (made by the post_save signal, as a singer, with PENDING RSVPs for
    upcoming events) is marked under 18 with the voice part."""
    user = User(username=unique_username(first_name, last_name), first_name=first_name, last_name=last_name, email=email)
    user.set_unusable_password()
    user.save()
    profile = user.profile
    profile.voice_part = voice_part or None
    profile.is_singer = True
    profile.is_under_18 = True
    profile.save(update_fields=["voice_part", "is_singer", "is_under_18"])
    return user


def make_guardian(parent, child_profile):
    """Links parent to child_profile as a parent or guardian."""
    child_profile.guardians.add(parent)


def can_split(user):
    """Why user's record can't be split into parent and child, or None if
    it can: it must be a singer's, and not already a parent's."""
    profile = getattr(user, "profile", None)
    if profile is None or not profile.is_singer:
        return "Only a singer's record can be split."
    if user.guarded_profiles.exists():
        return "This member is already linked as a parent or guardian, so their record isn't standing in for a child."
    if not user.has_usable_password():
        return "This member has no login of their own, so they can't be a parent standing in for a child."
    return None


@transaction.atomic
def split_parent_record(parent, first_name, last_name):
    """Splits an account where a parent has signed up for their child:
    a new record for the child takes the voice part, singer and under-18
    flags, subscription exemption, consents, medical notes and emergency
    contact, and the singing history (RSVPs, poll answers and payments).
    The parent keeps their login, email and broadcast history, stops
    being a singer and is linked to the child as guardian. All or
    nothing. Returns the child's User."""
    reason = can_split(parent)
    if reason:
        raise ValueError(reason)

    old = parent.profile
    child = create_child(first_name, last_name, old.voice_part)
    profile = child.profile
    for field in CHILD_FIELDS:
        setattr(profile, field, getattr(old, field))
    profile.save(update_fields=CHILD_FIELDS)

    # The child's new PENDING RSVPs make way for the parent's real ones
    Attendance.objects.filter(user=child).delete()
    Attendance.objects.filter(user=parent).update(user=child)
    AvailabilityResponse.objects.filter(user=parent).update(user=child)
    SubscriptionPayment.objects.filter(member=old).update(member=profile)

    old.voice_part = None
    old.is_singer = False
    old.is_under_18 = False
    old.is_exempt_from_subs = False
    old.consent_audio_video = False
    old.consent_photography = False
    old.medical_accessibility_notes = ""
    old.emergency_contact_name = ""
    old.emergency_contact_relation = ""
    old.emergency_contact_phone = ""
    old.save()

    make_guardian(parent, profile)
    return child


def children_of(user):
    """The active singers user is a parent or guardian of, by name, with
    their User loaded."""
    from .models import MemberProfile

    return list(
        MemberProfile.objects.filter(guardians=user, user__is_active=True)
        .select_related("user")
        .order_by("user__first_name", "user__last_name")
    )

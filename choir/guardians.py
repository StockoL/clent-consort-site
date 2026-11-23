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


def singer_label(singer):
    """A singer as the committee sees them: "Alex Smith (Alto, under 18)",
    "Ann Alto (Alto)"."""
    profile = getattr(singer, "profile", None)
    details = [profile.get_voice_part_display()] if profile and profile.voice_part else []
    if profile and profile.is_under_18:
        details.append("under 18")
    name = singer.get_full_name() or singer.username
    return f"{name} ({', '.join(details)})" if details else name


class Contact:
    """One email recipient (user) and the singers they're emailed about:
    themselves, and any children they're a parent or guardian of."""

    def __init__(self, user):
        self.user = user
        self.singers = []

    @property
    def email(self):
        return self.user.email

    @property
    def children(self):
        """The singers this person is contacted about as parent or guardian."""
        return [singer for singer in self.singers if singer.pk != self.user.pk]

    def parent_line(self):
        """The line that opens a parent's copy, or "" for a singer's own."""
        children = self.children
        if not children:
            return ""
        names = [singer_label(child) for child in children]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        return f"You're receiving this as parent or guardian of {joined}."

    def regarding(self):
        """Who the email was about, for the delivery record (300 characters)."""
        return "; ".join(singer_label(singer) for singer in self.singers)[:300]


def contacts_for(singers):
    """
    Who to email about these singers (Build Order Phase 15c): an adult
    singer themselves; an under-18 singer's active parents or guardians
    with an email address, and the singer too if they have one. Nobody is
    emailed twice: a parent of two children gets one copy, about both.

    Returns (contacts, unreachable): Contacts in name order, and the
    singers nobody can be emailed about, rather than dropping them
    silently. Prefetch profile__guardians on the singers for speed.
    """
    contacts = {}
    unreachable = []
    for singer in singers:
        profile = singer.profile
        targets = []
        if profile.is_under_18:
            targets = [g for g in profile.guardians.all() if g.is_active and g.email]
        if singer.email:
            targets.append(singer)
        if not targets:
            unreachable.append(singer)
            continue
        for user in targets:
            contact = contacts.setdefault(user.email.lower(), Contact(user))
            if singer not in contact.singers:
                contact.singers.append(singer)
    ordered = sorted(contacts.values(), key=lambda c: ((c.user.first_name or "").lower(), (c.user.last_name or "").lower(), c.email))
    return ordered, unreachable


def guardian_contacts(singer):
    """An under-18 singer's parents or guardians, for the committee's
    reports: [(User, phone)], active ones only. Empty for an adult."""
    profile = singer.profile
    if not profile.is_under_18:
        return []
    return [(g, getattr(getattr(g, "profile", None), "phone_number", "")) for g in profile.guardians.all() if g.is_active]

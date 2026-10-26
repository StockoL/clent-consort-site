"""
Who counts as committee, and who counts as a singer. Views, templates (via
choir.context_processors) and signals all ask these two questions, so the
answers live here.
"""

# The auth Group whose members get the committee tools. Created, with every
# existing staff user added to it, by migration 0024_committee_group.
COMMITTEE_GROUP = "Committee"


def is_committee(user):
    """
    Committee access: active, and a superuser or in the Committee group.

    Gates the genuinely sensitive committee views (financials, emergency
    roster, broadcast, scheduling, RSVP overrides). committee_hub and
    committee_documents_view are deliberately NOT gated by this - see the
    comment on those views.

    Transition (Build Order Phase 5): is_staff still counts too, for one
    release, so nobody is locked out if the migration that put every staff
    user into the group missed someone. Build Order Phase 11 removes it.
    """
    if not (user.is_authenticated and user.is_active):
        return False
    return (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name=COMMITTEE_GROUP).exists()
    )


def is_singer(user):
    """
    On the singing roster: gets RSVPs for events, appears in the ledger,
    RSVP report, Duty of Care roster, broadcasts and poll reminders.
    Someone with a login who doesn't sing (an accompanist, an
    administrator) is a non-singer: they can still log in and use the
    vault, and the committee tools if they're committee.
    """
    profile = getattr(user, "profile", None)
    return profile is not None and profile.is_singer

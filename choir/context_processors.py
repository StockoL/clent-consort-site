from django.utils.functional import SimpleLazyObject

from .models import AuditionApplication, ChoirSettings, Enquiry
from .permissions import is_committee


def choir_context(request):
    """
    Template context every page can use:
      - choir_settings: the ChoirSettings row (footer social links, term,
        subscription details). Lazy, so pages that never touch it don't
        query for it.
      - is_committee: whether the user gets the committee tools (see
        choir.permissions.is_committee). Templates use this, never
        user.is_staff.
      - inbox_unhandled_count: unhandled enquiries plus audition
        applications, for the badge on the committee Inbox nav item.
        Only computed for committee users, and only when a template uses it.
    """
    context = {"choir_settings": SimpleLazyObject(ChoirSettings.load)}

    user = getattr(request, "user", None)
    committee = user is not None and is_committee(user)
    context["is_committee"] = committee
    if committee:
        context["inbox_unhandled_count"] = SimpleLazyObject(
            lambda: Enquiry.objects.filter(handled=False).count()
            + AuditionApplication.objects.filter(handled=False).count()
        )

    return context

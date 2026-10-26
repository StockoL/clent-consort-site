from django.utils.functional import SimpleLazyObject

from .models import AuditionApplication, ChoirSettings, Enquiry


def choir_context(request):
    """
    Template context every page can use:
      - choir_settings: the ChoirSettings row (footer social links, term,
        subscription details). Lazy, so pages that never touch it don't
        query for it.
      - inbox_unhandled_count: unhandled enquiries plus audition
        applications, for the badge on the committee Inbox nav item.
        Only computed for committee users, and only when a template uses it.
    """
    context = {"choir_settings": SimpleLazyObject(ChoirSettings.load)}

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff:
        context["inbox_unhandled_count"] = SimpleLazyObject(
            lambda: Enquiry.objects.filter(handled=False).count()
            + AuditionApplication.objects.filter(handled=False).count()
        )

    return context

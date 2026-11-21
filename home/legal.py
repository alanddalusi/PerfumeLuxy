"""Legal pages are only available when the owner's real data is configured (see settings.LEGAL_OWNER)."""

from django.conf import settings


def legal_owner():
    return getattr(settings, "LEGAL_OWNER", {}) or {}


def legal_ready():
    owner = legal_owner()
    return all(owner.get(field) for field in getattr(settings, "LEGAL_REQUIRED_FIELDS", ()))


def legal_context(request):
    return {"legal_pages_ready": legal_ready()}

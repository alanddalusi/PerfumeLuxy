"""Legal pages are only available when the owner's real data is configured (see settings.LEGAL_OWNER)."""

from django.conf import settings


def legal_owner():
    return getattr(settings, "LEGAL_OWNER", {}) or {}


def legal_ready():
    owner = legal_owner()
    return all(owner.get(field) for field in getattr(settings, "LEGAL_REQUIRED_FIELDS", ()))


def shop_policy():
    return getattr(settings, "SHOP_POLICY", {}) or {}


def shop_pages_ready():
    policy = shop_policy()
    days = policy.get("return_days", "")
    return (legal_ready() and bool(policy.get("supplier_authorized"))
            and all(policy.get(field) for field in getattr(settings, "SHOP_POLICY_REQUIRED", ()))
            and days.isdigit() and int(days) >= 14)


def legal_context(request):
    return {"legal_pages_ready": legal_ready(), "shop_pages_ready": shop_pages_ready()}

from functools import wraps

from django.conf import settings
from django.core.exceptions import PermissionDenied


def sales_enabled():
    return settings.STORE_MODE == "live"


def store_mode_context(request):
    return {"store_prelaunch": not sales_enabled()}


def require_live_store(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not sales_enabled():
            raise PermissionDenied("La tienda está en preparación.")
        return view(request, *args, **kwargs)

    return wrapped


class CommercialAdminMixin:
    """Allow authorized staff to read commercial records during prelaunch."""

    def has_add_permission(self, request):
        return sales_enabled() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return sales_enabled() and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return sales_enabled() and super().has_delete_permission(request, obj)

    def get_actions(self, request):
        return super().get_actions(request) if sales_enabled() else {}

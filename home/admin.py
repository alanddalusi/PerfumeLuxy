from django.contrib import admin
from .models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "consent_version", "consent_requested_at", "confirmed_at", "withdrawn_at")
    fields = ("email", "consent_version", "subscribed_date", "consent_requested_at", "confirmed_at", "withdrawn_at")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    ordering = ("subscribed_date",)

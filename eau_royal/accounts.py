from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class MailAwareAccountAdapter(DefaultAccountAdapter):
    """Close sign-up while verification e-mails cannot be delivered (prelaunch without SMTP)."""

    def is_open_for_signup(self, request):
        return settings.ACCOUNT_SIGNUPS_OPEN and super().is_open_for_signup(request)

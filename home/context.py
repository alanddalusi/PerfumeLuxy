from django.conf import settings


def mail_context(request):
    return {
        "notice_signups_open": settings.NOTICE_SIGNUPS_OPEN,
        "account_signups_open": settings.ACCOUNT_SIGNUPS_OPEN,
    }

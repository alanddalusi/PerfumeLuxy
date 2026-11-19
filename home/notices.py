"""Opt-in lifecycle for launch subscriptions and individual product notices."""

import hashlib
from datetime import timedelta
from secrets import token_urlsafe

from django.conf import settings
from django.core import signing
from django.core.mail import get_connection, EmailMessage
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import NoticeRateLimit


CONFIRMATION_TTL = timedelta(hours=24)
RESEND_DELAY = timedelta(minutes=10)
AVAILABILITY_CONSENT_VERSION = "availability-email-v1"
SIGNER = signing.Signer(salt="perfumeria-notice-withdrawal-v1")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def rate_allowed(request):
    # Only use the peer address supplied by the server.
    address = request.META.get("REMOTE_ADDR", "unknown")
    key = salted_hmac("perfumeria-notice-rate", address, algorithm="sha256").hexdigest()
    hour = int(timezone.now().timestamp() // 3600)
    limit, _ = NoticeRateLimit.objects.get_or_create(key=key, hour=hour)
    return bool(NoticeRateLimit.objects.filter(pk=limit.pk, count__lt=10).update(count=F("count") + 1))


def unsubscribe_token(notice, kind):
    return SIGNER.sign_object({"id": notice.pk, "kind": kind, "nonce": notice.unsubscribe_nonce})


def send_confirmation(email, kind, product_name, confirm_url, withdrawal_url):
    backend = settings.EMAIL_BACKEND if settings.INTEREST_EMAIL_DELIVERY else settings.INTEREST_PREVIEW_BACKEND
    connection = get_connection(backend=backend)
    body = render_to_string("home/email/confirm_notice.txt", {
        "kind": kind, "product_name": product_name,
        "confirm_url": confirm_url, "withdrawal_url": withdrawal_url,
    })
    EmailMessage(
        subject="Confirma tu aviso · Perfumería El Buen Olor", body=body,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[email], connection=connection,
    ).send()


@transaction.atomic
def request_confirmation(request, notice, kind, *, email, version, product_name=""):
    model = type(notice)
    notice = model.objects.select_for_update().get(pk=notice.pk)
    now = timezone.now()
    active = notice.confirmed_at and not notice.withdrawn_at and notice.email == email and notice.consent_version == version
    recent = notice.consent_requested_at and now - notice.consent_requested_at < RESEND_DELAY
    if active or recent:
        return
    token = token_urlsafe(32)
    notice.email = email
    notice.consent_version = version
    notice.consent_requested_at = now
    notice.confirmed_at = None
    notice.withdrawn_at = None
    notice.confirmation_digest = digest(token)
    notice.confirmation_expires_at = now + CONFIRMATION_TTL
    notice.unsubscribe_nonce = token_urlsafe(32)
    notice.save(update_fields=[
        "email", "consent_version", "consent_requested_at", "confirmed_at", "withdrawn_at",
        "confirmation_digest", "confirmation_expires_at", "unsubscribe_nonce",
    ])
    confirm_url = request.build_absolute_uri(reverse("home:notice_confirm", args=[kind, token]))
    withdrawal_url = request.build_absolute_uri(reverse("home:notice_unsubscribe", args=[kind, unsubscribe_token(notice, kind)]))
    transaction.on_commit(lambda: send_confirmation(email, kind, product_name, confirm_url, withdrawal_url), robust=True)


def confirmation_queryset(model, token):
    return model.objects.filter(
        confirmation_digest=digest(token), confirmation_expires_at__gt=timezone.now(),
        confirmed_at__isnull=True, withdrawn_at__isnull=True,
    )


def withdrawal_queryset(model, kind, token):
    try:
        payload = SIGNER.unsign_object(token)
    except signing.BadSignature:
        return model.objects.none()
    if payload["kind"] != kind:
        return model.objects.none()
    return model.objects.filter(
        pk=payload["id"], unsubscribe_nonce=payload["nonce"], withdrawn_at__isnull=True,
    )

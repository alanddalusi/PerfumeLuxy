from datetime import timedelta
from urllib.parse import urlsplit

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from products.models import Product, StockAlert
from .models import Subscriber


@override_settings(
    STORE_MODE="prelaunch", INTEREST_EMAIL_DELIVERY=False,
    INTEREST_PREVIEW_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class NoticeTests(TestCase):
    def submit_launch(self, client, email="notice@example.test", **headers):
        with self.captureOnCommitCallbacks(execute=True):
            return client.post(reverse("home:index"), {"email": email, "consent": "on"}, **headers)

    def links(self):
        message = mail.outbox[-1]
        paths = [urlsplit(line).path for line in message.body.splitlines() if line.startswith("http")]
        self.assertEqual(len(paths), 2)
        self.assertNotIn(message.to[0], "".join(paths))
        return paths

    def test_launch_link_is_csrf_protected_single_use_and_withdrawal_is_independent(self):
        client = Client(enforce_csrf_checks=True)
        home = reverse("home:index")
        client.get(home)
        headers = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
        self.assertEqual(client.post(home, {"email": "notice@example.test"}, **headers).status_code, 200)
        self.assertFalse(Subscriber.objects.exists())
        self.assertRedirects(self.submit_launch(client, **headers), home)
        confirmation, withdrawal = self.links()
        notice = Subscriber.objects.get()
        self.assertIsNone(notice.confirmed_at)
        self.assertEqual(notice.consent_version, "launch-email-v2")
        response = client.get(confirmation)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        notice.refresh_from_db()
        self.assertIsNone(notice.confirmed_at)
        self.assertEqual(client.post(confirmation).status_code, 403)
        self.assertEqual(client.post(confirmation, **headers).status_code, 200)
        self.assertEqual(client.post(confirmation, **headers).status_code, 410)
        self.assertEqual(len(mail.outbox), 1)
        self.submit_launch(client, "NOTICE@example.test", **headers)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Subscriber.objects.count(), 1)

        self.assertEqual(client.get(withdrawal).status_code, 200)
        notice.refresh_from_db()
        self.assertIsNone(notice.withdrawn_at)
        self.assertEqual(client.post(withdrawal, **headers).status_code, 200)
        self.assertEqual(client.post(withdrawal, **headers).status_code, 410)
        notice.refresh_from_db()
        self.assertIsNotNone(notice.withdrawn_at)

    def test_expired_and_rotated_confirmation_tokens_cannot_be_used(self):
        self.submit_launch(self.client)
        old_confirmation, old_withdrawal = self.links()
        Subscriber.objects.update(
            confirmation_expires_at=timezone.now() - timedelta(seconds=1),
            consent_requested_at=timezone.now() - timedelta(minutes=11),
        )
        self.assertEqual(self.client.post(old_confirmation).status_code, 410)
        self.submit_launch(self.client)
        new_confirmation, _ = self.links()
        self.assertNotEqual(new_confirmation, old_confirmation)
        self.assertEqual(self.client.post(old_withdrawal).status_code, 410)
        self.assertEqual(self.client.post(new_confirmation).status_code, 200)
        self.assertEqual(Subscriber.objects.count(), 1)

    def test_request_rate_limit_ignores_forwarded_ip_and_pending_mail_is_deduplicated(self):
        self.submit_launch(self.client)
        self.submit_launch(self.client)
        self.assertEqual(len(mail.outbox), 1)
        for index in range(8):
            response = self.submit_launch(self.client, f"notice{index}@example.test")
            self.assertEqual(response.status_code, 302)
        response = self.submit_launch(self.client, "excess@example.test", HTTP_X_FORWARDED_FOR="192.0.2.42")
        self.assertEqual(response.status_code, 429)
        self.assertFalse(Subscriber.objects.filter(email="excess@example.test").exists())

    def test_product_confirmation_and_withdrawal_do_not_change_launch_subscription(self):
        user = get_user_model().objects.create_user(username="watcher", email="notice@example.test")
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        product = Product.objects.create(name="Prueba de disponibilidad", publication_status=Product.Publication.APPROVED)
        self.submit_launch(self.client)
        launch_link, _ = self.links()
        self.assertEqual(self.client.post(launch_link).status_code, 200)

        self.client.force_login(user)
        path = reverse("products:notify_when_available", args=[product.pk])
        self.client.post(path)
        self.assertFalse(StockAlert.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.assertRedirects(self.client.post(path, {"consent": "on"}), product.get_absolute_url())
        confirm, withdrawal = self.links()
        self.assertIn("/disponibilidad/", confirm)
        self.assertEqual(self.client.post(confirm.replace("/disponibilidad/", "/lanzamiento/")).status_code, 410)
        self.assertEqual(self.client.post(confirm).status_code, 200)
        self.assertIsNotNone(StockAlert.objects.get().confirmed_at)
        self.assertEqual(self.client.post(withdrawal).status_code, 200)
        self.assertIsNotNone(StockAlert.objects.get().withdrawn_at)
        self.assertIsNone(Subscriber.objects.get().withdrawn_at)

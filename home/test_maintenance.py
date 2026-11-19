from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from products.models import Product, StockAlert

from .models import NoticeRateLimit, Subscriber


class PurgeNoticeDataTests(TestCase):
    def setUp(self):
        now = timezone.now()
        hour = int(now.timestamp() // 3600)
        NoticeRateLimit.objects.create(key="old", hour=hour - 72, count=3)
        NoticeRateLimit.objects.create(key="recent", hour=hour, count=1)
        expired = now - timedelta(days=40)
        self.stale = Subscriber.objects.create(email="stale@example.test", confirmation_expires_at=expired)
        self.confirmed = Subscriber.objects.create(
            email="ok@example.test", confirmation_expires_at=expired, confirmed_at=expired)
        self.withdrawn = Subscriber.objects.create(
            email="out@example.test", confirmation_expires_at=expired, withdrawn_at=expired)
        self.legacy = Subscriber.objects.create(email="legacy@example.test")
        self.fresh = Subscriber.objects.create(email="new@example.test", confirmation_expires_at=now + timedelta(hours=2))
        user = get_user_model().objects.create_user(username="cliente", email="c@example.test")
        product = Product.objects.create(name="Perfume", description="x")
        self.alert = StockAlert.objects.create(user=user, product=product, email=user.email, confirmation_expires_at=expired)

    def run_purge(self, *args):
        output = StringIO()
        call_command("purge_notice_data", *args, stdout=output)
        return output.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self.run_purge()
        self.assertIn("1 rate-limit counters would be deleted", output)
        self.assertIn("1 launch requests would be deleted", output)
        self.assertIn("1 availability requests would be deleted", output)
        self.assertEqual(NoticeRateLimit.objects.count(), 2)
        self.assertEqual(Subscriber.objects.count(), 5)

    def test_apply_removes_only_stale_counters_and_never_confirmed_requests(self):
        self.run_purge("--apply")
        self.assertEqual(list(NoticeRateLimit.objects.values_list("key", flat=True)), ["recent"])
        remaining = set(Subscriber.objects.values_list("email", flat=True))
        self.assertEqual(remaining, {"ok@example.test", "out@example.test", "legacy@example.test", "new@example.test"})
        self.assertFalse(StockAlert.objects.exists())

    def test_rejects_unsafe_retention(self):
        with self.assertRaises(CommandError):
            self.run_purge("--counter-hours", "0")

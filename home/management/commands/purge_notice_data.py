from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from home.models import NoticeRateLimit, Subscriber
from products.models import StockAlert


class Command(BaseCommand):
    help = (
        "Remove expired anti-abuse counters and never-confirmed notice requests. "
        "Dry run unless --apply is given. Retention periods must match the privacy policy."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--counter-hours", type=int, default=48,
                            help="Keep rate-limit counters for this many hours (default 48).")
        parser.add_argument("--unconfirmed-days", type=int, default=30,
                            help="Delete requests whose confirmation link expired this many days ago (default 30).")

    def handle(self, *args, apply=False, counter_hours=48, unconfirmed_days=30, **options):
        if counter_hours < 2 or unconfirmed_days < 1:
            raise CommandError("Retention must be at least 2 hours for counters and 1 day for requests.")
        now = timezone.now()
        current_hour = int(now.timestamp() // 3600)
        counters = NoticeRateLimit.objects.filter(hour__lt=current_hour - counter_hours)
        cutoff = now - timedelta(days=unconfirmed_days)
        # Legacy rows without an expiry date are never touched by this command.
        pending = {
            "launch requests": Subscriber.objects.filter(
                confirmed_at__isnull=True, withdrawn_at__isnull=True, confirmation_expires_at__lt=cutoff),
            "availability requests": StockAlert.objects.filter(
                confirmed_at__isnull=True, withdrawn_at__isnull=True, confirmation_expires_at__lt=cutoff),
        }
        counts = {"rate-limit counters": counters.count(), **{name: qs.count() for name, qs in pending.items()}}
        if apply:
            with transaction.atomic():
                counters.delete()
                for queryset in pending.values():
                    queryset.delete()
        verb = "deleted" if apply else "would be deleted"
        for name, total in counts.items():
            self.stdout.write(f"{total} {name} {verb}")

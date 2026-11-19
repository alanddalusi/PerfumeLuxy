from django.db import models


class NoticeConsent(models.Model):
    confirmation_digest = models.CharField(max_length=64, blank=True, default="", db_index=True)
    confirmation_expires_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    consent_requested_at = models.DateTimeField(null=True, blank=True)
    unsubscribe_nonce = models.CharField(max_length=64, blank=True, default="")
    consent_version = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        abstract = True


class NoticeRateLimit(models.Model):
    key = models.CharField(max_length=64)
    hour = models.PositiveIntegerField(db_index=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("key", "hour"), name="notice_hourly_rate_unique")]


class Subscriber(NoticeConsent):
    email = models.EmailField(max_length=40, null=True)
    subscribed_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("email", "consent_version"),
                condition=~models.Q(consent_version=""),
                name="home_subscriber_unique_consent",
            ),
        ]

    def __str__(self):
        return self.email

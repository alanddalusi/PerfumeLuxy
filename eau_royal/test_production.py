import io
import logging
import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from home.models import Subscriber

from .logging_filters import RedactTokensFilter, redact
from .proxy import TrustedProxyMiddleware


def load_production_settings(**overrides):
    env = {
        "DJANGO_ENV": "production",
        "SECRET_KEY": get_random_secret_key(),
        "DJANGO_ALLOWED_HOSTS": "shop.example.test",
        "DATABASE_URL": "postgresql://store:unused@db.example.test:5432/perfumeria",
    }
    with patch.dict(os.environ, {**env, **overrides}, clear=True):
        return runpy.run_path(str(Path(settings.BASE_DIR) / "eau_royal" / "settings.py"))


class ProductionSettingsTests(SimpleTestCase):
    def test_mail_is_discarded_in_production_unless_smtp_is_explicit(self):
        configured = load_production_settings(INTEREST_EMAIL_DELIVERY="1")
        self.assertEqual(configured["EMAIL_BACKEND"], "django.core.mail.backends.dummy.EmailBackend")
        self.assertFalse(configured["INTEREST_EMAIL_DELIVERY"])
        self.assertEqual(configured["STORE_MODE"], "prelaunch")

        with self.assertRaises(ImproperlyConfigured):
            load_production_settings(EMAIL_DELIVERY="smtp")
        with self.assertRaises(ImproperlyConfigured):
            load_production_settings(EMAIL_DELIVERY="sendmail")
        smtp = load_production_settings(
            EMAIL_DELIVERY="smtp", EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="avisos@example.test",
        )
        self.assertEqual(smtp["EMAIL_BACKEND"], "django.core.mail.backends.smtp.EmailBackend")
        self.assertTrue(smtp["EMAIL_USE_TLS"])
        self.assertFalse(smtp["INTEREST_EMAIL_DELIVERY"])

    def test_development_never_uses_smtp(self):
        with patch.dict(os.environ, {"DJANGO_ENV": "development", "EMAIL_DELIVERY": "smtp"}, clear=True):
            configured = runpy.run_path(str(Path(settings.BASE_DIR) / "eau_royal" / "settings.py"))
        self.assertEqual(configured["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend")
        self.assertFalse(configured["INTEREST_EMAIL_DELIVERY"])

    def test_plaintext_database_only_for_listed_internal_service_names(self):
        internal = "postgresql://store:unused@db:5432/perfumeria?sslmode=disable"
        configured = load_production_settings(DATABASE_URL=internal, DJANGO_DB_PLAINTEXT_HOSTS="db")
        self.assertEqual(configured["DATABASES"]["default"]["OPTIONS"]["sslmode"], "disable")
        for overrides in (
            {"DATABASE_URL": internal},
            {"DATABASE_URL": internal.replace("@db:", "@db.example.test:"), "DJANGO_DB_PLAINTEXT_HOSTS": "db.example.test"},
            {"DATABASE_URL": internal.replace("sslmode=disable", "sslmode=prefer"), "DJANGO_DB_PLAINTEXT_HOSTS": "db"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ImproperlyConfigured):
                load_production_settings(**overrides)

    def test_log_filter_is_attached_to_the_console_handler(self):
        configured = load_production_settings()
        self.assertIn("redact_tokens", configured["LOGGING"]["handlers"]["console"]["filters"])
        self.assertIn("eau_royal.proxy.TrustedProxyMiddleware", configured["MIDDLEWARE"][0])
        self.assertEqual(configured["TRUSTED_PROXY_NETWORKS"], [])


class TrustedProxyTests(SimpleTestCase):
    def resolve(self, peer, forwarded=None, networks=("172.30.10.2/32",)):
        request = RequestFactory().get("/", REMOTE_ADDR=peer, **({"HTTP_X_FORWARDED_FOR": forwarded} if forwarded else {}))
        seen = {}

        def view(req):
            seen["addr"] = req.META["REMOTE_ADDR"]
            return HttpResponse()

        with self.settings(TRUSTED_PROXY_NETWORKS=list(networks)):
            TrustedProxyMiddleware(view)(request)
        return seen["addr"]

    def test_only_the_configured_proxy_can_report_the_client_address(self):
        self.assertEqual(self.resolve("172.30.10.2", "198.51.100.7"), "198.51.100.7")
        # Caddy appends the real peer last; anything before it came from the client.
        self.assertEqual(self.resolve("172.30.10.2", "203.0.113.9, 198.51.100.7"), "198.51.100.7")
        self.assertEqual(self.resolve("203.0.113.50", "198.51.100.7"), "203.0.113.50")
        self.assertEqual(self.resolve("172.30.10.2", "not-an-ip"), "172.30.10.2")
        self.assertEqual(self.resolve("172.30.10.2", "198.51.100.7", networks=()), "172.30.10.2")

    def test_invalid_network_configuration_fails_closed(self):
        with self.settings(TRUSTED_PROXY_NETWORKS=["proxy"]), self.assertRaises(ImproperlyConfigured):
            TrustedProxyMiddleware(lambda request: HttpResponse())


@override_settings(
    STORE_MODE="prelaunch", INTEREST_EMAIL_DELIVERY=False, TRUSTED_PROXY_NETWORKS=["172.30.10.2/32"],
    INTEREST_PREVIEW_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ProxiedRateLimitTests(TestCase):
    def test_visitors_behind_the_proxy_have_separate_limits(self):
        def submit(email, client_ip):
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post("/", {"email": email, "consent": "on"},
                                        REMOTE_ADDR="172.30.10.2", HTTP_X_FORWARDED_FOR=client_ip)

        for index in range(10):
            self.assertEqual(submit(f"a{index}@example.test", "198.51.100.1").status_code, 302)
        self.assertEqual(submit("blocked@example.test", "198.51.100.1").status_code, 429)
        # Spoofing an earlier hop does not escape the limit: only the proxy's entry counts.
        self.assertEqual(submit("spoof@example.test", "192.0.2.1, 198.51.100.1").status_code, 429)
        self.assertEqual(submit("other@example.test", "198.51.100.2").status_code, 302)
        self.assertTrue(Subscriber.objects.filter(email="other@example.test").exists())
        self.assertFalse(Subscriber.objects.filter(email__in=["blocked@example.test", "spoof@example.test"]).exists())


class TokenRedactionTests(TestCase):
    def test_tokens_are_removed_from_paths(self):
        for path in (
            "/avisos/lanzamiento/confirmar/abcDEF123_-/",
            "/avisos/disponibilidad/baja/eyJpZCI6MX0:1abc:XYZ/",
            "/accounts/confirm-email/MQ:1tok:sig/",
            "/accounts/password/reset/key/1-set-password/",
        ):
            with self.subTest(path=path):
                self.assertIn("[redacted]", redact(f"Gone: {path}"))
                self.assertNotRegex(redact(path), r"abcDEF|eyJpZ|MQ:1tok|1-set-password")
        self.assertEqual(redact("Not Found: /products/perfume/"), "Not Found: /products/perfume/")

    def test_django_request_warnings_do_not_contain_tokens(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(RedactTokensFilter())
        logger = logging.getLogger("django.request")
        logger.addHandler(handler)
        try:
            response = self.client.post("/avisos/lanzamiento/confirmar/secret-token-value/")
        finally:
            logger.removeHandler(handler)
        self.assertEqual(response.status_code, 410)
        self.assertIn("[redacted]", stream.getvalue())
        self.assertNotIn("secret-token-value", stream.getvalue())


class HealthTests(TestCase):
    def test_health_endpoint_reports_database_state_without_details(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post("/healthz/").status_code, 405)
        with patch("eau_royal.health.connection.cursor", side_effect=RuntimeError("db down")):
            response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("db down", response.content.decode())

    def test_health_endpoint_is_exempt_from_https_redirect_only(self):
        with self.settings(SECURE_SSL_REDIRECT=True):
            self.assertEqual(self.client.get("/healthz/").status_code, 200)
            self.assertEqual(self.client.get("/privacidad/").status_code, 301)


class DeploymentFilesTests(SimpleTestCase):
    root = Path(settings.BASE_DIR)

    def test_compose_keeps_prelaunch_guards_and_private_services(self):
        compose = (self.root / "deploy" / "compose.yaml").read_text(encoding="utf-8")
        db_block = compose.split("\n  db:\n", 1)[1].split("\n  web:\n", 1)[0]
        web_block = compose.split("\n  web:\n", 1)[1].split("\n  caddy:\n", 1)[0]
        self.assertNotIn("ports:", db_block)
        self.assertNotIn("ports:", web_block)
        self.assertIn("internal: true", compose)
        self.assertIn("STORE_MODE: prelaunch", web_block)
        caddy = (self.root / "deploy" / "Caddyfile").read_text(encoding="utf-8")
        self.assertIn("@private path /media/*", caddy)
        self.assertIn("[redacted]", caddy)
        example = (self.root / "deploy" / "env.production.example").read_text(encoding="utf-8")
        for line in ("STORE_MODE=prelaunch", "EMAIL_DELIVERY=disabled", "INTEREST_EMAIL_DELIVERY=0"):
            self.assertIn(line, example.splitlines())
        self.assertNotRegex(example, r"(?m)^STRIPE_")

    def test_docker_context_excludes_secrets_and_private_data(self):
        ignored = (self.root / ".dockerignore").read_text(encoding="utf-8").splitlines()
        for entry in ("env.py", ".env", "*.sqlite3", "media", "catalog_assets", "deploy/.env*", ".git"):
            self.assertIn(entry, ignored)

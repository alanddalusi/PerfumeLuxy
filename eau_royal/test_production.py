import io
import re
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


class MailClosedFormsTests(TestCase):
    """Production without SMTP: no form may promise or collect a confirmation e-mail."""

    def setUp(self):
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model
        from products.models import Brand, Product

        self.user = get_user_model().objects.create_user(username="cliente", email="c@example.test", password="x-Very-long-pass-91")
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        self.product = Product.objects.create(
            name="Perfume publicado", brand=Brand.objects.create(db_name="b", name="Marca"),
            description="x", publication_status=Product.Publication.APPROVED,
        )

    def test_production_flags_follow_real_mail_delivery(self):
        closed = load_production_settings()
        self.assertFalse(closed["NOTICE_SIGNUPS_OPEN"])
        self.assertFalse(closed["ACCOUNT_SIGNUPS_OPEN"])
        smtp = dict(EMAIL_DELIVERY="smtp", EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="a@example.test")
        accounts_only = load_production_settings(**smtp)
        self.assertTrue(accounts_only["ACCOUNT_SIGNUPS_OPEN"])
        self.assertFalse(accounts_only["NOTICE_SIGNUPS_OPEN"])
        self.assertTrue(load_production_settings(**smtp, INTEREST_EMAIL_DELIVERY="1")["NOTICE_SIGNUPS_OPEN"])

    @override_settings(NOTICE_SIGNUPS_OPEN=False, ACCOUNT_SIGNUPS_OPEN=False)
    def test_forms_are_hidden_and_submissions_store_nothing(self):
        from django.core import mail
        from django.urls import reverse
        from products.models import StockAlert

        home = self.client.get("/")
        self.assertNotContains(home, 'name="consent"')
        self.assertContains(home, "Avisos por correo muy pronto")
        self.assertNotContains(home, reverse("account_signup"))
        self.assertRedirects(self.client.post("/", {"email": "x@example.test", "consent": "on"}), "/")
        self.assertFalse(Subscriber.objects.exists())

        self.client.force_login(self.user)
        detail = self.client.get(self.product.get_absolute_url())
        self.assertNotContains(detail, reverse("products:notify_when_available", args=[self.product.pk]))
        self.assertContains(detail, "Aviso de disponibilidad muy pronto")
        self.client.post(reverse("products:notify_when_available", args=[self.product.pk]), {"consent": "on"})
        self.assertFalse(StockAlert.objects.exists())
        self.client.logout()

        self.assertNotContains(self.client.get(reverse("account_login")), reverse("account_reset_password"))
        self.assertNotContains(self.client.get(reverse("account_reset_password")), 'name="email"')
        signup = self.client.post(reverse("account_signup"), {
            "email": "new@example.test", "username": "nuevo", "password1": "x-Very-long-pass-91", "password2": "x-Very-long-pass-91",
        })
        self.assertEqual(signup.status_code, 200)
        self.assertFalse(Subscriber.objects.exists())
        from django.contrib.auth import get_user_model
        self.assertFalse(get_user_model().objects.filter(username="nuevo").exists())
        self.assertEqual(len(mail.outbox), 0)


class SmokeTestFilesTests(SimpleTestCase):
    root = Path(settings.BASE_DIR) / "deploy"

    def test_smoke_run_is_isolated_and_production_defaults_are_kept(self):
        compose = (self.root / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn('"${HTTP_BIND:-80}:80"', compose)
        self.assertIn('"${HTTPS_BIND:-443}:443"', compose)
        web_block = compose.split("\n  web:\n", 1)[1].split("\n  caddy:\n", 1)[0]
        self.assertNotIn("ipv4_address", web_block)  # one-off runs must not collide with web
        smoke = (self.root / "smoke" / "run.sh").read_text(encoding="utf-8")
        self.assertIn('COMPOSE_PROJECT_NAME="perfumeria-smoke"', smoke)
        self.assertIn("HTTP_BIND=127.0.0.1:", smoke)
        self.assertIn("HTTPS_BIND=127.0.0.1:", smoke)
        for line in ("STORE_MODE=prelaunch", "EMAIL_DELIVERY=disabled", "INTEREST_EMAIL_DELIVERY=0"):
            self.assertIn(line, smoke)
        self.assertNotIn("STRIPE_", smoke.split("cat > \"$PERFUMERIA_ENV_FILE\"", 1)[1].split("EOF", 2)[1])

    def test_smoke_run_guards_against_shared_hosts_and_foreign_projects(self):
        smoke = (self.root / "smoke" / "run.sh").read_text(encoding="utf-8")
        self.assertIn("label=com.docker.compose.project=perfumeria", smoke)  # refuses a host with production
        self.assertIn("snap list docker", smoke)
        self.assertIn('[ "$resolved" = "perfumeria-smoke" ]', smoke)
        guard, teardown = smoke.index('[ "$resolved" = "perfumeria-smoke" ]'), smoke.index("down -v --remove-orphans")
        self.assertLess(guard, smoke.index("compose down -v --remove-orphans >/dev/null 2>&1   #"))
        self.assertGreater(teardown, 0)
        for forbidden in ("system prune", "volume rm", "volume prune", "network prune", "docker rm "):
            self.assertNotIn(forbidden, smoke)

    def test_backup_scripts_hold_no_credentials_and_offsite_refuses_private_keys(self):
        for name in ("backup.sh", "restore.sh", "offsite.sh"):
            script = (self.root / "backup" / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertNotRegex(script, r"(?i)(PGPASSWORD|POSTGRES_PASSWORD=|password=)")
                self.assertIn("set -euo pipefail", script)
        self.assertIn("AGE-SECRET-KEY", (self.root / "backup" / "offsite.sh").read_text(encoding="utf-8"))


class SharedVpsTests(SimpleTestCase):
    root = Path(settings.BASE_DIR) / "deploy" / "shared"

    def compose(self):
        import yaml
        return yaml.safe_load((self.root / "compose.yaml").read_text(encoding="utf-8"))

    def test_shared_compose_is_isolated_from_the_forum(self):
        config = self.compose()
        self.assertEqual(config["name"], "perfumeria-production")
        services = config["services"]
        # Service names become DNS aliases on every network: generic names like "web"
        # would collide with the forum's containers on the shared edge network.
        self.assertEqual(set(services), {"perfumeria-db", "perfumeria-web"})
        for name, service in services.items():
            self.assertNotIn("ports", service, name)
            self.assertNotIn("container_name", service, name)
            self.assertIn("mem_limit", service, name)
            self.assertIn("cpus", service, name)
            self.assertIn("pids_limit", service, name)
        self.assertEqual(services["perfumeria-db"]["networks"], ["backend"])
        self.assertEqual(set(services["perfumeria-web"]["networks"]), {"backend", "shared_edge"})
        self.assertTrue(config["networks"]["backend"]["internal"])
        edge = config["networks"]["shared_edge"]
        self.assertTrue(edge["external"])
        self.assertIn("foroia-production_edge", edge["name"])
        self.assertNotIn("caddy", " ".join(services))

    def test_commerce_and_mail_are_pinned_off(self):
        env = self.compose()["services"]["perfumeria-web"]["environment"]
        self.assertEqual(env["STORE_MODE"], "prelaunch")
        self.assertEqual(env["EMAIL_DELIVERY"], "disabled")
        self.assertEqual(env["INTEREST_EMAIL_DELIVERY"], "0")
        for key in ("STRIPE_PUBLIC_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
            self.assertEqual(env[key], "")
        self.assertEqual(env["DJANGO_SERVE_STATIC"], "1")
        self.assertEqual(env["DJANGO_DB_PLAINTEXT_HOSTS"], "perfumeria-db")
        self.assertIn("@perfumeria-db:5432/", env["DATABASE_URL"])
        example = (self.root / "env.production.example").read_text(encoding="utf-8").splitlines()
        self.assertIn("PROXY_SERVICE=", example)
        self.assertNotRegex("\n".join(example), r"(?m)^(STRIPE_|STORE_MODE|EMAIL_DELIVERY)")

    def test_caddy_block_is_delimited_and_targets_the_unique_alias(self):
        block = (self.root / "perfumeria.caddy").read_text(encoding="utf-8")
        lines = block.strip().splitlines()
        self.assertTrue(lines[0].startswith("# >>> BEGIN perfumeria-el-buen-olor"))
        self.assertEqual(lines[-1], "# <<< END perfumeria-el-buen-olor")
        self.assertIn("reverse_proxy perfumeria-web:8000", block)
        self.assertIn("www.perfumeriaelbuenolor.es", block)
        self.assertIn("@perfumeria_private path /media/* /healthz*", block)
        self.assertIn("[redacted]", block)
        # Global options or snippets would leak into the forum's configuration.
        self.assertNotRegex(block, r"(?m)^\{")
        self.assertNotRegex(block, r"(?m)^\(")

    def test_scripts_never_stop_or_remove_forum_resources(self):
        for path in self.root.glob("*.sh"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(script=path.name):
                for forbidden in ("docker stop", "docker restart", "docker rm", "network rm", "volume rm",
                                  "prune", "down -v", "compose down", "caddy stop", "caddy run", 'rm -- "$host_file'):
                    self.assertNotIn(forbidden, text)
                # The forum's Caddyfile only ever receives an append, the saved copy or the
                # same file without our block; never generated content.
                for line in re.findall(r'^.*>\s*"\$host_file".*$', text, flags=re.M):
                    self.assertRegex(line, r'(>> "\$host_file"|cat -- "\$(backup|work/stripped\.Caddyfile)" > "\$host_file")')
        restore = (self.root.parent / "backup" / "restore.sh").read_text(encoding="utf-8")
        self.assertIn('compose stop "$WEB" $PROXY', restore)


class SharedProxySettingsTests(SimpleTestCase):
    def test_whitenoise_only_when_requested(self):
        self.assertNotIn("whitenoise.middleware.WhiteNoiseMiddleware", load_production_settings()["MIDDLEWARE"])
        middleware = load_production_settings(DJANGO_SERVE_STATIC="1")["MIDDLEWARE"]
        security = middleware.index("django.middleware.security.SecurityMiddleware")
        self.assertEqual(middleware[security + 1], "whitenoise.middleware.WhiteNoiseMiddleware")

    def resolve(self, peer, forwarded, addresses):
        from . import proxy

        request = RequestFactory().get("/", REMOTE_ADDR=peer, HTTP_X_FORWARDED_FOR=forwarded)
        seen = {}

        def view(req):
            seen["addr"] = req.META["REMOTE_ADDR"]
            return HttpResponse()

        def getaddrinfo(host, *args, **kwargs):
            if host not in addresses:
                raise OSError("unknown host")
            return [(None, None, None, "", (address, 0)) for address in addresses[host]]

        with self.settings(TRUSTED_PROXY_NETWORKS=[], TRUSTED_PROXY_HOSTS=["foroia-production-caddy-1"]), \
                patch.object(proxy.socket, "getaddrinfo", side_effect=getaddrinfo):
            proxy.TrustedProxyMiddleware(view)(request)
        return seen["addr"]

    def test_proxy_trusted_by_container_name(self):
        forum = {"foroia-production-caddy-1": ["172.18.0.5"]}
        self.assertEqual(self.resolve("172.18.0.5", "198.51.100.7", forum), "198.51.100.7")
        # Another container on the shared network cannot claim a client address.
        self.assertEqual(self.resolve("172.18.0.9", "198.51.100.7", forum), "172.18.0.9")
        # Name not resolvable: nobody is trusted (fail closed).
        self.assertEqual(self.resolve("172.18.0.5", "198.51.100.7", {}), "172.18.0.5")

    def test_invalid_proxy_host_entries_fail_closed(self):
        from . import proxy

        with self.settings(TRUSTED_PROXY_HOSTS=["172.18.0.0/16"]), self.assertRaises(ImproperlyConfigured):
            proxy.TrustedProxyMiddleware(lambda request: HttpResponse())


class SharedVpsAuditAndRehearsalTests(SimpleTestCase):
    root = Path(settings.BASE_DIR) / "deploy" / "shared"

    def test_remote_audit_is_read_only(self):
        text = (self.root / "audit-readonly.sh").read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("docker run", "docker create", "docker rm", "docker stop", "docker restart", "docker kill",
                          "docker cp", "network create", "network connect", "network rm", "volume rm", "volume create", "volume prune", "compose up",
                          "compose down", "caddy reload", "mkdir", "tee ", "mktemp", "rm -", "sed -i", "chmod", "chown"):
            self.assertNotIn(forbidden, code)
        # Output redirections only to /dev/null; results go to stdout.
        for target in re.findall(r"(?<![<>&0-9-])>{1,2}\s*([^\s;|)]+)", code):
            self.assertEqual(target, "/dev/null")
        self.assertNotIn("cat \"$host_file\"", code)  # never prints the forum Caddyfile

    def test_rehearsal_refuses_real_forum_and_real_deployment(self):
        text = (self.root / "rehearsal" / "run.sh").read_text(encoding="utf-8")
        self.assertIn('LABEL="perfumeria.rehearsal"', text)
        self.assertIn("this is not a rehearsal machine", text)
        self.assertIn("never rehearse next to a real deployment", text)
        self.assertIn("NOT removing $SIM_PROJECT", text)
        self.assertIn("local_certs", text)  # no ACME request for the real domain
        guards = text.index("# ------------------------------------------------------------ guards")
        self.assertLess(guards, text.index("sim up -d"))
        self.assertLess(guards, text.index('cat > "$ENV_PATH"'))
        compose = (self.root / "rehearsal" / "foro-compose.yaml").read_text(encoding="utf-8")
        self.assertEqual(compose.count('perfumeria.rehearsal: "true"'), 8)  # 3 services, 2 networks, 3 volumes
        self.assertIn("127.0.0.1:${SIM_HTTPS_PORT", compose)

    def test_validation_container_never_duplicates_the_caddyfile_mount(self):
        lib = (self.root / "lib.sh").read_text(encoding="utf-8")
        self.assertIn('[ "$destination" != "$inside" ]', lib)
        self.assertIn("--network none", lib)
        self.assertIn("readonly", lib)

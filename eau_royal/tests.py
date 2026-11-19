import json
import os
import runpy
from builtins import __import__ as import_module
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .seo import json_ld


class DeploymentSettingsTests(TestCase):
    def test_legacy_development_settings_cannot_override_explicit_database(self):
        def legacy_import(name, *args, **kwargs):
            if name == "env":
                os.environ.pop("DATABASE_URL", None)
                os.environ["SECRET_KEY"] = "local-only-test"
                return None
            return import_module(name, *args, **kwargs)

        env = {"DJANGO_ENV": "development", "DATABASE_URL": "postgresql://local/db"}
        with patch.dict(os.environ, env, clear=True), patch("builtins.__import__", side_effect=legacy_import), patch("pathlib.Path.is_file", return_value=True):
            configured = runpy.run_path(str(Path(settings.BASE_DIR) / "eau_royal" / "settings.py"))
            self.assertEqual(configured["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
            self.assertEqual(os.environ["DATABASE_URL"], env["DATABASE_URL"])
            self.assertEqual(configured["SECRET_KEY"], "local-only-test")

    def load_settings(self, **overrides):
        env = {
            "DJANGO_ENV": "production",
            "SECRET_KEY": get_random_secret_key(),
            "DJANGO_ALLOWED_HOSTS": "shop.example.test",
            "DATABASE_URL": "postgresql://store:unused@db.example.test:5432/perfumeria",
        }
        with patch.dict(os.environ, {**env, **overrides}, clear=True):
            return runpy.run_path(str(Path(settings.BASE_DIR) / "eau_royal" / "settings.py"))

    def test_production_settings_validate_host_database_and_secret(self):
        for overrides in (
            {"SECRET_KEY": ""},
            {"DJANGO_ALLOWED_HOSTS": "*"},
            {"DATABASE_URL": ""},
            {"DATABASE_URL": "sqlite:///local.sqlite3"},
            {"DATABASE_URL": "postgresql://db.example.test/perfumeria?sslmode=disable"},
        ):
            with self.subTest(setting=next(iter(overrides))):
                with self.assertRaises(ImproperlyConfigured):
                    self.load_settings(**overrides)

    def test_https_headers_and_cookies_under_production_settings(self):
        configured = self.load_settings()
        self.assertFalse(configured["DEBUG"])
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", configured)
        self.assertEqual(configured["DATABASES"]["default"]["OPTIONS"]["sslmode"], "require")
        self.assertEqual(configured["STORE_MODE"], "prelaunch")
        self.assertEqual(
            self.load_settings(DJANGO_TRUST_HTTPS_PROXY="1")["SECURE_PROXY_SSL_HEADER"],
            ("HTTP_X_FORWARDED_PROTO", "https"),
        )

        security_settings = {
            key: value for key, value in configured.items()
            if key.startswith(("SECURE_", "SESSION_COOKIE_", "CSRF_COOKIE_"))
            or key in {"DEBUG", "ALLOWED_HOSTS", "X_FRAME_OPTIONS"}
        }
        with self.settings(**security_settings):
            client = Client(HTTP_HOST="shop.example.test")
            url = reverse("account_login")
            response = client.get(url)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response["Location"], "https://shop.example.test" + url)
            response = client.get(url, secure=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("max-age=", response["Strict-Transport-Security"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response["X-Frame-Options"], "DENY")
            self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
            self.assertTrue(response.cookies[settings.CSRF_COOKIE_NAME]["secure"])
            self.assertTrue(settings.SESSION_COOKIE_SECURE)
            self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_json_ld_round_trips_script_sensitive_text(self):
        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.start_tags = []

            def handle_starttag(self, tag, attrs):
                self.start_tags.append((tag, attrs))

        document = {"name": 'Ámbar & Té "especial" </script><span>'}
        html = json_ld(document)
        parser = Scripts()
        parser.feed(html)
        self.assertEqual(parser.start_tags, [("script", [("type", "application/ld+json")])])
        self.assertEqual(json.loads(html.split(">", 1)[1].rsplit("<", 1)[0]), document)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountCompatibilityTests(TestCase):
    def test_existing_verified_account_logs_in_with_username_and_email(self):
        password = "unrelated-demo-passphrase-83"
        user = get_user_model().objects.create_user(
            username="legacy-user", email="legacy@example.test", password=password,
        )
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        login_url = reverse("account_login")
        for identity in (user.username, user.email):
            with self.subTest(identity=identity):
                client = Client(enforce_csrf_checks=True)
                client.get(login_url)
                headers = {"HTTP_X_CSRFTOKEN": client.cookies[settings.CSRF_COOKIE_NAME].value}
                response = client.post(login_url, {"login": identity, "password": password}, **headers)
                self.assertRedirects(response, reverse("home:index"))
                self.assertEqual(client.session["_auth_user_id"], str(user.pk))

    def test_signup_creates_unverified_account_and_confirmation_email(self):
        password = "unrelated-demo-passphrase-29"
        response = self.client.post(reverse("account_signup"), {
            "username": "new-customer", "email": "new@example.test",
            "password1": password, "password2": password,
        })
        self.assertRedirects(response, reverse("account_email_verification_sent"))
        email = EmailAddress.objects.get(email="new@example.test")
        self.assertFalse(email.verified)
        self.assertFalse(self.client.session.get("_auth_user_id"))
        self.assertEqual(mail.outbox[0].to, [email.email])

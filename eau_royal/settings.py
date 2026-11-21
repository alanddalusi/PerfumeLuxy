"""Django configuration for local development and production."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_flag(name):
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


def env_list(name):
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").strip().lower()
if DJANGO_ENV not in {"development", "production"}:
    raise ImproperlyConfigured("DJANGO_ENV must be development or production.")
PRODUCTION = DJANGO_ENV == "production"

# Preserve the existing local signing key when upgrading a legacy checkout.
local_secret = ""
if not PRODUCTION and not os.environ.get("SECRET_KEY") and (BASE_DIR / "env.py").is_file():
    original_environment = os.environ.copy()
    try:
        import env  # noqa: F401
        local_secret = os.environ.get("SECRET_KEY", "")
    finally:
        os.environ.clear()
        os.environ.update(original_environment)

SECRET_KEY = os.environ.get("SECRET_KEY") or local_secret
DEBUG = not PRODUCTION
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

if PRODUCTION:
    if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
        raise ImproperlyConfigured("Set a strong SECRET_KEY before starting production.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Set explicit DJANGO_ALLOWED_HOSTS in production.")
else:
    SECRET_KEY = SECRET_KEY or "django-insecure-local-development-only-perfumeria-el-buen-olor"
    ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]"]

SECURE_SSL_REDIRECT = PRODUCTION
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = PRODUCTION and env_flag("DJANGO_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = SECURE_HSTS_INCLUDE_SUBDOMAINS and env_flag("DJANGO_HSTS_PRELOAD")
if PRODUCTION and env_flag("DJANGO_TRUST_HTTPS_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Container health checks reach Gunicorn directly over HTTP on the private network.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
# Peers allowed to report the visitor address in X-Forwarded-For (the bundled Caddy).
# Empty by default: REMOTE_ADDR is then always the TCP peer.
TRUSTED_PROXY_NETWORKS = env_list("DJANGO_TRUSTED_PROXY_NETWORKS")
# Shared VPS: container names of a proxy whose address may change (resolved every 30 s).
TRUSTED_PROXY_HOSTS = env_list("DJANGO_TRUSTED_PROXY_HOSTS")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "home",
    "products",
    "bag",
    "checkout",
    "profiles",
    "storages",
    "crispy_forms",
    "crispy_bootstrap5",
]

MIDDLEWARE = [
    "eau_royal.proxy.TrustedProxyMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "eau_royal.urls"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
            os.path.join(BASE_DIR, "templates", "allauth"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "bag.contexts.bag_contents",
                "checkout.store_mode.store_mode_context",
                "home.legal.legal_context",
                "home.context.mail_context",
                "eau_royal.seo.seo_context",
            ],
            "builtins": [
                "crispy_forms.templatetags.crispy_forms_tags",
                "crispy_forms.templatetags.crispy_forms_field",
            ],
        },
    },
]

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by e-mail
    "allauth.account.auth_backends.AuthenticationBackend",
)

SITE_ID = 1

ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_ADAPTER = "eau_royal.accounts.MailAwareAccountAdapter"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_MIN_LENGTH = 4
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"

WSGI_APPLICATION = "eau_royal.wsgi.application"


DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if PRODUCTION and not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL is required in production.")
if DATABASE_URL:
    database = dj_database_url.parse(DATABASE_URL, conn_health_checks=True)
    if PRODUCTION:
        if database["ENGINE"] != "django.db.backends.postgresql":
            raise ImproperlyConfigured("Production requires PostgreSQL.")
        options = database.setdefault("OPTIONS", {})
        sslmode = options.setdefault("sslmode", "require")
        # Plain connections are accepted only for explicitly listed single-label service
        # names (e.g. "db" on an internal Docker network without published ports).
        plaintext_hosts = {host for host in env_list("DJANGO_DB_PLAINTEXT_HOSTS") if "." not in host and ":" not in host}
        private_service = sslmode == "disable" and database.get("HOST") in plaintext_hosts
        if sslmode not in {"require", "verify-ca", "verify-full"} and not private_service:
            raise ImproperlyConfigured("Production PostgreSQL requires TLS.")
        database["CONN_MAX_AGE"] = 60
    DATABASES = {"default": database}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True


USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
STATICFILES_DIRS = (os.path.join(BASE_DIR, "static"),)
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
if env_flag("USE_AWS"):
    bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME") or "eau-royal"
    domain = os.environ.get("AWS_S3_CUSTOM_DOMAIN") or f"{bucket}.s3.amazonaws.com"
    storage_options = {
        "bucket_name": bucket,
        "region_name": os.environ.get("AWS_S3_REGION_NAME", "eu-west-2"),
        "custom_domain": domain,
    }
    STORAGES = {
        "default": {
            "BACKEND": "custom_storages.MediaStorage",
            "OPTIONS": storage_options,
        },
        "staticfiles": {
            "BACKEND": "custom_storages.StaticStorage",
            "OPTIONS": storage_options,
        },
    }
    STATIC_URL = f"https://{domain}/static/"
    MEDIA_URL = f"https://{domain}/media/"

# Shared VPS: the existing reverse proxy cannot mount our static volume, so Django serves the
# collected files itself (WhiteNoise). Off by default: the bundled Caddy serves /static/.
SERVE_STATIC = env_flag("DJANGO_SERVE_STATIC")
if SERVE_STATIC:
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
        "whitenoise.middleware.WhiteNoiseMiddleware",
    )
    WHITENOISE_MAX_AGE = 86400

STORE_MODE = os.environ.get("STORE_MODE", "prelaunch").strip().lower()

# Legal identity of the site owner (LSSI-CE art. 10, RGPD art. 13). Only real data, set on the server.
# Until every required value is present, /aviso-legal/, /politica-de-privacidad/ and /contacto/
# answer 404 and are not linked or listed in the sitemap: nothing is published with invented data.
LEGAL_OWNER = {
    "name": os.environ.get("LEGAL_OWNER_NAME", "").strip(),           # nombre completo o razón social
    "tax_id": os.environ.get("LEGAL_OWNER_TAX_ID", "").strip(),       # NIF / CIF
    "address": os.environ.get("LEGAL_OWNER_ADDRESS", "").strip(),     # domicilio completo
    "email": os.environ.get("LEGAL_OWNER_EMAIL", "").strip(),         # correo de contacto
    "phone": os.environ.get("LEGAL_OWNER_PHONE", "").strip(),         # opcional
    "registry": os.environ.get("LEGAL_OWNER_REGISTRY", "").strip(),   # datos registrales (si es sociedad)
}
LEGAL_REQUIRED_FIELDS = ("name", "tax_id", "address", "email")
CATALOG_ASSET_ROOT = Path(os.environ.get("CATALOG_ASSET_ROOT") or BASE_DIR / "catalog_assets")
STORAGES["catalog_assets"] = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {"location": CATALOG_ASSET_ROOT},
}
# Outgoing mail is off unless EMAIL_DELIVERY=smtp is set explicitly in production.
EMAIL_DELIVERY = os.environ.get("EMAIL_DELIVERY", "disabled").strip().lower()
if EMAIL_DELIVERY not in {"disabled", "smtp"}:
    raise ImproperlyConfigured("EMAIL_DELIVERY must be disabled or smtp.")
SMTP_ENABLED = PRODUCTION and EMAIL_DELIVERY == "smtp"
INTEREST_EMAIL_DELIVERY = SMTP_ENABLED and env_flag("INTEREST_EMAIL_DELIVERY")
# Forms that promise a confirmation e-mail are offered only when that e-mail can really be
# sent. Development keeps them open because mail goes to the console.
NOTICE_SIGNUPS_OPEN = INTEREST_EMAIL_DELIVERY or not PRODUCTION
ACCOUNT_SIGNUPS_OPEN = SMTP_ENABLED or not PRODUCTION
INTEREST_PREVIEW_BACKEND = (
    "django.core.mail.backends.dummy.EmailBackend" if PRODUCTION
    else "django.core.mail.backends.console.EmailBackend"
)

# Stripe API
STRIPE_CURRENCY = "gbp"
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DISCOUNT_PERCENTAGE = 15
DISCOUNT_THRESHOLD = 60
FREE_DELIVERY_THRESHOLD = 100

if SMTP_ENABLED:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "").strip()
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USE_SSL = env_flag("EMAIL_USE_SSL")
    EMAIL_USE_TLS = not EMAIL_USE_SSL
    EMAIL_TIMEOUT = 10
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD") or os.environ.get("EMAIL_HOST_PASS", "")
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "").strip()
    if not EMAIL_HOST or not DEFAULT_FROM_EMAIL:
        raise ImproperlyConfigured("EMAIL_DELIVERY=smtp requires EMAIL_HOST and DEFAULT_FROM_EMAIL.")
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
elif PRODUCTION:
    # Production without approved SMTP: every message is discarded, nothing leaves the server.
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "").strip() or "no-reply@localhost"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "eau-royal@royal.com"


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_tokens": {"()": "eau_royal.logging_filters.RedactTokensFilter"},
        # Outside production, behave like Django's default: log only while DEBUG is on.
        "environment": {"()": "django.utils.log.RequireDebugTrue" if not PRODUCTION else "logging.Filter"},
    },
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {
        # Container stdout; Docker rotates it (see deploy/docker-compose.yml).
        "console": {"class": "logging.StreamHandler", "filters": ["environment", "redact_tokens"], "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"), "propagate": False},
    },
}

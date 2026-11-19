"""Offline settings for reviewing the legacy catalog fixture."""

from .settings import *  # noqa: F403

CATALOG_REVIEW = True
STORE_MODE = "prelaunch"
DEBUG = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "catalog-review.sqlite3",  # noqa: F405
    },
}
ROOT_URLCONF = __name__
urlpatterns = []

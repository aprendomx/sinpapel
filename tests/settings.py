"""Minimal Django settings for sinpapel test suite."""
import os

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": os.getenv("TEST_DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("TEST_DB_NAME", ":memory:"),
        "USER": os.getenv("TEST_DB_USER", ""),
        "PASSWORD": os.getenv("TEST_DB_PASSWORD", ""),
        "HOST": os.getenv("TEST_DB_HOST", ""),
        "PORT": os.getenv("TEST_DB_PORT", ""),
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "simple_history",
    "sinpapel",
    "tests",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

SINPAPEL_SIGNATURE_BACKEND = "sinpapel.signing.backends.fake.FakeBackend"
SINPAPEL_PREDICATE_MODULES = ["tests.test_predicates"]

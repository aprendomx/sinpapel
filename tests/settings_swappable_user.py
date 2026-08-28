"""Settings con AUTH_USER_MODEL swapped, para el test de regresión de FKs.

sinpapel debe declarar sus FKs a usuario con `settings.AUTH_USER_MODEL`. Si
alguno vuelve al literal "auth.User", `manage.py check` falla con fields.E301
y el framework queda inservible en cualquier proyecto con usuario custom.
"""
from tests.settings import *  # noqa: F401,F403

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "simple_history",
    "sinpapel",
    "tests.swappable_user",
]

AUTH_USER_MODEL = "swappable_user.CustomUser"

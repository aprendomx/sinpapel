"""Modelo de usuario custom, solo para el test de AUTH_USER_MODEL swappable."""
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    class Meta:
        app_label = "swappable_user"

"""Regresión: sinpapel debe soportar un AUTH_USER_MODEL custom.

Hasta 0.8.2, `VersionFlujo.creado_por`, `SeguimientoWorkflow.usuario_accion` y
`RegistroFirma.signer` declaraban el FK con el literal "auth.User". Con un
usuario custom, Django aborta en el system check con cinco `fields.E301`
(los tres campos más sus modelos Historical) y el proyecto no arranca.

El check corre en un subproceso porque AUTH_USER_MODEL no se puede cambiar
dentro de un proceso Django ya inicializado.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_hardcoded_auth_user_in_model_fields():
    """Ningún FK de sinpapel apunta al literal 'auth.User'."""
    from django.conf import settings
    from django.contrib.auth import get_user_model

    from sinpapel.models import RegistroFirma, SeguimientoWorkflow, VersionFlujo

    user_model = get_user_model()
    campos = [
        (VersionFlujo, "creado_por"),
        (SeguimientoWorkflow, "usuario_accion"),
        (RegistroFirma, "signer"),
    ]
    for modelo, nombre in campos:
        field = modelo._meta.get_field(nombre)
        assert field.remote_field.model is user_model, (
            f"{modelo.__name__}.{nombre} debe resolver a "
            f"{settings.AUTH_USER_MODEL}, no a un modelo fijo."
        )


def test_system_check_passes_with_swapped_user_model():
    """`manage.py check` pasa limpio con AUTH_USER_MODEL custom."""
    proc = subprocess.run(
        [sys.executable, "-m", "django", "check"],
        cwd=REPO_ROOT,
        env={
            "DJANGO_SETTINGS_MODULE": "tests.settings_swappable_user",
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(REPO_ROOT.parent),
            "TEST_DB_NAME": ":memory:",
        },
        capture_output=True,
        check=False,
        text=True,
    )
    assert proc.returncode == 0, (
        "sinpapel no soporta AUTH_USER_MODEL custom:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_migrate_succeeds_with_swapped_user_model():
    """`migrate` aplica el esquema completo con AUTH_USER_MODEL custom."""
    proc = subprocess.run(
        [sys.executable, "-m", "django", "migrate", "--run-syncdb", "-v", "0"],
        cwd=REPO_ROOT,
        env={
            "DJANGO_SETTINGS_MODULE": "tests.settings_swappable_user",
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(REPO_ROOT.parent),
            "TEST_DB_NAME": ":memory:",
        },
        capture_output=True,
        check=False,
        text=True,
    )
    assert proc.returncode == 0, (
        "migrate falla con AUTH_USER_MODEL custom:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )

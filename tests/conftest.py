"""sinpapel — pytest fixtures comunes a tests sinpapel/.

S13.1: autouse fixture clears cache entre tests para evitar leaks.
LocMemCache es process-wide; transactional DB resetea entre tests pero
cache persiste, causando stale Estado/VersionFlujo entries con IDs
de la DB rolled-back.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_sinpapel_cache_each_test():
    """S13.1: clear sinpapel.cache entre tests (anti-leak LocMemCache)."""
    from sinpapel.cache import clear_all
    clear_all()
    yield
    clear_all()


@pytest.fixture
def sinpapel_migrated(transactional_db):
    """Ensure sinpapel migrations are applied for tests that need the schema.

    Some tests use @pytest.mark.django_db(transaction=True) which skips
    automatic migration in some backends (PostgreSQL). This fixture forces
    migrations to run once per test function that requests it.
    """
    from django.core.management import call_command
    call_command("migrate", verbosity=0)

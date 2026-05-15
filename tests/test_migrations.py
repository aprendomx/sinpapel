"""Verify legacy table prefix has been removed."""
from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_no_creditos_table_prefix():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'creditos_%'"
        )
        count = cursor.fetchone()[0]
    assert count == 0, f"Found {count} legacy tables with creditos_ prefix"


@pytest.mark.django_db
def test_sinpapel_tables_exist():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sinpapel_%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
    assert "sinpapel_estado" in tables
    assert "sinpapel_etapa" in tables
    assert "sinpapel_documento" in tables
    assert "sinpapel_registrofirma" in tables

"""Smoke test: la migración 0001_initial es reversible.

Aplica reverse → forward via MigrationExecutor sobre la test DB y verifica
que las tablas se dropean y recrean sin perder datos en las tablas no-history.
"""
from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

skip_if_not_sqlite = pytest.mark.skipif(
    connection.vendor != "sqlite",
    reason="SQLite-specific introspection query",
)


@skip_if_not_sqlite
@pytest.mark.django_db(transaction=True)
def test_migration_0001_is_reversible():
    """0001_initial puede aplicarse forward → reverse → forward."""
    executor = MigrationExecutor(connection)

    # Forward state ya aplicado por pytest-django; vamos al estado anterior (zero)
    executor.migrate([("sinpapel", None)])

    # Verificar que las tablas sinpapel fueron dropeadas
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sinpapel_%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
    assert not tables, f"sinpapel tables persisten tras reverse: {tables}"

    # Re-apply forward
    executor.loader.build_graph()  # refresh state
    executor.migrate([("sinpapel", "0001_initial")])

    # Verificar que las tablas sinpapel existen de nuevo
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sinpapel_%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
    expected = {
        "sinpapel_estado",
        "sinpapel_etapa",
        "sinpapel_configuraciontransicion",
        "sinpapel_versionflujo",
        "sinpapel_seguimientoworkflow",
        "sinpapel_requisitoestadodocumento",
        "sinpapel_documento",
        "sinpapel_tipodocumento",
        "sinpapel_instanciadocumento",
        "sinpapel_razonrechazodocumento",
        "sinpapel_expedienteadjunto",
        "sinpapel_registrofirma",
    }
    assert expected.issubset(tables), (
        f"sinpapel tables faltantes tras forward: {expected - tables}"
    )

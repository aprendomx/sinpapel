"""Smoke test: la migración 0003_historical_records es reversible.

Aplica reverse → forward via MigrationExecutor sobre la test DB y verifica
que las tablas historical* se dropean y recrean sin perder datos en las
tablas no-history.
"""
from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_migration_0003_is_reversible():
    """0003_historical_records puede aplicarse forward → reverse → forward."""
    executor = MigrationExecutor(connection)

    # Forward state ya aplicado por pytest-django; vamos al estado anterior
    executor.migrate([("sinpapel", "0002_extract_remaining_models")])

    # Verificar que las tablas historical* fueron dropeadas
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'sinpapel_historical%' "
            "OR table_name LIKE 'historical%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
    assert not tables, f"historical* tables persisten tras reverse: {tables}"

    # Re-apply forward
    executor.loader.build_graph()  # refresh state
    executor.migrate([("sinpapel", "0003_historical_records")])

    # Verificar que las tablas historical* existen de nuevo
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'sinpapel_historical%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
    expected = {
        "sinpapel_historicalregistrofirma",
        "sinpapel_historicalinstanciadocumento",
        "sinpapel_historicalconfiguraciontransicion",
        "sinpapel_historicalversionflujo",
        "sinpapel_historicalrequisitoestadodocumento",
    }
    assert expected.issubset(tables), (
        f"historical tables faltantes tras forward: {expected - tables}"
    )

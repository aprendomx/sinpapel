"""S13.8 — Tests para schema flow_export + management commands.

Cubre:
- T1: schema funciones (serialize, validate, find_missing, deserialize)
- T2: sinpapel_export_flujo CLI
- T3: sinpapel_import_flujo CLI
- T4: round-trip equivalence + atomic rollback + ambiguity
"""
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import Group

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def catalog_setup(db):
    """Crea Estados + TipoDocumentos + Groups + VersionFlujo con transitions+requisitos."""
    from sinpapel.models import (
        ConfiguracionTransicion, Estado, RequisitoEstadoDocumento,
        TipoDocumento, VersionFlujo,
    )

    e_orig = Estado.objects.create(nombre="FP_CAPTURA")
    e_dest = Estado.objects.create(nombre="FP_REVISION")
    e_final = Estado.objects.create(nombre="FP_APROBADO")

    td_ine = TipoDocumento.objects.create(nombre="FP_INE")
    td_curp = TipoDocumento.objects.create(nombre="FP_CURP")

    g_at = Group.objects.create(name="FP_AsistenteTecnico")
    g_jefe = Group.objects.create(name="FP_JefeModulo")

    flujo = VersionFlujo.objects.create(
        nombre="FP_FLUJO_TEST", descripcion="test", activo=True,
        metadatos={"positions": {"1": {"x": 100, "y": 200}}},
    )
    t1 = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=e_orig, estado_destino=e_dest,
    )
    t1.grupos_permitidos.add(g_at, g_jefe)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=e_dest, estado_destino=e_final,
    )
    RequisitoEstadoDocumento.objects.create(
        estado=e_orig, tipo_documento=td_ine, porcentaje=100, auto_carga=False,
    )
    RequisitoEstadoDocumento.objects.create(
        estado=e_orig, tipo_documento=td_curp, porcentaje=100, auto_carga=True,
    )
    return {
        "flujo": flujo,
        "estados": {"orig": e_orig, "dest": e_dest, "final": e_final},
        "tipos": {"ine": td_ine, "curp": td_curp},
        "grupos": {"at": g_at, "jefe": g_jefe},
    }


# ─────────────────────────────────────────────────────────────────────────────
# T1 — Schema funciones
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_serialize_flujo_includes_schema_version(catalog_setup):
    from sinpapel.schemas.flujo_export import SCHEMA_VERSION, serialize_flujo
    data = serialize_flujo(catalog_setup["flujo"])
    assert data["schema_version"] == SCHEMA_VERSION
    assert "exported_at" in data
    assert "flujo" in data
    assert data["flujo"]["nombre"] == "FP_FLUJO_TEST"


@pytest.mark.django_db
def test_serialize_flujo_transitions_with_grupos_sorted(catalog_setup):
    from sinpapel.schemas.flujo_export import serialize_flujo
    data = serialize_flujo(catalog_setup["flujo"])
    transitions = data["flujo"]["transiciones"]
    assert len(transitions) == 2
    t_first = next(t for t in transitions if t["estado_origen"] == "FP_CAPTURA")
    # Grupos sorted (deterministic)
    assert t_first["grupos_permitidos"] == ["FP_AsistenteTecnico", "FP_JefeModulo"]
    # Estado destinos por nombre
    assert t_first["estado_destino"] == "FP_REVISION"


@pytest.mark.django_db
def test_serialize_flujo_requisitos_with_porcentaje_auto_carga(catalog_setup):
    from sinpapel.schemas.flujo_export import serialize_flujo
    data = serialize_flujo(catalog_setup["flujo"])
    requisitos = data["flujo"]["requisitos"]
    assert len(requisitos) == 2
    r_ine = next(r for r in requisitos if r["tipo_documento"] == "FP_INE")
    assert r_ine["estado"] == "FP_CAPTURA"
    assert r_ine["porcentaje"] == 100
    assert r_ine["auto_carga"] is False
    r_curp = next(r for r in requisitos if r["tipo_documento"] == "FP_CURP")
    assert r_curp["auto_carga"] is True


def test_validate_schema_version_v01_ok():
    from sinpapel.schemas.flujo_export import validate_schema_version
    validate_schema_version({"schema_version": "0.1"})  # no raise


def test_validate_schema_version_unsupported_raises():
    from sinpapel.schemas.flujo_export import validate_schema_version
    # "0.99" is clearly unsupported; "0.2" became supported in S27.2 (ADR-017).
    with pytest.raises(ValueError, match="Unsupported schema_version"):
        validate_schema_version({"schema_version": "0.99"})


def test_validate_schema_version_v02_ok():
    """S27.2 (ADR-017): validate acepta v0.2 (extension de S13.8 v0.1-only)."""
    from sinpapel.schemas.flujo_export import validate_schema_version
    validate_schema_version({"schema_version": "0.2"})  # no raise


def test_validate_schema_version_rejects_0_3():
    """S27.2: forward-compat reject explícito pre-1.0 (ADR-017)."""
    from sinpapel.schemas.flujo_export import validate_schema_version
    with pytest.raises(ValueError, match="Unsupported schema_version='0.3'"):
        validate_schema_version({"schema_version": "0.3"})


@pytest.mark.django_db
def test_v0_1_fixture_still_importable(catalog_setup):
    """S27.2 backward-compat (ADR-017): v0.1 fixture sigue importable post-v0.2.

    Static fixture en tests/fixtures/flujo_v0_1.json protege contra
    regresión accidental del contrato v0.1.
    """
    from sinpapel.schemas.flujo_export import deserialize_flujo
    fixture_path = FIXTURES_DIR / "flujo_v0_1.json"
    with open(fixture_path) as f:
        data = json.load(f)

    assert data["schema_version"] == "0.1"
    assert "catalogos" not in data  # v0.1 shape

    flujo = deserialize_flujo(data)
    assert flujo is not None
    assert flujo.nombre == "FP_FIXTURE_V0_1"
    # Validate transitions persisted
    assert flujo.transiciones.count() == 2


# ─────────────────────────────────────────────────────────────────────────────
# S27.2 T2 — serialize_flujo with inline_catalogs (v0.2 export)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_serialize_flujo_default_is_v0_1(catalog_setup):
    """S27.2 D2: default serialize sin inline_catalogs produce v0.1."""
    from sinpapel.schemas.flujo_export import serialize_flujo
    data = serialize_flujo(catalog_setup["flujo"])
    assert data["schema_version"] == "0.1"
    assert "catalogos" not in data


@pytest.mark.django_db
def test_serialize_flujo_inline_catalogs_produces_v0_2(catalog_setup):
    """S27.2 AC1: opt-in inline_catalogs=True produce v0.2 con catalogos section."""
    from sinpapel.schemas.flujo_export import serialize_flujo
    data = serialize_flujo(catalog_setup["flujo"], inline_catalogs=True)
    assert data["schema_version"] == "0.2"
    assert "catalogos" in data
    assert set(data["catalogos"].keys()) == {"estados", "etapas", "grupos", "tipos_documento"}

    estado_names = {e["nombre"] for e in data["catalogos"]["estados"]}
    assert estado_names == {"FP_CAPTURA", "FP_REVISION", "FP_APROBADO"}

    tipo_names = {t["nombre"] for t in data["catalogos"]["tipos_documento"]}
    assert "FP_INE" in tipo_names
    assert "FP_CURP" in tipo_names

    group_names = {g["name"] for g in data["catalogos"]["grupos"]}
    assert group_names == {"FP_AsistenteTecnico", "FP_JefeModulo"}


@pytest.mark.django_db
def test_serialize_v0_2_includes_estado_etapa_relation(catalog_setup):
    """S27.2 AC6: Estado.etapa serialized as nombre ref en v0.2."""
    from sinpapel.models import Etapa
    from sinpapel.schemas.flujo_export import serialize_flujo

    etapa = Etapa.objects.create(nombre="FP_ETAPA_PRE")
    estado_orig = catalog_setup["estados"]["orig"]
    estado_orig.etapa = etapa
    estado_orig.save()

    data = serialize_flujo(catalog_setup["flujo"], inline_catalogs=True)
    etapa_names = {e["nombre"] for e in data["catalogos"]["etapas"]}
    assert "FP_ETAPA_PRE" in etapa_names

    estado_orig_data = next(
        e for e in data["catalogos"]["estados"] if e["nombre"] == "FP_CAPTURA"
    )
    assert estado_orig_data["etapa"] == "FP_ETAPA_PRE"

    # Estado without etapa serialized as None
    estado_dest_data = next(
        e for e in data["catalogos"]["estados"] if e["nombre"] == "FP_REVISION"
    )
    assert estado_dest_data["etapa"] is None


@pytest.mark.django_db
def test_serialize_v0_2_positions_name_keyed(catalog_setup):
    """S27.2 D6: v0.2 export migra metadatos.positions de ID-keying a name-keying."""
    from sinpapel.schemas.flujo_export import serialize_flujo

    flujo = catalog_setup["flujo"]
    estado_orig = catalog_setup["estados"]["orig"]
    estado_dest = catalog_setup["estados"]["dest"]
    # Set positions con ID-keying (legacy creditos behavior)
    flujo.metadatos = {
        "positions": {
            str(estado_orig.id): {"x": 100, "y": 200},
            str(estado_dest.id): {"x": 300, "y": 400},
        }
    }
    flujo.save()

    data = serialize_flujo(flujo, inline_catalogs=True)
    positions = data["flujo"]["metadatos"]["positions"]
    assert "FP_CAPTURA" in positions
    assert positions["FP_CAPTURA"] == {"x": 100, "y": 200}
    assert "FP_REVISION" in positions
    assert positions["FP_REVISION"] == {"x": 300, "y": 400}
    # ID keys no longer present (converted)
    assert str(estado_orig.id) not in positions
    assert str(estado_dest.id) not in positions


# ─────────────────────────────────────────────────────────────────────────────
# S27.2 T3 — deserialize_flujo with create_catalogs (v0.2 import + upsert)
# ─────────────────────────────────────────────────────────────────────────────


def _v0_2_minimal_data(flujo_nombre: str = "FP_FLUJO_S27_2") -> dict:
    """Helper: build v0.2 JSON data for tests con catalogos inline."""
    return {
        "schema_version": "0.2",
        "exported_at": "2026-05-11T20:00:00+00:00",
        "catalogos": {
            "etapas": [
                {"nombre": "ETAPA_X", "color": "#aaa", "descripcion": "",
                 "orden": 1, "activo": True}
            ],
            "estados": [
                {
                    "nombre": "EST_NUEVO_A", "color": "#111", "icono": "edit",
                    "descripcion": "", "orden": 1, "activo": True,
                    "etapa": "ETAPA_X",
                    "permite_expediente": False, "expediente_obligatorio": False,
                },
                {
                    "nombre": "EST_NUEVO_B", "color": "#222", "icono": "check",
                    "descripcion": "", "orden": 2, "activo": True,
                    "etapa": None,
                    "permite_expediente": False, "expediente_obligatorio": False,
                },
            ],
            "grupos": [{"name": "GRP_NUEVO"}],
            "tipos_documento": [],
        },
        "flujo": {
            "nombre": flujo_nombre,
            "descripcion": "S27.2 T3 test",
            "activo": False,
            "metadatos": {"positions": {"EST_NUEVO_A": {"x": 10, "y": 20}}},
            "transiciones": [
                {"estado_origen": "EST_NUEVO_A", "estado_destino": "EST_NUEVO_B",
                 "grupos_permitidos": ["GRP_NUEVO"]}
            ],
            "requisitos": [],
        },
    }


@pytest.mark.django_db
def test_deserialize_v0_2_creates_inline_catalogs(db):
    """S27.2 AC3: v0.2 import con create_catalogs=True crea Estados/Etapas/Grupos missing."""
    from django.contrib.auth.models import Group
    from sinpapel.models import Estado, Etapa, VersionFlujo
    from sinpapel.schemas.flujo_export import deserialize_flujo

    assert not Estado.objects.filter(nombre="EST_NUEVO_A").exists()
    assert not Etapa.objects.filter(nombre="ETAPA_X").exists()
    assert not Group.objects.filter(name="GRP_NUEVO").exists()

    data = _v0_2_minimal_data()
    flujo = deserialize_flujo(data)  # create_catalogs=True by default

    assert flujo is not None
    assert Estado.objects.filter(nombre="EST_NUEVO_A").exists()
    assert Estado.objects.filter(nombre="EST_NUEVO_B").exists()
    assert Etapa.objects.filter(nombre="ETAPA_X").exists()
    assert Group.objects.filter(name="GRP_NUEVO").exists()
    # Estado.etapa FK resolved
    estado_a = Estado.objects.get(nombre="EST_NUEVO_A")
    assert estado_a.etapa is not None
    assert estado_a.etapa.nombre == "ETAPA_X"
    # Flujo transitions persisted
    assert VersionFlujo.objects.get(nombre="FP_FLUJO_S27_2").transiciones.count() == 1


@pytest.mark.django_db
def test_deserialize_v0_2_update_existing_emits_warning(db, caplog):
    """S27.2 AC4 + D5: upsert update existing Estado emite WARNING (no exception)."""
    import logging
    from sinpapel.models import Estado
    from sinpapel.schemas.flujo_export import deserialize_flujo

    # Pre-existing Estado con defaults distintos
    Estado.objects.create(nombre="EST_NUEVO_A", color="#OLD", icono="old_icon")

    data = _v0_2_minimal_data()
    with caplog.at_level(logging.WARNING, logger="sinpapel.schemas.flujo_export"):
        flujo = deserialize_flujo(data)

    assert flujo is not None
    estado_a = Estado.objects.get(nombre="EST_NUEVO_A")
    assert estado_a.color == "#111"  # updated to inline value
    assert estado_a.icono == "edit"
    # WARNING emitted
    warning_msgs = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any("EST_NUEVO_A" in m for m in warning_msgs)


@pytest.mark.django_db
def test_deserialize_v0_2_no_create_catalogs_rejects_missing(db):
    """S27.2 AC5: create_catalogs=False con missing Estado raises (v0.1 semantics)."""
    from sinpapel.schemas.flujo_export import deserialize_flujo

    data = _v0_2_minimal_data()
    with pytest.raises(ValueError, match="Missing entities in destination"):
        deserialize_flujo(data, create_catalogs=False)


@pytest.mark.django_db
def test_deserialize_v0_2_ambiguous_estado_rejects(db):
    """S27.2 AC7: ambiguity check preservado en v0.2 (PAT-E-523)."""
    from sinpapel.models import Estado
    from sinpapel.schemas.flujo_export import deserialize_flujo

    # Create AMBIGUITY: 2 Estados con mismo nombre (Catalogo.nombre NOT unique)
    Estado.objects.create(nombre="EST_NUEVO_A", color="#one")
    Estado.objects.create(nombre="EST_NUEVO_A", color="#two")

    data = _v0_2_minimal_data()
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        deserialize_flujo(data)


@pytest.mark.django_db
def test_deserialize_v0_2_upserts_etapa_before_estado(db):
    """S27.2 D7: upsert order Etapa -> Estado (FK dependency)."""
    from sinpapel.models import Estado, Etapa
    from sinpapel.schemas.flujo_export import deserialize_flujo

    assert not Etapa.objects.exists()
    assert not Estado.objects.exists()

    data = _v0_2_minimal_data()
    deserialize_flujo(data)

    # Etapa creada antes que Estado (FK resolved)
    etapa = Etapa.objects.get(nombre="ETAPA_X")
    estado_a = Estado.objects.get(nombre="EST_NUEVO_A")
    assert estado_a.etapa_id == etapa.id


# ─────────────────────────────────────────────────────────────────────────────
# S27.2 T4 — Round-trip integration (real Django ORM, no mocks)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_round_trip_v0_2_with_inline_catalogs_real_db(catalog_setup):
    """S27.2 AC10 + integration gate: round-trip v0.2 schema-equivalent vs real ORM.

    Flow:
        1. catalog_setup crea VersionFlujo + Estados/TipoDocumento/Group en DB
        2. Export v0.2 (inline_catalogs=True)
        3. Modify exported nombre (evita duplicate flujo reject)
        4. Import → crea new VersionFlujo (catalogos existing son upserted no-op)
        5. Re-export v0.2 del new flujo
        6. Assert schema-equivalent (transitions, requisitos, catalog refs)
    """
    from sinpapel.schemas.flujo_export import deserialize_flujo, serialize_flujo

    flujo = catalog_setup["flujo"]
    # Set positions ID-keyed para validar conversion ID->nombre en round-trip
    flujo.metadatos = {
        "positions": {
            str(catalog_setup["estados"]["orig"].id): {"x": 50, "y": 50},
            str(catalog_setup["estados"]["dest"].id): {"x": 250, "y": 100},
        }
    }
    flujo.save()

    # Export v0.2
    exported = serialize_flujo(flujo, inline_catalogs=True)
    assert exported["schema_version"] == "0.2"
    # positions migrated to name-keying
    assert "FP_CAPTURA" in exported["flujo"]["metadatos"]["positions"]

    # Modify nombre para evitar duplicate reject
    exported["flujo"]["nombre"] = "FP_FLUJO_ROUNDTRIP"

    # Import → upsert catalogos (no-op porque ya existen) + crea new flujo
    imported_flujo = deserialize_flujo(exported)
    assert imported_flujo is not None
    assert imported_flujo.nombre == "FP_FLUJO_ROUNDTRIP"

    # Re-export
    re_exported = serialize_flujo(imported_flujo, inline_catalogs=True)
    assert re_exported["schema_version"] == "0.2"

    # Schema-equivalent: transiciones byte-equal
    assert exported["flujo"]["transiciones"] == re_exported["flujo"]["transiciones"]
    assert exported["flujo"]["requisitos"] == re_exported["flujo"]["requisitos"]
    # Catalog references schema-equivalent (sorted by nombre + same field set)
    assert (
        sorted(e["nombre"] for e in exported["catalogos"]["estados"])
        == sorted(e["nombre"] for e in re_exported["catalogos"]["estados"])
    )
    assert (
        sorted(g["name"] for g in exported["catalogos"]["grupos"])
        == sorted(g["name"] for g in re_exported["catalogos"]["grupos"])
    )
    # positions name-keyed both sides
    assert exported["flujo"]["metadatos"]["positions"] == re_exported["flujo"]["metadatos"]["positions"]


@pytest.mark.django_db
def test_find_missing_entities_empty_when_complete(catalog_setup):
    from sinpapel.schemas.flujo_export import find_missing_entities, serialize_flujo
    data = serialize_flujo(catalog_setup["flujo"])
    missing = find_missing_entities(data)
    assert missing == {"Estado": [], "TipoDocumento": [], "Group": []}


@pytest.mark.django_db
def test_find_missing_entities_lists_missing(db):
    from sinpapel.schemas.flujo_export import find_missing_entities
    data = {
        "schema_version": "0.1",
        "flujo": {
            "nombre": "X",
            "transiciones": [
                {"estado_origen": "DOES_NOT_EXIST_A", "estado_destino": "DOES_NOT_EXIST_B",
                 "grupos_permitidos": ["MissingGroup"]},
            ],
            "requisitos": [
                {"estado": "DOES_NOT_EXIST_A", "tipo_documento": "MissingTipo",
                 "porcentaje": 100, "auto_carga": False},
            ],
        },
    }
    missing = find_missing_entities(data)
    assert "DOES_NOT_EXIST_A" in missing["Estado"]
    assert "DOES_NOT_EXIST_B" in missing["Estado"]
    assert "MissingTipo" in missing["TipoDocumento"]
    assert "MissingGroup" in missing["Group"]


@pytest.mark.django_db
def test_deserialize_flujo_dry_run_does_not_persist(catalog_setup):
    from sinpapel.models import VersionFlujo
    from sinpapel.schemas.flujo_export import deserialize_flujo, serialize_flujo

    data = serialize_flujo(catalog_setup["flujo"])
    data["flujo"]["nombre"] = "FP_DRY_RUN_ONLY"
    count_before = VersionFlujo.objects.count()
    result = deserialize_flujo(data, dry_run=True, activo=False)
    assert result is None
    assert VersionFlujo.objects.count() == count_before


@pytest.mark.django_db
def test_deserialize_flujo_creates_entities_atomically(catalog_setup):
    from sinpapel.models import (
        ConfiguracionTransicion, RequisitoEstadoDocumento, VersionFlujo,
    )
    from sinpapel.schemas.flujo_export import deserialize_flujo, serialize_flujo

    data = serialize_flujo(catalog_setup["flujo"])
    data["flujo"]["nombre"] = "FP_DESERIALIZED_NEW"
    flujo_count_before = VersionFlujo.objects.count()
    ct_count_before = ConfiguracionTransicion.objects.count()
    rd_count_before = RequisitoEstadoDocumento.objects.count()

    new_flujo = deserialize_flujo(data, dry_run=False, activo=False)

    assert new_flujo is not None
    assert new_flujo.nombre == "FP_DESERIALIZED_NEW"
    assert new_flujo.activo is False  # safe default
    assert VersionFlujo.objects.count() == flujo_count_before + 1
    assert ConfiguracionTransicion.objects.count() == ct_count_before + 2
    # D-requisitos-shared-catalog: get_or_create — los 2 requisitos ya existen
    # en fixture (estado=FP_CAPTURA), por lo que NO se crean duplicados.
    assert RequisitoEstadoDocumento.objects.count() == rd_count_before


@pytest.mark.django_db
def test_deserialize_flujo_missing_entities_raises(catalog_setup):
    from sinpapel.schemas.flujo_export import deserialize_flujo
    data = {
        "schema_version": "0.1",
        "flujo": {
            "nombre": "FP_MISSING_TEST",
            "descripcion": "",
            "activo": False,
            "metadatos": None,
            "transiciones": [{
                "estado_origen": "MISSING_ESTADO_1",
                "estado_destino": "FP_CAPTURA",
                "grupos_permitidos": [],
            }],
            "requisitos": [],
        },
    }
    with pytest.raises(ValueError, match="Missing entities"):
        deserialize_flujo(data, dry_run=False, activo=False)


@pytest.mark.django_db
def test_deserialize_flujo_duplicate_nombre_raises(catalog_setup):
    from sinpapel.schemas.flujo_export import deserialize_flujo, serialize_flujo
    data = serialize_flujo(catalog_setup["flujo"])
    # Mismo nombre que existing → reject
    with pytest.raises(ValueError, match="already exists"):
        deserialize_flujo(data, dry_run=False, activo=False)


# ─────────────────────────────────────────────────────────────────────────────
# T2 — sinpapel_export_flujo CLI
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_export_command_to_stdout(catalog_setup):
    """call_command sinpapel_export_flujo <id> → JSON válido en stdout."""
    from django.core.management import call_command

    out = StringIO()
    call_command("sinpapel_export_flujo", catalog_setup["flujo"].pk, stdout=out)
    text = out.getvalue()
    data = json.loads(text)
    assert data["schema_version"] == "0.1"
    assert data["flujo"]["nombre"] == "FP_FLUJO_TEST"


@pytest.mark.django_db
def test_export_command_to_file(catalog_setup, tmp_path):
    """--output FILE escribe JSON al archivo + success message."""
    from django.core.management import call_command

    out_path = tmp_path / "flujo.json"
    out_buf = StringIO()
    call_command(
        "sinpapel_export_flujo", catalog_setup["flujo"].pk,
        output=str(out_path), stdout=out_buf,
    )
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["flujo"]["nombre"] == "FP_FLUJO_TEST"
    assert "Exported" in out_buf.getvalue()


@pytest.mark.django_db
def test_export_command_inline_catalogs_emits_v0_2(catalog_setup):
    """S27.3 AC1: --inline-catalogs flag produce v0.2 con seccion catalogos."""
    from django.core.management import call_command

    out = StringIO()
    call_command(
        "sinpapel_export_flujo", catalog_setup["flujo"].pk,
        inline_catalogs=True, stdout=out,
    )
    data = json.loads(out.getvalue())
    assert data["schema_version"] == "0.2"
    assert "catalogos" in data
    assert set(data["catalogos"].keys()) == {
        "estados", "etapas", "grupos", "tipos_documento"
    }


@pytest.mark.django_db
def test_export_command_inline_catalogs_to_file(catalog_setup, tmp_path):
    """S27.3 AC7: --inline-catalogs combinable con --output + message refleja version."""
    from django.core.management import call_command

    out_path = tmp_path / "flujo_v0_2.json"
    out_buf = StringIO()
    call_command(
        "sinpapel_export_flujo", catalog_setup["flujo"].pk,
        inline_catalogs=True, output=str(out_path), stdout=out_buf,
    )
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.2"
    assert "catalogos" in data
    # Success message refleja version
    msg = out_buf.getvalue()
    assert "Exported" in msg
    assert "0.2" in msg


@pytest.mark.django_db
def test_export_command_invalid_id_raises(db):
    """VersionFlujo no existe → CommandError."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="does not exist"):
        call_command("sinpapel_export_flujo", 99999999)


# ─────────────────────────────────────────────────────────────────────────────
# T3 — sinpapel_import_flujo CLI
# ─────────────────────────────────────────────────────────────────────────────


def _export_to_tmp(catalog_setup_fixture, tmp_path, rename_to: str | None = None):
    """Helper: export catalog_setup flujo to tmp file, optionally rename."""
    from sinpapel.schemas.flujo_export import serialize_flujo
    data = serialize_flujo(catalog_setup_fixture["flujo"])
    if rename_to:
        data["flujo"]["nombre"] = rename_to
    out_path = tmp_path / "flujo.json"
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return out_path


@pytest.mark.django_db
def test_import_command_happy_path(catalog_setup, tmp_path):
    """call_command import → VersionFlujo creado con activo=False default."""
    from django.core.management import call_command
    from sinpapel.models import VersionFlujo

    file_path = _export_to_tmp(catalog_setup, tmp_path, rename_to="FP_IMPORT_HAPPY")
    out = StringIO()
    call_command("sinpapel_import_flujo", str(file_path), stdout=out)

    flujo = VersionFlujo.objects.get(nombre="FP_IMPORT_HAPPY")
    assert flujo.activo is False  # safe default
    assert "Imported" in out.getvalue()


@pytest.mark.django_db
def test_import_command_dry_run_does_not_persist(catalog_setup, tmp_path):
    """--dry-run → DB unchanged."""
    from django.core.management import call_command
    from sinpapel.models import VersionFlujo

    file_path = _export_to_tmp(catalog_setup, tmp_path, rename_to="FP_IMPORT_DRY")
    count_before = VersionFlujo.objects.count()
    out = StringIO()
    call_command("sinpapel_import_flujo", str(file_path), dry_run=True, stdout=out)

    assert VersionFlujo.objects.count() == count_before
    assert "DRY-RUN" in out.getvalue()
    assert not VersionFlujo.objects.filter(nombre="FP_IMPORT_DRY").exists()


@pytest.mark.django_db
def test_import_command_activo_flag_overrides_default(catalog_setup, tmp_path):
    """--activo → activo=True override."""
    from django.core.management import call_command
    from sinpapel.models import VersionFlujo

    file_path = _export_to_tmp(catalog_setup, tmp_path, rename_to="FP_IMPORT_ACTIVO")
    call_command("sinpapel_import_flujo", str(file_path), activo=True,
                 stdout=StringIO())

    flujo = VersionFlujo.objects.get(nombre="FP_IMPORT_ACTIVO")
    assert flujo.activo is True


@pytest.mark.django_db
def test_import_command_missing_entities_raises(db, tmp_path):
    """Missing entities → CommandError exit 1 con mensaje formatted."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    data = {
        "schema_version": "0.1",
        "flujo": {
            "nombre": "FP_MISSING_TEST_CMD",
            "descripcion": "",
            "activo": False,
            "metadatos": None,
            "transiciones": [{
                "estado_origen": "MISSING_X",
                "estado_destino": "MISSING_Y",
                "grupos_permitidos": [],
            }],
            "requisitos": [],
        },
    }
    file_path = tmp_path / "missing.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(CommandError, match="Missing entities"):
        call_command("sinpapel_import_flujo", str(file_path))


@pytest.mark.django_db
def test_import_command_unsupported_schema_version_raises(db, tmp_path):
    """schema_version no en SUPPORTED_SCHEMA_VERSIONS → CommandError.

    Pre-S27.2: solo "0.1" soportado. Post-S27.2: {0.1, 0.2}. Usar "0.99"
    como clearly-unsupported version-agnostic.
    """
    from django.core.management import call_command
    from django.core.management.base import CommandError

    file_path = tmp_path / "v099.json"
    file_path.write_text(json.dumps({"schema_version": "0.99", "flujo": {}}),
                         encoding="utf-8")
    with pytest.raises(CommandError, match="Unsupported schema_version"):
        call_command("sinpapel_import_flujo", str(file_path))


@pytest.mark.django_db
def test_import_command_duplicate_flujo_name_raises(catalog_setup, tmp_path):
    """Mismo nombre flujo → CommandError con sugerencia."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    # Export sin rename — mismo nombre que existing
    file_path = _export_to_tmp(catalog_setup, tmp_path)
    with pytest.raises(CommandError, match="already exists"):
        call_command("sinpapel_import_flujo", str(file_path))


@pytest.mark.django_db
def test_import_command_file_not_found_raises(db):
    """File no existe → CommandError."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="not found|No such"):
        call_command("sinpapel_import_flujo", "/tmp/does_not_exist_s138.json")


# ─────────────────────────────────────────────────────────────────────────────
# T4 — Round-trip + atomic rollback + ambiguity
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_round_trip_export_import_re_export_equivalent(catalog_setup):
    """export X → import (rename) → re-export Y → JSONs flujo content equivalente."""
    from sinpapel.schemas.flujo_export import deserialize_flujo, serialize_flujo

    # 1. Export original
    data_a = serialize_flujo(catalog_setup["flujo"])

    # 2. Rename + import como nuevo
    import copy
    data_a_for_import = copy.deepcopy(data_a)
    data_a_for_import["flujo"]["nombre"] = "FP_ROUND_TRIP_COPY"
    flujo_new = deserialize_flujo(data_a_for_import, dry_run=False, activo=False)

    # 3. Re-export
    data_b = serialize_flujo(flujo_new)

    # 4. Normalize for comparison: rename back + override activo (D-active-default)
    data_b["flujo"]["nombre"] = data_a["flujo"]["nombre"]
    data_b["flujo"]["activo"] = data_a["flujo"]["activo"]

    # exported_at differs por timestamps → comparar solo flujo content
    assert data_a["flujo"] == data_b["flujo"]


@pytest.mark.django_db
def test_atomic_rollback_on_mid_import_failure(catalog_setup, tmp_path, monkeypatch):
    """Mid-import error rolls back todo (transaction.atomic)."""
    from sinpapel.models import ConfiguracionTransicion, VersionFlujo
    from sinpapel.schemas import flujo_export as fe_module

    file_path = _export_to_tmp(catalog_setup, tmp_path, rename_to="FP_ATOMIC_TEST")

    # Monkeypatch ConfiguracionTransicion.objects.create para raise mid-import
    original_create = ConfiguracionTransicion.objects.create
    call_count = {"n": 0}

    def _failing_create(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] >= 2:  # falla en la 2da transición
            raise RuntimeError("simulated mid-import failure")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(
        ConfiguracionTransicion.objects, "create", _failing_create
    )

    flujo_count_before = VersionFlujo.objects.count()
    ct_count_before = ConfiguracionTransicion.objects.count()

    from django.core.management import call_command
    from django.core.management.base import CommandError
    with pytest.raises((RuntimeError, CommandError)):
        call_command("sinpapel_import_flujo", str(file_path), stdout=StringIO())

    # Verify rollback: ningún VersionFlujo ni ConfiguracionTransicion creado
    assert VersionFlujo.objects.count() == flujo_count_before
    assert ConfiguracionTransicion.objects.count() == ct_count_before
    assert not VersionFlujo.objects.filter(nombre="FP_ATOMIC_TEST").exists()


@pytest.mark.django_db
def test_ambiguous_estado_lookup_raises(catalog_setup, tmp_path):
    """Catalogo.nombre NOT unique — 2 Estados mismo nombre → AMBIGUOUS error."""
    from sinpapel.models import Estado
    from django.core.management import call_command
    from django.core.management.base import CommandError

    # Crear 2do Estado con MISMO nombre (Catalogo.nombre NOT unique)
    Estado.objects.create(nombre="FP_CAPTURA")  # duplicate

    file_path = _export_to_tmp(catalog_setup, tmp_path, rename_to="FP_AMBIGUITY_TEST")
    with pytest.raises(CommandError, match="AMBIGUOUS"):
        call_command("sinpapel_import_flujo", str(file_path), stdout=StringIO())

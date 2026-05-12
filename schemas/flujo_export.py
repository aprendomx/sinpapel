"""Sinpapel — Flow portability schema (S13.8).

Schema v0.1: VersionFlujo + ConfiguracionTransicion + RequisitoEstadoDocumento
serializados con FK externos por nombre (Estado/TipoDocumento/Group). PKs
auto-regenerated en import — no preservación cross-environment.

Decisiones (ver s13.8-design.md §3):
- D-schema-fields: solo fields que existen actualmente. firma_requerida,
  obligatorio, orden NO existen → omitidos. Schema fiel a model real.
- D-no-historicalrecords: history NO en export (entorno-specific).
- D-no-creado-por: User IDs NO portables.
- D-ambiguity-lookup: nombre lookup retorna >1 → reject AMBIGUOUS explícito
  (Catalogo.nombre NOT unique constraint).
- D-duplicate-import-policy: VersionFlujo nombre existente → reject explícito.
- D-id-strategy: PKs siempre auto-generated.
- D-atomicity: @transaction.atomic wrap deserialize_flujo.
- D-active-default: import activo=False default; --activo override.
- D-schema-version-policy: strict equality "0.1" pre-1.0.

PAT-E-523: missing entities → reject explícito, never silent skip.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from sinpapel.models import VersionFlujo

SCHEMA_VERSION = "0.1"  # default emitido por serialize_flujo() backward-compat
SCHEMA_VERSION_LATEST = "0.2"  # S27.2 (ADR-017): emitido por serialize_flujo(inline_catalogs=True)
SUPPORTED_SCHEMA_VERSIONS = frozenset({"0.1", "0.2"})


def serialize_flujo(flujo: "VersionFlujo") -> dict:
    """Serializa VersionFlujo + transitions + requisitos a dict schema v0.1.

    FK externos por nombre. M2M grupos_permitidos sorted para determinism.
    Requisitos incluyen los referidos por Estados involucrados en transitions.
    """
    from sinpapel.models import RequisitoEstadoDocumento

    transitions = [
        {
            "estado_origen": t.estado_origen.nombre,
            "estado_destino": t.estado_destino.nombre,
            "grupos_permitidos": sorted(
                t.grupos_permitidos.values_list("name", flat=True)
            ),
        }
        for t in flujo.transiciones.all()
        .select_related("estado_origen", "estado_destino")
        .prefetch_related("grupos_permitidos")
        .order_by("estado_origen__nombre", "estado_destino__nombre")
    ]

    estados_ids = set()
    for t in flujo.transiciones.all().values("estado_origen_id", "estado_destino_id"):
        estados_ids.add(t["estado_origen_id"])
        estados_ids.add(t["estado_destino_id"])

    requisitos = [
        {
            "estado": r.estado.nombre,
            "tipo_documento": r.tipo_documento.nombre,
            "porcentaje": r.porcentaje,
            "auto_carga": r.auto_carga,
        }
        for r in RequisitoEstadoDocumento.objects.filter(estado_id__in=estados_ids)
        .select_related("estado", "tipo_documento")
        .order_by("estado__nombre", "tipo_documento__nombre")
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "flujo": {
            "nombre": flujo.nombre,
            "descripcion": flujo.descripcion or "",
            "activo": flujo.activo,
            "metadatos": flujo.metadatos,
            "transiciones": transitions,
            "requisitos": requisitos,
        },
    }


def validate_schema_version(data: dict) -> None:
    """Reject si schema_version no está en SUPPORTED_SCHEMA_VERSIONS.

    Forward-compat strict pre-1.0: solo versiones explícitamente soportadas.
    S27.2 (ADR-017): añade v0.2 con backward-compat v0.1.
    """
    version = data.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = sorted(SUPPORTED_SCHEMA_VERSIONS)
        raise ValueError(
            f"Unsupported schema_version='{version}'. "
            f"This sinpapel knows {supported}. "
            f"Upgrade sinpapel package or downgrade source schema."
        )


def find_missing_entities(data: dict) -> dict[str, list[str]]:
    """Returns {Estado, TipoDocumento, Group: [...]} con missing names sorted.

    PAT-E-523: pre-validation explícita ANTES de import — sysadmin sabe qué falta.
    """
    from django.contrib.auth.models import Group
    from sinpapel.models import Estado, TipoDocumento

    flujo_data = data["flujo"]
    estado_names: set[str] = set()
    for t in flujo_data["transiciones"]:
        estado_names.add(t["estado_origen"])
        estado_names.add(t["estado_destino"])
    for r in flujo_data["requisitos"]:
        estado_names.add(r["estado"])

    tipo_names = {r["tipo_documento"] for r in flujo_data["requisitos"]}

    group_names: set[str] = set()
    for t in flujo_data["transiciones"]:
        group_names.update(t["grupos_permitidos"])

    existing_estados = set(
        Estado.objects.filter(nombre__in=estado_names).values_list("nombre", flat=True)
    )
    existing_tipos = set(
        TipoDocumento.objects.filter(nombre__in=tipo_names).values_list("nombre", flat=True)
    )
    existing_groups = set(
        Group.objects.filter(name__in=group_names).values_list("name", flat=True)
    )

    return {
        "Estado": sorted(estado_names - existing_estados),
        "TipoDocumento": sorted(tipo_names - existing_tipos),
        "Group": sorted(group_names - existing_groups),
    }


@transaction.atomic
def deserialize_flujo(
    data: dict, *, dry_run: bool = False, activo: bool = False
) -> "VersionFlujo | None":
    """Crea VersionFlujo + transitions + requisitos atomicamente.

    Pre-validations (reject-on-missing antes de cualquier write):
    1. validate_schema_version
    2. find_missing_entities → raise si algo missing
    3. ambiguity check (Catalogo.nombre NOT unique → reject si >1 match)
    4. duplicate flujo check (mismo nombre existing → reject)

    Si dry_run=True → retorna None sin persistir.
    Si dry_run=False → crea entities y retorna VersionFlujo.
    """
    from django.contrib.auth.models import Group
    from sinpapel.models import (
        ConfiguracionTransicion,
        Estado,
        RequisitoEstadoDocumento,
        TipoDocumento,
        VersionFlujo,
    )

    validate_schema_version(data)
    flujo_data = data["flujo"]

    # 1. Missing entities check (PAT-E-523)
    missing = find_missing_entities(data)
    if any(missing.values()):
        raise ValueError(_format_missing_error(missing))

    # 2. Duplicate flujo nombre check
    if VersionFlujo.objects.filter(nombre=flujo_data["nombre"]).exists():
        raise ValueError(
            f"VersionFlujo '{flujo_data['nombre']}' already exists. "
            f"Rename in JSON or delete existing first."
        )

    # 3. Ambiguity check (Catalogo.nombre NOT unique)
    estado_names = {t["estado_origen"] for t in flujo_data["transiciones"]} | \
                   {t["estado_destino"] for t in flujo_data["transiciones"]} | \
                   {r["estado"] for r in flujo_data["requisitos"]}
    for name in estado_names:
        if Estado.objects.filter(nombre=name).count() > 1:
            raise ValueError(
                f"AMBIGUOUS: multiple Estados named '{name}' in destination. "
                f"Rename or de-dup in destination, retry."
            )
    tipo_names = {r["tipo_documento"] for r in flujo_data["requisitos"]}
    for name in tipo_names:
        if TipoDocumento.objects.filter(nombre=name).count() > 1:
            raise ValueError(
                f"AMBIGUOUS: multiple TipoDocumento named '{name}'. "
                f"Rename or de-dup in destination, retry."
            )

    if dry_run:
        return None

    # 4. Persist atomicamente (transaction.atomic wraps todo)
    flujo = VersionFlujo.objects.create(
        nombre=flujo_data["nombre"],
        descripcion=flujo_data.get("descripcion", ""),
        activo=activo,
        metadatos=flujo_data.get("metadatos"),
    )

    # Lookup maps (single query each)
    estado_lookup = {
        e.nombre: e for e in Estado.objects.filter(nombre__in=estado_names)
    }
    tipo_lookup = {
        t.nombre: t for t in TipoDocumento.objects.filter(nombre__in=tipo_names)
    }

    for t_data in flujo_data["transiciones"]:
        ct = ConfiguracionTransicion.objects.create(
            flujo=flujo,
            estado_origen=estado_lookup[t_data["estado_origen"]],
            estado_destino=estado_lookup[t_data["estado_destino"]],
        )
        for group_name in t_data["grupos_permitidos"]:
            ct.grupos_permitidos.add(Group.objects.get(name=group_name))

    # D-requisitos-shared-catalog: RequisitoEstadoDocumento tiene
    # unique_together (estado, tipo_documento) — shared catalog state, NOT
    # flujo-specific. Use get_or_create: si exists, preservar valores actuales
    # (no sobre-escribir config del destino). Si new, crear con imported values.
    for r_data in flujo_data["requisitos"]:
        RequisitoEstadoDocumento.objects.get_or_create(
            estado=estado_lookup[r_data["estado"]],
            tipo_documento=tipo_lookup[r_data["tipo_documento"]],
            defaults={
                "porcentaje": r_data.get("porcentaje", 100),
                "auto_carga": r_data.get("auto_carga", False),
            },
        )

    return flujo


def _format_missing_error(missing: dict[str, list[str]]) -> str:
    lines = ["Missing entities in destination:"]
    for kind, names in missing.items():
        if names:
            lines.append(f"  - {kind}: {names}")
    total = sum(len(names) for names in missing.values())
    lines.append("")
    lines.append(f"Total missing: {total} entities")
    lines.append("Action required: create them in destination, then retry import.")
    return "\n".join(lines)

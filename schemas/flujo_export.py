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
import logging
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from sinpapel.models import VersionFlujo

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "0.1"  # default emitido por serialize_flujo() backward-compat
SCHEMA_VERSION_LATEST = "0.2"  # S27.2 (ADR-017): emitido por serialize_flujo(inline_catalogs=True)
SUPPORTED_SCHEMA_VERSIONS = frozenset({"0.1", "0.2"})


def serialize_flujo(flujo: "VersionFlujo", *, inline_catalogs: bool = False) -> dict:
    """Serializa VersionFlujo + transitions + requisitos.

    Args:
        flujo: VersionFlujo a serializar.
        inline_catalogs: si True, emite v0.2 con sección 'catalogos' inline
            (Estado, Etapa, Group, TipoDocumento referenciados por el flujo)
            y metadatos.positions name-keyed. Si False (default), emite v0.1 —
            referencias por nombre, catálogos asumidos en destino (backward-
            compat S13.8).

    Returns:
        dict serializable a JSON:
        - v0.1: {schema_version, exported_at, flujo: {...}}
        - v0.2: {schema_version, exported_at, catalogos: {...}, flujo: {...}}
    """
    from sinpapel.models import RequisitoEstadoDocumento

    transitions = []
    for t in (
        flujo.transiciones.all()
        .select_related("estado_origen", "estado_destino")
        .prefetch_related("grupos_permitidos", "condiciones")
        .order_by("estado_origen__nombre", "estado_destino__nombre")
    ):
        t_data = {
            "estado_origen": t.estado_origen.nombre,
            "estado_destino": t.estado_destino.nombre,
            "grupos_permitidos": sorted(
                t.grupos_permitidos.values_list("name", flat=True)
            ),
        }
        condiciones = [
            {
                "tipo": c.tipo,
                "configuracion": c.configuracion,
                "mensaje_error": c.mensaje_error,
                "orden": c.orden,
                "activo": c.activo,
            }
            for c in t.condiciones.all().order_by("orden")
        ]
        if condiciones:
            t_data["condiciones"] = condiciones
        transitions.append(t_data)

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

    # v0.2: convertir positions a name-keying (designer no conoce IDs)
    if inline_catalogs and flujo.metadatos and "positions" in flujo.metadatos:
        metadatos = {
            **flujo.metadatos,
            "positions": _positions_to_names(flujo.metadatos["positions"], flujo),
        }
    else:
        metadatos = flujo.metadatos

    schema_version = SCHEMA_VERSION_LATEST if inline_catalogs else SCHEMA_VERSION
    result: dict = {
        "schema_version": schema_version,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if inline_catalogs:
        result["catalogos"] = _serialize_catalogos(flujo)
    result["flujo"] = {
        "nombre": flujo.nombre,
        "descripcion": flujo.descripcion or "",
        "activo": flujo.activo,
        "metadatos": metadatos,
        "transiciones": transitions,
        "requisitos": requisitos,
    }
    return result


def _positions_to_names(
    positions: dict | None, flujo: "VersionFlujo"  # noqa: ARG001
) -> dict | None:
    """Migra positions keying de ID -> nombre para v0.2 export.

    Si positions es None o vacío, retorna as-is.
    Si todas las keys son numéricas (legacy v0.1 creditos), lookup
    Estado.objects.get(pk=...) y convierte a name-keyed.
    Si keys ya son nombres, retorna as-is (idempotent).
    Estados not found en DB se omiten silently (drop preferred sobre crash).
    """
    if not positions:
        return positions

    if not all(isinstance(k, str) and k.isdigit() for k in positions.keys()):
        return positions  # ya name-keyed o mixed (skip migration)

    from sinpapel.models import Estado

    ids = [int(k) for k in positions.keys()]
    id_to_nombre = {e.id: e.nombre for e in Estado.objects.filter(pk__in=ids)}
    return {
        id_to_nombre[int(id_str)]: pos
        for id_str, pos in positions.items()
        if int(id_str) in id_to_nombre
    }


def _serialize_catalogos(flujo: "VersionFlujo") -> dict:
    """Extrae Estados/Etapas/Grupos/TiposDocumento referenciados por flujo + requisitos.

    Subset (no todos los catálogos del DB). Ordenado por nombre deterministicamente
    para round-trip equivalence.
    """
    from django.contrib.auth.models import Group
    from sinpapel.models import Estado, Etapa, RequisitoEstadoDocumento, TipoDocumento

    estado_names: set[str] = set()
    group_names: set[str] = set()

    for t in (
        flujo.transiciones.all()
        .select_related("estado_origen", "estado_destino")
        .prefetch_related("grupos_permitidos")
    ):
        estado_names.add(t.estado_origen.nombre)
        estado_names.add(t.estado_destino.nombre)
        for g in t.grupos_permitidos.all():
            group_names.add(g.name)

    estados_qs = Estado.objects.filter(nombre__in=estado_names).select_related("etapa")

    requisitos_qs = RequisitoEstadoDocumento.objects.filter(
        estado__in=estados_qs
    ).select_related("tipo_documento")
    tipo_names = {r.tipo_documento.nombre for r in requisitos_qs}

    estados_data = []
    etapa_names: set[str] = set()
    for e in estados_qs.order_by("nombre").prefetch_related("slas"):
        etapa_nombre = e.etapa.nombre if e.etapa else None
        if etapa_nombre:
            etapa_names.add(etapa_nombre)
        estado_data: dict = {
            "nombre": e.nombre,
            "color": e.color,
            "icono": e.icono,
            "descripcion": e.descripcion or "",
            "orden": e.orden,
            "activo": e.activo,
            "etapa": etapa_nombre,
            "permite_expediente": e.permite_expediente,
            "expediente_obligatorio": e.expediente_obligatorio,
        }
        slas = [
            {
                "dias_maximos": s.dias_maximos,
                "accion_vencimiento": s.accion_vencimiento,
                "configuracion_accion": s.configuracion_accion,
                "activo": s.activo,
            }
            for s in e.slas.all().order_by("accion_vencimiento")
        ]
        if slas:
            estado_data["slas"] = slas
        estados_data.append(estado_data)

    etapas_data = [
        {
            "nombre": etapa.nombre,
            "color": etapa.color,
            "descripcion": etapa.descripcion or "",
            "orden": etapa.orden,
            "activo": etapa.activo,
        }
        for etapa in Etapa.objects.filter(nombre__in=etapa_names).order_by("nombre")
    ]

    tipos_data = [
        {
            "nombre": td.nombre,
            "color": td.color,
            "descripcion": td.descripcion or "",
            "orden": td.orden,
            "activo": td.activo,
        }
        for td in TipoDocumento.objects.filter(nombre__in=tipo_names).order_by("nombre")
    ]

    grupos_data = [
        {"name": g.name}
        for g in Group.objects.filter(name__in=group_names).order_by("name")
    ]

    return {
        "estados": estados_data,
        "etapas": etapas_data,
        "grupos": grupos_data,
        "tipos_documento": tipos_data,
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
    data: dict,
    *,
    dry_run: bool = False,
    activo: bool = False,
    create_catalogs: bool = True,
) -> "VersionFlujo | None":
    """Crea VersionFlujo + transitions + requisitos atomicamente.

    Args:
        data: dict en schema v0.1 o v0.2 (validate_schema_version).
        dry_run: si True, retorna None sin persistir.
        activo: setea VersionFlujo.activo (default False, defensive).
        create_catalogs: solo aplica a v0.2. Si True (default), upsert
            inline catalogos antes de procesar flujo. Si False, comporta
            como v0.1 — rely en destino, reject si missing.

    Pre-validations (reject-on-missing antes de cualquier write):
    1. validate_schema_version
    2. Si v0.2 + create_catalogs=True: upsert catalogos
       Else: find_missing_entities → raise si algo missing
    3. ambiguity check (Catalogo.nombre NOT unique → reject si >1 match)
    4. duplicate flujo check (mismo nombre existing → reject)

    Si dry_run=True → retorna None sin persistir.
    Si dry_run=False → crea entities y retorna VersionFlujo.
    """
    from django.contrib.auth.models import Group
    from sinpapel.models import (
        CondicionTransicion,
        ConfiguracionTransicion,
        Estado,
        RequisitoEstadoDocumento,
        TipoDocumento,
        VersionFlujo,
    )

    validate_schema_version(data)
    flujo_data = data["flujo"]

    # S27.2: v0.2 + create_catalogs=True → upsert inline catalogos primero
    # (ambiguity check se delega a _upsert_catalogos, ya que valida
    # multiple matches via Catalogo.nombre NOT unique)
    is_v0_2_inline = (
        data.get("schema_version") == SCHEMA_VERSION_LATEST
        and "catalogos" in data
        and create_catalogs
    )

    if is_v0_2_inline:
        _upsert_catalogos(data["catalogos"])
    else:
        # 1. Missing entities check (PAT-E-523) — v0.1 path o v0.2 opt-out
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
        # S27.3 fix: v0.2 + create_catalogs path writes via _upsert_catalogos.
        # transaction.atomic commits al exit si no raise — explicit rollback
        # garantiza dry-run zero-writes contract.
        transaction.set_rollback(True)
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
        for c_data in t_data.get("condiciones", []):
            CondicionTransicion.objects.create(
                transicion=ct,
                tipo=c_data["tipo"],
                configuracion=c_data.get("configuracion", {}),
                mensaje_error=c_data.get("mensaje_error", "No cumple con las condiciones requeridas."),
                orden=c_data.get("orden", 0),
                activo=c_data.get("activo", True),
            )

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


# ─────────────────────────────────────────────────────────────────────────────
# S27.2 — Upsert helpers para v0.2 inline catalogos
# ─────────────────────────────────────────────────────────────────────────────


def _upsert_catalogos(catalogos: dict) -> None:
    """Upsert Etapas → Estados → TipoDocumento → Group (FK order D7).

    Args:
        catalogos: dict con keys 'etapas', 'estados', 'tipos_documento', 'grupos'
            (todos opcionales — sections vacías son OK).

    Side-effects:
        - Crea entities missing por natural key (nombre/name).
        - Actualiza entities existentes con defaults distintos + emit WARNING.
        - Ambiguity (>1 match por nombre) → raise PAT-E-523.

    Raises:
        ValueError: si Catalogo.nombre NOT unique constraint genera >1 match.
    """
    for etapa_data in catalogos.get("etapas", []):
        _upsert_etapa(etapa_data)
    for estado_data in catalogos.get("estados", []):
        _upsert_estado(estado_data)
    for tipo_data in catalogos.get("tipos_documento", []):
        _upsert_tipo_documento(tipo_data)
    for grupo_data in catalogos.get("grupos", []):
        _upsert_grupo(grupo_data)


def _check_ambiguity(model, nombre_field: str, nombre_value: str) -> None:
    """Reject si >1 match por nombre/name (PAT-E-523 preserved en upsert path)."""
    count = model.objects.filter(**{nombre_field: nombre_value}).count()
    if count > 1:
        raise ValueError(
            f"AMBIGUOUS: multiple {model.__name__} con {nombre_field}='{nombre_value}'. "
            f"Rename or de-dup en destino, retry."
        )


def _upsert_etapa(data: dict) -> None:
    from sinpapel.models import Etapa
    _check_ambiguity(Etapa, "nombre", data["nombre"])
    existing = Etapa.objects.filter(nombre=data["nombre"]).first()
    fields = {
        "color": data.get("color", "#4DEFE2"),
        "descripcion": data.get("descripcion", ""),
        "orden": data.get("orden", 0),
        "activo": data.get("activo", False),
    }
    if existing is None:
        Etapa.objects.create(nombre=data["nombre"], **fields)
        return
    changed = {
        f: (getattr(existing, f), v) for f, v in fields.items() if getattr(existing, f) != v
    }
    if changed:
        logger.warning(f"Updating Etapa '{data['nombre']}' inline: {list(changed.keys())}")
        for f, (_, new) in changed.items():
            setattr(existing, f, new)
        existing.save()


def _upsert_estado(data: dict) -> None:
    from sinpapel.models import Estado, Etapa
    _check_ambiguity(Estado, "nombre", data["nombre"])
    etapa_nombre = data.get("etapa")
    etapa = None
    if etapa_nombre:
        _check_ambiguity(Etapa, "nombre", etapa_nombre)
        etapa = Etapa.objects.filter(nombre=etapa_nombre).first()
        if etapa is None:
            raise ValueError(
                f"Estado '{data['nombre']}' refers to Etapa '{etapa_nombre}' "
                f"not found in destination. Include in catalogos.etapas inline."
            )
    existing = Estado.objects.filter(nombre=data["nombre"]).first()
    fields = {
        "color": data.get("color", "#4DEFE2"),
        "icono": data.get("icono", "circle"),
        "descripcion": data.get("descripcion", ""),
        "orden": data.get("orden", 0),
        "activo": data.get("activo", False),
        "etapa": etapa,
        "permite_expediente": data.get("permite_expediente", False),
        "expediente_obligatorio": data.get("expediente_obligatorio", False),
    }
    if existing is None:
        estado = Estado.objects.create(nombre=data["nombre"], **fields)
    else:
        changed = {
            f: (getattr(existing, f), v) for f, v in fields.items() if getattr(existing, f) != v
        }
        if changed:
            logger.warning(f"Updating Estado '{data['nombre']}' inline: {list(changed.keys())}")
            for f, (_, new) in changed.items():
                setattr(existing, f, new)
            existing.save()
        estado = existing

    # Upsert SLAs (unique together: estado + accion_vencimiento)
    from sinpapel.models.sla import SLAConfiguracion
    for sla_data in data.get("slas", []):
        SLAConfiguracion.objects.update_or_create(
            estado=estado,
            accion_vencimiento=sla_data["accion_vencimiento"],
            defaults={
                "dias_maximos": sla_data.get("dias_maximos", 0),
                "configuracion_accion": sla_data.get("configuracion_accion", {}),
                "activo": sla_data.get("activo", True),
            },
        )


def _upsert_tipo_documento(data: dict) -> None:
    from sinpapel.models import TipoDocumento
    _check_ambiguity(TipoDocumento, "nombre", data["nombre"])
    existing = TipoDocumento.objects.filter(nombre=data["nombre"]).first()
    fields = {
        "color": data.get("color", "#4DEFE2"),
        "descripcion": data.get("descripcion", ""),
        "orden": data.get("orden", 0),
        "activo": data.get("activo", False),
    }
    if existing is None:
        TipoDocumento.objects.create(nombre=data["nombre"], **fields)
        return
    changed = {
        f: (getattr(existing, f), v) for f, v in fields.items() if getattr(existing, f) != v
    }
    if changed:
        logger.warning(
            f"Updating TipoDocumento '{data['nombre']}' inline: {list(changed.keys())}"
        )
        for f, (_, new) in changed.items():
            setattr(existing, f, new)
        existing.save()


def _upsert_grupo(data: dict) -> None:
    from django.contrib.auth.models import Group
    # auth Group: name unique constraint enforced by Django (no _check_ambiguity needed)
    Group.objects.get_or_create(name=data["name"])

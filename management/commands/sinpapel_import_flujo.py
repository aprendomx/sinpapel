"""S13.8 + S27.3 — manage.py sinpapel_import_flujo <FILE> [--dry-run] [--activo] [--no-create-catalogs].

Importa VersionFlujo + transitions + requisitos desde JSON portable
(schema v0.1 + v0.2). FK externos por nombre (Estado, TipoDocumento, Group).

S27.3 (ADR-017): v0.2 con sección 'catalogos' inline → upsert default
(--no-create-catalogs para opt-out a v0.1 semantics).

PAT-E-523 reject explícito si:
- Missing entities en destination (v0.1 o v0.2 + --no-create-catalogs)
- VersionFlujo nombre duplicado
- Schema_version no en SUPPORTED_SCHEMA_VERSIONS
- Estado/TipoDocumento ambiguity (Catalogo.nombre NOT unique)

Defensive default: activo=False. --activo flag override.

Usage:
    python manage.py sinpapel_import_flujo flujo.json                    # v0.1 o v0.2 default
    python manage.py sinpapel_import_flujo flujo.json --dry-run
    python manage.py sinpapel_import_flujo flujo.json --activo
    python manage.py sinpapel_import_flujo flujo.json --no-create-catalogs  # v0.2 opt-out
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from sinpapel.schemas.flujo_export import deserialize_flujo


class Command(BaseCommand):
    help = "Import VersionFlujo from JSON (schema v0.1 + v0.2, --no-create-catalogs for v0.2 opt-out)"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path al archivo JSON")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Validate without persisting",
        )
        parser.add_argument(
            "--activo", action="store_true",
            help="Override safe default activo=False",
        )
        parser.add_argument(
            "--no-create-catalogs", action="store_true",
            help="v0.2 opt-out: rely en destino, reject if missing entities (v0.1 semantics).",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        try:
            with open(file_path, encoding="utf-8") as fp:
                data = json.load(fp)
        except FileNotFoundError as exc:
            raise CommandError(f"File not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {file_path}: {exc}") from exc

        dry_run = options.get("dry_run", False)
        activo = options.get("activo", False)
        create_catalogs = not options.get("no_create_catalogs", False)

        try:
            flujo = deserialize_flujo(
                data, dry_run=dry_run, activo=activo,
                create_catalogs=create_catalogs,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        flujo_data = data.get("flujo", {})
        version = data.get("schema_version", "0.1")
        n_transiciones = len(flujo_data.get("transiciones", []))
        n_requisitos = len(flujo_data.get("requisitos", []))

        # v0.2 + create_catalogs → contar per-type inline catalogos (Q1 plan resolution)
        inline_catalogs_msg = ""
        if version == "0.2" and create_catalogs:
            cat = data.get("catalogos", {})
            inline_catalogs_msg = (
                f" Inline catalogos: "
                f"{len(cat.get('estados', []))} Estados, "
                f"{len(cat.get('etapas', []))} Etapas, "
                f"{len(cat.get('grupos', []))} Grupos, "
                f"{len(cat.get('tipos_documento', []))} TiposDocumento."
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"DRY-RUN OK: would import VersionFlujo "
                f"'{flujo_data.get('nombre', '?')}' "
                f"(schema v{version}): "
                f"{n_transiciones} transiciones, {n_requisitos} requisitos.{inline_catalogs_msg}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Imported VersionFlujo '{flujo.nombre}' (id={flujo.pk}, schema v{version}): "
                f"{n_transiciones} transiciones, {n_requisitos} requisitos.{inline_catalogs_msg}"
            ))

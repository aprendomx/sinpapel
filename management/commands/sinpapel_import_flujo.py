"""S13.8 — manage.py sinpapel_import_flujo <FILE> [--dry-run] [--activo].

Importa VersionFlujo + transitions + requisitos desde JSON portable
(schema v0.1). FK externos por nombre (Estado, TipoDocumento, Group).

PAT-E-523 reject explícito si:
- Missing entities en destination
- VersionFlujo nombre duplicado
- Schema_version > current
- Estado/TipoDocumento ambiguity (Catalogo.nombre NOT unique)

Defensive default: activo=False. --activo flag override.

Usage:
    python manage.py sinpapel_import_flujo flujo.json
    python manage.py sinpapel_import_flujo flujo.json --dry-run
    python manage.py sinpapel_import_flujo flujo.json --activo
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from sinpapel.schemas.flujo_export import deserialize_flujo


class Command(BaseCommand):
    help = "Import VersionFlujo from JSON (schema v0.1)"

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

        try:
            flujo = deserialize_flujo(data, dry_run=dry_run, activo=activo)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        flujo_data = data.get("flujo", {})
        n_transiciones = len(flujo_data.get("transiciones", []))
        n_requisitos = len(flujo_data.get("requisitos", []))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"DRY-RUN OK: would import VersionFlujo "
                f"'{flujo_data.get('nombre', '?')}' "
                f"({n_transiciones} transiciones, {n_requisitos} requisitos)"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Imported VersionFlujo '{flujo.nombre}' (id={flujo.pk}): "
                f"{n_transiciones} transiciones, {n_requisitos} requisitos"
            ))

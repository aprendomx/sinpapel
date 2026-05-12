"""S13.8 + S27.3 — manage.py sinpapel_export_flujo <id> [--inline-catalogs] [--output FILE].

Exporta VersionFlujo + transitions + requisitos a JSON portable
(schema v0.1 + v0.2) con FK externos por nombre.

S27.3 (ADR-017): --inline-catalogs emite v0.2 con Estados/Etapas/Group/
TipoDocumento embebidos + metadatos.positions name-keyed.

Usage:
    python manage.py sinpapel_export_flujo 42                       # stdout v0.1
    python manage.py sinpapel_export_flujo 42 --inline-catalogs     # stdout v0.2
    python manage.py sinpapel_export_flujo 42 --output flujo.json
    python manage.py sinpapel_export_flujo 42 --inline-catalogs --output flujo_v2.json
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from sinpapel.models import VersionFlujo
from sinpapel.schemas.flujo_export import serialize_flujo


class Command(BaseCommand):
    help = "Export VersionFlujo to portable JSON (schema v0.1 default, --inline-catalogs for v0.2)"

    def add_arguments(self, parser):
        parser.add_argument(
            "flujo_id", type=int, help="ID del VersionFlujo a exportar"
        )
        parser.add_argument(
            "--output", type=str, default=None,
            help="Output file path (default: stdout)",
        )
        parser.add_argument(
            "--inline-catalogs", action="store_true",
            help="Emit schema v0.2 with inline catalogos (Estados/Etapas/Group/TipoDocumento) for designer round-trip.",
        )

    def handle(self, *args, **options):
        try:
            flujo = VersionFlujo.objects.get(pk=options["flujo_id"])
        except VersionFlujo.DoesNotExist as exc:
            raise CommandError(
                f"VersionFlujo with id={options['flujo_id']} does not exist"
            ) from exc

        inline_catalogs = options.get("inline_catalogs", False)
        data = serialize_flujo(flujo, inline_catalogs=inline_catalogs)
        text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)

        output = options.get("output")
        if output:
            with open(output, "w", encoding="utf-8") as fp:
                fp.write(text)
            self.stdout.write(self.style.SUCCESS(
                f"Exported VersionFlujo '{flujo.nombre}' "
                f"(id={flujo.pk}, schema v{data['schema_version']}) to {output}"
            ))
        else:
            self.stdout.write(text)

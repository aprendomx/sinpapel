"""S13.8 — manage.py sinpapel_export_flujo <id> [--output FILE].

Exporta VersionFlujo + transitions + requisitos a JSON portable
(schema v0.1) con FK externos por nombre.

Usage:
    python manage.py sinpapel_export_flujo 42                    # stdout
    python manage.py sinpapel_export_flujo 42 --output flujo.json
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from sinpapel.models import VersionFlujo
from sinpapel.schemas.flujo_export import serialize_flujo


class Command(BaseCommand):
    help = "Export VersionFlujo to portable JSON (schema v0.1)"

    def add_arguments(self, parser):
        parser.add_argument(
            "flujo_id", type=int, help="ID del VersionFlujo a exportar"
        )
        parser.add_argument(
            "--output", type=str, default=None,
            help="Output file path (default: stdout)",
        )

    def handle(self, *args, **options):
        try:
            flujo = VersionFlujo.objects.get(pk=options["flujo_id"])
        except VersionFlujo.DoesNotExist as exc:
            raise CommandError(
                f"VersionFlujo with id={options['flujo_id']} does not exist"
            ) from exc

        data = serialize_flujo(flujo)
        text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)

        output = options.get("output")
        if output:
            with open(output, "w", encoding="utf-8") as fp:
                fp.write(text)
            self.stdout.write(self.style.SUCCESS(
                f"Exported VersionFlujo '{flujo.nombre}' (id={flujo.pk}) to {output}"
            ))
        else:
            self.stdout.write(text)

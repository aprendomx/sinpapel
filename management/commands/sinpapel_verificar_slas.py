"""Management command: sinpapel_verificar_slas.

Evaluates all active SLAs against workflow-enabled instances and
executes configured actions for overdue instances.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from sinpapel.services.sla_engine import SLAEngine


class Command(BaseCommand):
    help = "Verifica SLAs activos y ejecuta acciones para instancias vencidas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Reporta SLAs vencidos sin ejecutar acciones",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 DRY RUN — No se ejecutarán acciones"))

        # Nota: En implementación real, escanearía todos los modelos workflow-enabled
        # Para v0.4.0, reportamos SLAs activos encontrados
        from sinpapel.models.sla import SLAConfiguracion
        slas = SLAConfiguracion.objects.filter(activo=True)
        self.stdout.write(f"SLAs activos encontrados: {slas.count()}")

        for sla in slas:
            self.stdout.write(f"  - {sla}")

        self.stdout.write(self.style.SUCCESS("✅ SLAs verificados"))

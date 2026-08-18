"""Management command: sinpapel_verificar_slas.

Evalúa todos los SLAs activos contra las instancias workflow-enabled
registradas y ejecuta las acciones configuradas para las vencidas.

Uso (cron de producción):
    python manage.py sinpapel_verificar_slas
    python manage.py sinpapel_verificar_slas --dry-run
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
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN — No se ejecutarán acciones")
            )

        from sinpapel.models.sla import SLAConfiguracion

        slas = SLAConfiguracion.objects.filter(activo=True)
        self.stdout.write(f"SLAs activos encontrados: {slas.count()}")
        for sla in slas:
            self.stdout.write(f"  - {sla}")

        conteo = SLAEngine.verificar_todos(dry_run=dry_run)
        if conteo:
            etiqueta = "Acciones por ejecutar" if dry_run else "Acciones ejecutadas"
            self.stdout.write(f"{etiqueta}:")
            for accion, n in sorted(conteo.items()):
                self.stdout.write(f"  - {accion}: {n}")
        else:
            self.stdout.write("Sin instancias vencidas.")

        self.stdout.write(self.style.SUCCESS("✅ SLAs verificados"))

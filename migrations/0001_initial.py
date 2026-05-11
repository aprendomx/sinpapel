"""S12.2/T1 — Walking skeleton: extraer RegistroFirma a sinpapel.

Registra el modelo RegistroFirma en el state de Django para la app sinpapel,
SIN tocar la tabla SQL `creditos_registrofirma` (sigue intacta vía
db_table override en el modelo).

Patrón clave: SeparateDatabaseAndState con database_operations=[].
Esto separa la modificación del state Django (CreateModel registra el modelo
en el migration history) de la del SQL (CREATE TABLE no se ejecuta porque
la tabla ya existe desde creditos).

Si este patrón funciona, T2 lo replica para los 12 modelos restantes.

ADR-006. Walking skeleton del paquete sinpapel.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("creditos", "0051_documento_remove_producto"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="RegistroFirma",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "backend_name",
                            models.CharField(
                                default="fiel",
                                help_text="Identificador del backend de firma (fiel, pades, docusign, manual, etc.)",
                                max_length=50,
                                verbose_name="Backend",
                            ),
                        ),
                        (
                            "backend_metadata",
                            models.JSONField(
                                blank=True,
                                default=dict,
                                help_text="Datos específicos del backend (FIEL: pkcs7, cert, rfc, serie; etc.)",
                                verbose_name="Metadata del Backend",
                            ),
                        ),
                        (
                            "signer_display_name",
                            models.CharField(
                                help_text="Nombre del firmante para visualización (puede no coincidir con User.get_full_name).",
                                max_length=255,
                                verbose_name="Nombre del Firmante",
                            ),
                        ),
                        (
                            "target_object_id",
                            models.PositiveIntegerField(
                                blank=True, null=True, verbose_name="ID de entidad firmada"
                            ),
                        ),
                        (
                            "content_hash",
                            models.CharField(
                                help_text="SHA-256 hex del payload canónico firmado",
                                max_length=128,
                                verbose_name="Hash del contenido firmado",
                            ),
                        ),
                        (
                            "is_required",
                            models.BooleanField(
                                default=False,
                                help_text="True si la transición exigía firma obligatoria",
                                verbose_name="¿Firma requerida?",
                            ),
                        ),
                        (
                            "verification_result",
                            models.CharField(
                                choices=[
                                    ("VALIDA", "Válida"),
                                    ("INVALIDA", "Inválida"),
                                    ("PENDIENTE", "Pendiente de verificación"),
                                ],
                                default="PENDIENTE",
                                max_length=10,
                                verbose_name="Resultado de validación",
                            ),
                        ),
                        (
                            "signed_at",
                            models.DateTimeField(
                                help_text="Momento en que se realizó la firma (según el cliente)",
                                verbose_name="Timestamp de firma",
                            ),
                        ),
                        (
                            "signer",
                            models.ForeignKey(
                                blank=True,
                                help_text="Usuario interno que firmó. NULL si la firma es externa.",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="firmas",
                                to="auth.user",
                                verbose_name="Firmante (User)",
                            ),
                        ),
                        (
                            "target_content_type",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="contenttypes.contenttype",
                                verbose_name="Tipo de entidad firmada",
                            ),
                        ),
                    ],
                    options={
                        # Preserva tabla SQL existente — extracción a sinpapel sin data migration
                        "db_table": "creditos_registrofirma",
                        "verbose_name": "Registro de Firma",
                        "verbose_name_plural": "Registros de Firma",
                        "indexes": [
                            models.Index(
                                fields=["target_content_type", "target_object_id"],
                                name="rf_target_idx",
                            ),
                            models.Index(
                                fields=["signer", "-signed_at"],
                                name="rf_signer_idx",
                            ),
                        ],
                    },
                ),
            ],
            database_operations=[],  # ← clave: tabla creditos_registrofirma ya existe
        ),
    ]

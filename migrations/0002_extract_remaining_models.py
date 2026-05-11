"""S12.2/T2 — Extraer 10 modelos restantes a sinpapel.

Pattern validado en T1: SeparateDatabaseAndState con database_operations=[]
preserva tablas SQL existentes (creditos_*) mientras registra los modelos
en sinpapel state.

Modelos extraídos:
- workflow: Estado, VersionFlujo, ConfiguracionTransicion, SeguimientoWorkflow,
  RequisitoEstadoDocumento
- documents: TipoDocumento, Documento, InstanciaDocumento, RazonRechazoDocumento
- attachments: ExpedienteAdjunto

Total: 10 modelos. Combinado con T1 (RegistroFirma) = 11 modelos en sinpapel.

HistorialRevisionDocumento y PlantillaDocumento permanecen en creditos
(tienen FKs a DocumentoSolicitud/ProductoCreditoFOVISSSTE creditos-específicos).
"""
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('sinpapel', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],  # ← clave: tablas creditos_* ya existen
            state_operations=[
            migrations.CreateModel(
                name='ConfiguracionTransicion',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ],
                options={
                    'verbose_name': 'Transición',
                    'verbose_name_plural': 'Transiciones',
                    'db_table': 'creditos_configuraciontransicion',
                },
            ),
            migrations.CreateModel(
                name='Documento',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('nombre', models.CharField(max_length=250)),
                    ('descripcion', models.TextField(blank=True, null=True)),
                    ('activo', models.BooleanField(default=False)),
                    ('color', models.CharField(default='#4DEFE2', max_length=25)),
                    ('orden', models.IntegerField(default=0)),
                    ('imagen', models.ImageField(blank=True, max_length=1000, null=True, upload_to='portadas/', verbose_name='Miniatura')),
                    ('metadatos', models.JSONField(blank=True, null=True)),
                    ('valor', models.CharField(max_length=100)),
                    ('contenido', models.TextField(blank=True, null=True)),
                    ('plantilla', models.FileField(blank=True, null=True, upload_to='plantillas/')),
                    ('tipo_plantilla', models.CharField(choices=[('DOCX', 'Word'), ('PDF', 'PDF')], default='DOCX', max_length=10, verbose_name='Tipo de Plantilla')),
                    ('configuracion_overlay', models.JSONField(blank=True, default=dict, help_text='Configuración de campos visibles y posiciones en el overlay PDF', null=True, verbose_name='Configuración de Overlay PDF')),
                ],
                options={
                    'verbose_name': 'Documento',
                    'verbose_name_plural': 'Documentos',
                    'db_table': 'creditos_documento',
                },
            ),
            migrations.CreateModel(
                name='Etapa',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('nombre', models.CharField(max_length=250)),
                    ('descripcion', models.TextField(blank=True, null=True)),
                    ('activo', models.BooleanField(default=False)),
                    ('color', models.CharField(default='#4DEFE2', max_length=25)),
                    ('orden', models.IntegerField(default=0)),
                    ('imagen', models.ImageField(blank=True, max_length=1000, null=True, upload_to='portadas/', verbose_name='Miniatura')),
                    ('metadatos', models.JSONField(blank=True, null=True)),
                ],
                options={
                    'verbose_name': 'Etapa',
                    'verbose_name_plural': 'Etapas',
                    'db_table': 'creditos_etapa',
                    'ordering': ['orden'],
                },
            ),
            migrations.CreateModel(
                name='Estado',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('nombre', models.CharField(max_length=250)),
                    ('descripcion', models.TextField(blank=True, null=True)),
                    ('activo', models.BooleanField(default=False)),
                    ('color', models.CharField(default='#4DEFE2', max_length=25)),
                    ('orden', models.IntegerField(default=0)),
                    ('imagen', models.ImageField(blank=True, max_length=1000, null=True, upload_to='portadas/', verbose_name='Miniatura')),
                    ('metadatos', models.JSONField(blank=True, null=True)),
                    ('permite_expediente', models.BooleanField(default=False, help_text='Indica si se pueden adjuntar documentos mientras el trámite está en este estado.', verbose_name='Permite expediente adjunto')),
                    ('expediente_obligatorio', models.BooleanField(default=False, help_text='Si es True, debe adjuntarse al menos un expediente antes de avanzar al siguiente estado.', verbose_name='Expediente obligatorio')),
                    ('icono', models.CharField(blank=True, default='circle', help_text='Nombre del ícono de Material Design / Quasar (ej. check_circle, cancel).', max_length=80, verbose_name='Ícono (Material Design)')),
                ],
                options={
                    'verbose_name': 'Estado',
                    'verbose_name_plural': 'Estados',
                    'db_table': 'creditos_estado',
                    'ordering': ['orden'],
                },
            ),
            migrations.CreateModel(
                name='ExpedienteAdjunto',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('target_object_id', models.PositiveIntegerField(verbose_name='ID de entidad')),
                    ('event_object_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de evento')),
                    ('nombre', models.CharField(blank=True, default='', help_text='Descripción breve del contenido del archivo.', max_length=200, verbose_name='Nombre del documento')),
                    ('archivo', models.FileField(upload_to='expedientes/', verbose_name='Archivo')),
                ],
                options={
                    'verbose_name': 'Expediente Adjunto',
                    'verbose_name_plural': 'Expedientes Adjuntos',
                    'db_table': 'creditos_expedienteadjunto',
                    'ordering': ['-creado'],
                },
            ),
            migrations.CreateModel(
                name='InstanciaDocumento',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('target_object_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de entidad')),
                    ('archivo_generado', models.FileField(blank=True, null=True, upload_to='documentos_generados/')),
                    ('actor_object_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de actor')),
                    ('metadatos', models.JSONField(blank=True, null=True)),
                ],
                options={
                    'verbose_name': 'Instancia de Documento',
                    'verbose_name_plural': 'Instancias de Documentos',
                    'db_table': 'creditos_instanciadocumento',
                },
            ),
            migrations.CreateModel(
                name='RazonRechazoDocumento',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('clave', models.CharField(max_length=30, unique=True)),
                    ('descripcion', models.CharField(max_length=200)),
                    ('activa', models.BooleanField(default=True)),
                ],
                options={
                    'verbose_name': 'Razón de Rechazo de Documento',
                    'verbose_name_plural': 'Razones de Rechazo de Documento',
                    'db_table': 'creditos_razonrechazodocumento',
                    'ordering': ['clave'],
                },
            ),
            migrations.CreateModel(
                name='RequisitoEstadoDocumento',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('porcentaje', models.IntegerField(default=100, help_text='Porcentaje mínimo requerido (0-100)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                    ('auto_carga', models.BooleanField(default=False)),
                ],
                options={
                    'verbose_name': 'Requisito Estado-Documento',
                    'verbose_name_plural': 'Requisitos Estado-Documento',
                    'db_table': 'creditos_requisitoestadodocumento',
                },
            ),
            migrations.CreateModel(
                name='SeguimientoWorkflow',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('target_object_id', models.PositiveIntegerField(verbose_name='ID de entidad')),
                    ('fecha_accion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Acción')),
                    ('comentarios', models.TextField(help_text='Justificación de la decisión tomada', verbose_name='Comentarios/Justificación')),
                    ('documentos_adjuntos', models.JSONField(blank=True, default=list, help_text='Lista de documentos asociados a esta acción', null=True, verbose_name='Documentos Adjuntos')),
                    ('monto_aprobado', models.DecimalField(blank=True, decimal_places=2, help_text='Monto aprobado (puede diferir del solicitado)', max_digits=12, null=True, verbose_name='Monto Aprobado')),
                    ('condiciones', models.TextField(blank=True, help_text='Condiciones para la aprobación (si aplica)', null=True, verbose_name='Condiciones')),
                    ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='Dirección IP')),
                ],
                options={
                    'verbose_name': 'Seguimiento de Workflow',
                    'verbose_name_plural': 'Seguimientos de Workflow',
                    'db_table': 'creditos_seguimientoworkflow',
                    'ordering': ['-fecha_accion'],
                },
            ),
            migrations.CreateModel(
                name='TipoDocumento',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('creado', models.DateTimeField(auto_now_add=True, null=True)),
                    ('actualizado', models.DateTimeField(auto_now=True, null=True)),
                    ('caducidad', models.DateTimeField(blank=True, null=True)),
                    ('nombre', models.CharField(max_length=250)),
                    ('descripcion', models.TextField(blank=True, null=True)),
                    ('activo', models.BooleanField(default=False)),
                    ('color', models.CharField(default='#4DEFE2', max_length=25)),
                    ('orden', models.IntegerField(default=0)),
                    ('imagen', models.ImageField(blank=True, max_length=1000, null=True, upload_to='portadas/', verbose_name='Miniatura')),
                    ('metadatos', models.JSONField(blank=True, null=True)),
                ],
                options={
                    'verbose_name': 'Tipo de Documento',
                    'verbose_name_plural': 'Tipos de Documento',
                    'db_table': 'creditos_tipodocumento',
                    'ordering': ['id'],
                },
            ),
            migrations.CreateModel(
                name='VersionFlujo',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('nombre', models.CharField(max_length=100, verbose_name='Nombre')),
                    ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                    ('activo', models.BooleanField(default=False, help_text='Desactivar retira el flujo de todos los productos asignados (fallback al dict).', verbose_name='Activo')),
                    ('metadatos', models.JSONField(blank=True, help_text='Posiciones de nodos en el canvas: {positions: {estado_id: {x, y}}}', null=True, verbose_name='Metadatos')),
                    ('creado', models.DateTimeField(auto_now_add=True, verbose_name='Creado en')),
                ],
                options={
                    'verbose_name': 'Versión de Flujo',
                    'verbose_name_plural': 'Versiones de Flujo',
                    'db_table': 'creditos_versionflujo',
                },
            ),
            migrations.RenameIndex(
                model_name='registrofirma',
                new_name='creditos_re_target__eedb6b_idx',
                old_name='rf_target_idx',
            ),
            migrations.RenameIndex(
                model_name='registrofirma',
                new_name='creditos_re_signer__70a434_idx',
                old_name='rf_signer_idx',
            ),
            migrations.AddField(
                model_name='configuraciontransicion',
                name='grupos_permitidos',
                field=models.ManyToManyField(blank=True, help_text='Vacío = cualquier grupo puede ejecutar la transición.', to='auth.group', verbose_name='Grupos permitidos'),
            ),
            migrations.AddField(
                model_name='documento',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='documento',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='estado',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='estado',
                name='etapa',
                field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estados', to='sinpapel.etapa', verbose_name='Etapa'),
            ),
            migrations.AddField(
                model_name='estado',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='configuraciontransicion',
                name='estado_destino',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='sinpapel.estado', verbose_name='Estado destino'),
            ),
            migrations.AddField(
                model_name='configuraciontransicion',
                name='estado_origen',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='sinpapel.estado', verbose_name='Estado origen'),
            ),
            migrations.AddField(
                model_name='expedienteadjunto',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='expedienteadjunto',
                name='event_content_type',
                field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='contenttypes.contenttype', verbose_name='Tipo de evento'),
            ),
            migrations.AddField(
                model_name='expedienteadjunto',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='expedienteadjunto',
                name='target_content_type',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype', verbose_name='Tipo de entidad'),
            ),
            migrations.AddField(
                model_name='instanciadocumento',
                name='actor_content_type',
                field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='contenttypes.contenttype', verbose_name='Tipo de actor'),
            ),
            migrations.AddField(
                model_name='instanciadocumento',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='instanciadocumento',
                name='documento',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='sinpapel.documento'),
            ),
            migrations.AddField(
                model_name='instanciadocumento',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='instanciadocumento',
                name='target_content_type',
                field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype', verbose_name='Tipo de entidad'),
            ),
            migrations.AddField(
                model_name='razonrechazodocumento',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='razonrechazodocumento',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='requisitoestadodocumento',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='requisitoestadodocumento',
                name='estado',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requisitos_documentales', to='sinpapel.estado'),
            ),
            migrations.AddField(
                model_name='requisitoestadodocumento',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='seguimientoworkflow',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='seguimientoworkflow',
                name='estado_anterior',
                field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='seguimientos_desde', to='sinpapel.estado', verbose_name='Estado Anterior'),
            ),
            migrations.AddField(
                model_name='seguimientoworkflow',
                name='estado_nuevo',
                field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='seguimientos_hacia', to='sinpapel.estado', verbose_name='Estado Nuevo'),
            ),
            migrations.AddField(
                model_name='seguimientoworkflow',
                name='firma_registro',
                field=models.OneToOneField(blank=True, help_text='Evidencia criptográfica de la firma electrónica (si se firmó)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='seguimiento', to='sinpapel.registrofirma', verbose_name='Registro de Firma'),
            ),
            migrations.AddField(
                model_name='seguimientoworkflow',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='seguimientoworkflow',
                name='target_content_type',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype', verbose_name='Tipo de entidad'),
            ),
            migrations.AddField(
                model_name='seguimientoworkflow',
                name='usuario_accion',
                field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='acciones_solicitud', to=settings.AUTH_USER_MODEL, verbose_name='Usuario que realizó la acción'),
            ),
            migrations.AddField(
                model_name='tipodocumento',
                name='autor',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_autor', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='tipodocumento',
                name='modificador',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_modificador', to=settings.AUTH_USER_MODEL),
            ),
            migrations.AddField(
                model_name='requisitoestadodocumento',
                name='tipo_documento',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requisitos_estado', to='sinpapel.tipodocumento'),
            ),
            migrations.AddField(
                model_name='documento',
                name='tipo_documento',
                field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='sinpapel.tipodocumento'),
            ),
            migrations.AddField(
                model_name='versionflujo',
                name='creado_por',
                field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Creado por'),
            ),
            migrations.AddField(
                model_name='configuraciontransicion',
                name='flujo',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transiciones', to='sinpapel.versionflujo', verbose_name='Versión de Flujo'),
            ),
            migrations.AddIndex(
                model_name='expedienteadjunto',
                index=models.Index(fields=['target_content_type', 'target_object_id'], name='exp_target_idx'),
            ),
            migrations.AddIndex(
                model_name='instanciadocumento',
                index=models.Index(fields=['target_content_type', 'target_object_id'], name='inst_doc_target_idx'),
            ),
            migrations.AddIndex(
                model_name='instanciadocumento',
                index=models.Index(fields=['actor_content_type', 'actor_object_id'], name='inst_doc_actor_idx'),
            ),
            migrations.AddIndex(
                model_name='seguimientoworkflow',
                index=models.Index(fields=['target_content_type', 'target_object_id', '-fecha_accion'], name='seg_workflow_target_idx'),
            ),
            migrations.AddIndex(
                model_name='seguimientoworkflow',
                index=models.Index(fields=['estado_nuevo', 'fecha_accion'], name='creditos_se_estado__ed79dd_idx'),
            ),
            migrations.AddIndex(
                model_name='seguimientoworkflow',
                index=models.Index(fields=['usuario_accion', '-fecha_accion'], name='creditos_se_usuario_c17fd8_idx'),
            ),
            migrations.AlterUniqueTogether(
                name='requisitoestadodocumento',
                unique_together={('estado', 'tipo_documento')},
            ),
            migrations.AlterUniqueTogether(
                name='configuraciontransicion',
                unique_together={('flujo', 'estado_origen', 'estado_destino')},
            ),
            ],
        ),
    ]

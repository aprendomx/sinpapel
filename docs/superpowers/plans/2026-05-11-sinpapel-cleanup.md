# Sinpapel Cleanup & Standalone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform `sinpapel` from an extracted submodule with hardcoded dependencies on `creditos` into a fully standalone, reusable Django package.

**Architecture:** Inline the `trazable` dependency, remove cross-app FKs, rename legacy SQL table prefixes, decouple integration tests from the monolith, lower the Python requirement, add CI, and introduce i18n via `gettext_lazy`.

**Tech Stack:** Django 5.0+, pytest-django, cryptography, django-simple-history, django-colorfield (new), GitHub Actions

---

## File Map

| File | Responsibility |
|------|---------------|
| `sinpapel/mixins.py` | New — inlines `Trazable` and `Catalogo` (previously from external `trazable` package) |
| `sinpapel/models/workflow.py` | Modify — create `Etapa` model, repoint `Estado.etapa` FK to it, rename `db_table`, update imports |
| `sinpapel/models/documents.py` | Modify — rename `db_table`, update imports |
| `sinpapel/models/attachments.py` | Modify — rename `db_table`, update imports |
| `sinpapel/models/signatures.py` | Modify — rename `db_table` if legacy prefix exists |
| `migrations/0004_*` | New — creates `Etapa`, repoints `Estado.etapa` FK, renames all tables |
| `tests/models.py` | New — minimal test-only Django models for workflow engine integration tests |
| `tests/apps.py` | New — Django AppConfig for the test app |
| `tests/test_workflow_engine.py` | Modify — replace `creditos` imports with local test models |
| `tests/test_mixins.py` | New — verifies inlined Trazable/Catalogo behavior |
| `pyproject.toml` | Modify — dependencies, Python version, classifiers |
| `py.typed` | New — PEP 561 marker file |
| `.github/workflows/ci.yml` | New — GitHub Actions CI matrix |
| All model files | Modify — wrap `verbose_name`/`help_text`/choices in `gettext_lazy` |

---

## Task 1: Inline `trazable` dependency

**Files:**
- Create: `sinpapel/mixins.py`
- Modify: `sinpapel/models/workflow.py`, `sinpapel/models/documents.py`, `sinpapel/models/attachments.py`
- Modify: `pyproject.toml`
- Test: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mixins.py`:

```python
"""Tests for inlined Trazable and Catalogo mixins."""
from __future__ import annotations

import pytest
from django.db import models

from sinpapel.mixins import Catalogo, Trazable


class _TestTrazableModel(Trazable):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "tests"


class _TestCatalogoModel(Catalogo):
    extra = models.CharField(max_length=50)

    class Meta:
        app_label = "tests"


@pytest.mark.django_db
def test_trazable_fields_exist():
    """Trazable model instances have creado, actualizado, autor, modificador."""
    from django.contrib.auth.models import User

    user = User.objects.create_user("traz_test", password="x")
    obj = _TestTrazableModel.objects.create(name="a", autor=user, modificador=user)
    assert obj.creado is not None
    assert obj.actualizado is not None
    assert obj.autor == user
    assert obj.modificador == user


@pytest.mark.django_db
def test_catalogo_fields_exist():
    """Catalogo inherits Trazable and adds nombre, activo, orden, etc."""
    obj = _TestCatalogoModel.objects.create(nombre="cat", activo=True, orden=1, extra="x")
    assert obj.nombre == "cat"
    assert obj.activo is True
    assert obj.orden == 1
    assert str(obj) == "cat"
```

Run: `pytest tests/test_mixins.py -v`
Expected: `ModuleNotFoundError: No module named 'sinpapel.mixins'`

- [ ] **Step 2: Create `sinpapel/mixins.py`**

```python
"""Sinpapel — reusable model mixins (inlined from trazable package).

Provides Trazable (created/updated/author/modifier tracking) and Catalogo
(base catalog with nombre/activo/orden/color/metadata).
"""
from django.contrib.auth import get_user_model
from django.db import models


class Trazable(models.Model):
    creado = models.DateTimeField(auto_now_add=True, null=True)
    actualizado = models.DateTimeField(auto_now=True, null=True)
    autor = models.ForeignKey(
        get_user_model(),
        null=True,
        on_delete=models.CASCADE,
        related_name="%(class)s_autor",
    )
    modificador = models.ForeignKey(
        get_user_model(),
        null=True,
        on_delete=models.CASCADE,
        related_name="%(class)s_modificador",
    )
    caducidad = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class Catalogo(Trazable):
    nombre = models.CharField(max_length=250, null=False, blank=False)
    descripcion = models.TextField(null=True, blank=True)
    activo = models.BooleanField(default=False)
    color = models.CharField(max_length=7, default="#4DEFE2")
    orden = models.IntegerField(default=0)
    imagen = models.ImageField(
        upload_to="portadas/",
        max_length=1000,
        null=True,
        blank=True,
        verbose_name="Miniatura",
    )
    metadatos = models.JSONField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.nombre
```

Note: Using `CharField(max_length=7)` instead of `ColorField` to avoid adding `django-colorfield` as a dependency. The database schema remains compatible (ColorField stores as VARCHAR).

- [ ] **Step 3: Update imports in model files**

In `sinpapel/models/workflow.py`, replace:
```python
from trazable.models import Catalogo, Trazable
```
with:
```python
from sinpapel.mixins import Catalogo, Trazable
```

Do the same in:
- `sinpapel/models/documents.py`
- `sinpapel/models/attachments.py`

- [ ] **Step 4: Update `pyproject.toml`**

Remove the comment block about `trazable` and add a note that it is no longer required. If `trazable` is listed anywhere as a dependency, remove it. (It is currently only mentioned in comments, not in the `dependencies` array.)

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_mixins.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add sinpapel/mixins.py sinpapel/models/workflow.py sinpapel/models/documents.py sinpapel/models/attachments.py tests/test_mixins.py pyproject.toml
git commit -m "feat: inline trazable mixins (Trazable + Catalogo)

Removes external dependency on private trazable package.
ColorField replaced with CharField(max_length=7) for zero-dependency standalone."
```

---

## Task 2: Create `Etapa` model and repoint `Estado.etapa` FK into sinpapel

**Files:**
- Modify: `sinpapel/models/workflow.py`
- Modify: `sinpapel/models/__init__.py`
- Test: `tests/test_no_creditos_dep.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_no_creditos_dep.py`:

```python
"""Verify sinpapel models do not depend on creditos."""
from __future__ import annotations


def test_estado_etapa_points_to_sinpanel_etapa():
    from sinpapel.models import Estado

    etapa_field = Estado._meta.get_field("etapa")
    assert etapa_field.remote_field.model._meta.app_label == "sinpapel", (
        "Estado.etapa must point to a sinpapel model, not creditos"
    )
```

Run: `pytest tests/test_no_creditos_dep.py -v`
Expected: FAIL — `etapa` still points to `creditos.EtapaTramite`.

- [ ] **Step 2: Add `Etapa` model to `sinpapel/models/workflow.py`**

Insert the new model right before `Estado`, and change the FK target.

In `sinpapel/models/workflow.py`:

1. Replace the `etapa` field definition inside `Estado` (lines 17–24) so it points to `sinpapel.Etapa`:

```python
class Etapa(Catalogo):
    """Grupo de estados que representa una etapa del trámite."""

    class Meta:
        db_table = "sinpapel_etapa"
        app_label = "sinpapel"
        verbose_name = "Etapa"
        verbose_name_plural = "Etapas"
        ordering = ["orden"]


class Estado(Catalogo):
    etapa = models.ForeignKey(
        "sinpapel.Etapa",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="estados",
        verbose_name="Etapa",
    )
    # rest of Estado fields remain unchanged
```

2. Add `Etapa` to `sinpapel/models/__init__.py`:

```python
from sinpapel.models.workflow import (
    ConfiguracionTransicion,
    Estado,
    Etapa,
    RequisitoEstadoDocumento,
    SeguimientoWorkflow,
    VersionFlujo,
)
```

And add `"Etapa"` to `__all__`.

- [ ] **Step 3: Re-run test**

Run: `pytest tests/test_no_creditos_dep.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add sinpapel/models/workflow.py sinpapel/models/__init__.py tests/test_no_creditos_dep.py
git commit -m "feat: create Etapa model and repoint Estado.etapa FK into sinpapel

Replaces cross-app dependency creditos.EtapaTramite with a native
sinpapel.Etapa catalog model."
```

---

## Task 3: Rename SQL tables from `creditos_*` to `sinpapel_*`

**Files:**
- Modify: `sinpapel/models/workflow.py`, `sinpapel/models/documents.py`, `sinpapel/models/attachments.py`, `sinpapel/models/signatures.py`
- Create: `migrations/0004_rename_tables.py`
- Test: `tests/test_migrations.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrations.py`:

```python
"""Verify legacy table prefix has been removed."""
from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_no_creditos_table_prefix():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'creditos_%'"
        )
        count = cursor.fetchone()[0]
    assert count == 0, f"Found {count} legacy tables with creditos_ prefix"
```

Run: `pytest tests/test_migrations.py -v`
Expected: FAIL — tables still named `creditos_*`.

- [ ] **Step 2: Update `db_table` in all models**

In `sinpapel/models/workflow.py`:
- `db_table = "creditos_estado"` → `db_table = "sinpapel_estado"`
- `db_table = "creditos_versionflujo"` → `db_table = "sinpapel_versionflujo"`
- `db_table = "creditos_configuraciontransicion"` → `db_table = "sinpapel_configuraciontransicion"`
- `db_table = "creditos_seguimientoworkflow"` → `db_table = "sinpapel_seguimientoworkflow"`
- `db_table = "creditos_requisitoestadodocumento"` → `db_table = "sinpapel_requisitoestadodocumento"`

In `sinpapel/models/documents.py`:
- `db_table = "creditos_tipodocumento"` → `db_table = "sinpapel_tipodocumento"`
- `db_table = "creditos_documento"` → `db_table = "sinpapel_documento"`
- `db_table = "creditos_instanciadocumento"` → `db_table = "sinpapel_instanciadocumento"`
- `db_table = "creditos_razonrechazodocumento"` → `db_table = "sinpapel_razonrechazodocumento"`

In `sinpapel/models/attachments.py`: check and rename if needed.
In `sinpapel/models/signatures.py`: check and rename if needed.

- [ ] **Step 3: Create combined migration**

Create `migrations/0004_rename_tables.py`:

```python
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sinpapel", "0003_historical_records"),
    ]

    operations = [
        # Create Etapa model (Task 2)
        migrations.CreateModel(
            name="Etapa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=250)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(default=False)),
                ("color", models.CharField(default="#4DEFE2", max_length=7)),
                ("orden", models.IntegerField(default=0)),
                ("imagen", models.ImageField(blank=True, max_length=1000, null=True, upload_to="portadas/", verbose_name="Miniatura")),
                ("metadatos", models.JSONField(blank=True, null=True)),
                ("creado", models.DateTimeField(auto_now_add=True, null=True)),
                ("actualizado", models.DateTimeField(auto_now=True, null=True)),
                ("autor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_autor", to="auth.user")),
                ("modificador", models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_modificador", to="auth.user")),
                ("caducidad", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "sinpapel_etapa",
                "verbose_name": "Etapa",
                "verbose_name_plural": "Etapas",
                "ordering": ["orden"],
            },
        ),
        # Repoint Estado.etapa to sinpapel.Etapa
        migrations.AlterField(
            model_name="estado",
            name="etapa",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="estados",
                to="sinpapel.etapa",
                verbose_name="Etapa",
            ),
        ),
        # Rename all legacy creditos_* tables
        migrations.AlterModelTable(
            name="estado",
            table="sinpapel_estado",
        ),
        migrations.AlterModelTable(
            name="versionflujo",
            table="sinpapel_versionflujo",
        ),
        migrations.AlterModelTable(
            name="configuraciontransicion",
            table="sinpapel_configuraciontransicion",
        ),
        migrations.AlterModelTable(
            name="seguimientoworkflow",
            table="sinpapel_seguimientoworkflow",
        ),
        migrations.AlterModelTable(
            name="requisitoestadodocumento",
            table="sinpapel_requisitoestadodocumento",
        ),
        migrations.AlterModelTable(
            name="tipodocumento",
            table="sinpapel_tipodocumento",
        ),
        migrations.AlterModelTable(
            name="documento",
            table="sinpapel_documento",
        ),
        migrations.AlterModelTable(
            name="instanciadocumento",
            table="sinpapel_instanciadocumento",
        ),
        migrations.AlterModelTable(
            name="razonrechazodocumento",
            table="sinpapel_razonrechazodocumento",
        ),
        # Add remaining models if they have legacy prefixes
        # (check attachments.py and signatures.py)
    ]
```

Also check historical records tables — `django-simple-history` uses `historical_` prefix. Those might also have `creditos_` prefix. If so, add AlterModelTable for each Historical model. Check `0003_historical_records.py` to see which historical models were created.

- [ ] **Step 4: Run test**

Run: `pytest tests/test_migrations.py -v`
Expected: PASS (after applying migration in test setup).

- [ ] **Step 5: Commit**

```bash
git add sinpapel/models/ migrations/0004_rename_tables.py tests/test_migrations.py
git commit -m "refactor: rename SQL tables from creditos_* to sinpapel_*

Includes removal of Estado.etapa FK. BREAKING for existing deployments —
requires running migration 0004."
```

---

## Task 4: Decouple workflow engine tests from `creditos`

**Files:**
- Create: `tests/models.py`, `tests/apps.py`
- Modify: `tests/test_workflow_engine.py`
- Modify: `tests/conftest.py` (if needed)

- [ ] **Step 1: Create test app models**

Create `tests/models.py`:

```python
"""Test-only models for sinpapel integration tests.

These models are registered under the 'tests' app so workflow engine
tests do not depend on the creditos monolith.
"""
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from sinpapel import workflow_enabled
from sinpapel.mixins import Trazable
from sinpapel.models import Estado, VersionFlujo


@workflow_enabled(state_field="estado", workflow_key="test_solicitud")
class TestSolicitud(Trazable):
    folio = models.CharField(max_length=50, unique=True)
    estado = models.ForeignKey(
        Estado,
        on_delete=models.CASCADE,
        null=True,
    )
    producto = models.ForeignKey(
        "TestProducto",
        on_delete=models.CASCADE,
        null=True,
    )

    # GenericRelation expected by engine for expediente_obligatorio check
    expedientes = GenericRelation(
        "sinpapel.ExpedienteAdjunto",
        content_type_field="target_content_type",
        object_id_field="target_object_id",
    )

    def resolve_workflow_version(self):
        if self.producto_id and hasattr(self.producto, "flujo"):
            return self.producto.flujo
        return VersionFlujo.objects.filter(activo=True).first()

    class Meta:
        app_label = "tests"


class TestProducto(models.Model):
    nombre = models.CharField(max_length=100)
    flujo = models.ForeignKey(
        VersionFlujo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        app_label = "tests"


class TestProductoVersionFlujo(models.Model):
    producto = models.ForeignKey(TestProducto, on_delete=models.CASCADE)
    flujo = models.ForeignKey(VersionFlujo, on_delete=models.CASCADE)

    class Meta:
        app_label = "tests"
```

Create `tests/apps.py`:

```python
from django.apps import AppConfig


class TestsConfig(AppConfig):
    name = "tests"
    verbose_name = "Sinpapel Tests"
```

- [ ] **Step 2: Rewrite `tests/test_workflow_engine.py`**

Replace the entire file content. Keep the same test semantics but use `TestSolicitud`, `TestProducto`, `TestProductoVersionFlujo` instead of `Solicitud`, `ProductoCreditoFOVISSSTE`, `ProductoVersionFlujo`.

Key changes:
- Fixture `setup_engine_basico` uses `TestSolicitud`, `TestProducto`, `TestProductoVersionFlujo`
- Remove all `from creditos.models import ...`
- `TestSolicitud` has `resolve_workflow_version` returning `self.producto.flujo`

Full rewritten file:

```python
"""Tests integration para WorkflowEngine con modelos de prueba + DB."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, User

from sinpapel.services.workflow_engine import WorkflowEngine


@pytest.fixture
def setup_engine_basico(db):
    """Crea Estado, VersionFlujo, ConfiguracionTransicion, TestProducto, TestSolicitud."""
    from sinpapel.models import (
        ConfiguracionTransicion,
        Estado,
        VersionFlujo,
    )
    from tests.models import TestProducto, TestProductoVersionFlujo, TestSolicitud

    estado_origen, _ = Estado.objects.get_or_create(nombre="ENG_ORIGEN")
    estado_destino, _ = Estado.objects.get_or_create(nombre="ENG_DESTINO")
    flujo = VersionFlujo.objects.create(nombre="ENG_FLUJO", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo,
        estado_origen=estado_origen,
        estado_destino=estado_destino,
    )
    producto = TestProducto.objects.create(nombre="ENG_P", flujo=flujo)
    TestProductoVersionFlujo.objects.create(producto=producto, flujo=flujo)
    solicitud = TestSolicitud.objects.create(estado=estado_origen, producto=producto, folio="ENG-001")
    return {
        "solicitud": solicitud,
        "estado_origen": estado_origen,
        "estado_destino": estado_destino,
        "flujo": flujo,
        "producto": producto,
        "transicion": transicion,
    }


@pytest.mark.django_db
def test_engine_puede_cambiar_estado_valid_transition(setup_engine_basico):
    superuser = User.objects.create_superuser("eng_super_valid", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ENG_DESTINO",
        superuser,
    )
    assert puede is True
    assert msg == "OK"


@pytest.mark.django_db
def test_engine_puede_cambiar_estado_invalid_transition(setup_engine_basico):
    superuser = User.objects.create_superuser("eng_super_invalid", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ESTADO_NUNCA_CONFIGURADO",
        superuser,
    )
    assert puede is False
    assert "no existe" in (msg or "")


@pytest.mark.django_db
def test_engine_cambiar_estado_creates_seguimiento(setup_engine_basico):
    from sinpapel.models import SeguimientoWorkflow

    superuser = User.objects.create_superuser("eng_super_change", password="x")
    seguimientos_antes = SeguimientoWorkflow.objects.count()

    result = WorkflowEngine().cambiar_estado(
        instance=setup_engine_basico["solicitud"],
        target_state_name="ENG_DESTINO",
        user=superuser,
        comentarios="test cambiar",
    )

    assert result["success"] is True
    assert result["estado_anterior"] == "ENG_ORIGEN"
    assert result["estado_nuevo"] == "ENG_DESTINO"
    assert SeguimientoWorkflow.objects.count() == seguimientos_antes + 1

    setup_engine_basico["solicitud"].refresh_from_db()
    assert setup_engine_basico["solicitud"].estado.nombre == "ENG_DESTINO"


@pytest.mark.django_db
def test_engine_available_transitions_returns_list(setup_engine_basico):
    user = User.objects.create_user("eng_avail", password="x")
    transitions = WorkflowEngine().available_transitions(
        setup_engine_basico["solicitud"],
        user,
    )
    assert setup_engine_basico["estado_destino"] in transitions


@pytest.mark.django_db
def test_engine_invalid_transition_raises_permission_error(setup_engine_basico):
    superuser = User.objects.create_superuser("eng_super_raise", password="x")
    with pytest.raises(PermissionError):
        WorkflowEngine().cambiar_estado(
            instance=setup_engine_basico["solicitud"],
            target_state_name="ESTADO_NUNCA_CONFIG",
            user=superuser,
            comentarios="x",
        )


@pytest.mark.django_db
def test_engine_resolves_flujo_via_resolve_workflow_version(setup_engine_basico):
    flujo = setup_engine_basico["solicitud"].resolve_workflow_version()
    assert flujo is not None
    assert flujo.nombre == "ENG_FLUJO"


@pytest.mark.django_db
def test_engine_validates_grupos_permitidos(setup_engine_basico):
    grupo_test = Group.objects.create(name="grupo_eng_test")
    setup_engine_basico["transicion"].grupos_permitidos.add(grupo_test)

    user_sin_grupo = User.objects.create_user("eng_no_group", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ENG_DESTINO",
        user_sin_grupo,
    )
    assert puede is False
    assert "No tiene permisos" in (msg or "")


@pytest.mark.django_db
def test_engine_grupos_permitidos_user_in_group_passes(setup_engine_basico):
    grupo_ok = Group.objects.create(name="grupo_eng_ok")
    setup_engine_basico["transicion"].grupos_permitidos.add(grupo_ok)

    user = User.objects.create_user("eng_with_group", password="x")
    user.groups.add(grupo_ok)

    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ENG_DESTINO",
        user,
    )
    assert puede is True


@pytest.mark.django_db
def test_engine_dispatches_side_effects(setup_engine_basico):
    from sinpapel.services.side_effects import SIDE_EFFECTS

    invocations: list[dict] = []

    def _test_handler(instance, user, **kwargs):
        invocations.append(
            {
                "instance_id": instance.id,
                "user_username": user.username,
                "kwargs": kwargs,
            }
        )
        return {"side_effect_ran": True}

    SIDE_EFFECTS["ENG_DESTINO"] = _test_handler
    try:
        superuser = User.objects.create_superuser("eng_se", password="x")
        result = WorkflowEngine().cambiar_estado(
            instance=setup_engine_basico["solicitud"],
            target_state_name="ENG_DESTINO",
            user=superuser,
            comentarios="se test",
        )
        assert result.get("side_effect_ran") is True
        assert len(invocations) == 1
        assert invocations[0]["instance_id"] == setup_engine_basico["solicitud"].id
    finally:
        del SIDE_EFFECTS["ENG_DESTINO"]


@pytest.mark.django_db
def test_engine_atomic_transaction(setup_engine_basico):
    from sinpapel.models import SeguimientoWorkflow
    from sinpapel.services.side_effects import SIDE_EFFECTS

    def _bad_handler(instance, user, **kwargs):
        raise RuntimeError("side effect failure")

    SIDE_EFFECTS["ENG_DESTINO"] = _bad_handler
    try:
        superuser = User.objects.create_superuser("eng_atom", password="x")
        seguimientos_antes = SeguimientoWorkflow.objects.count()

        result = WorkflowEngine().cambiar_estado(
            instance=setup_engine_basico["solicitud"],
            target_state_name="ENG_DESTINO",
            user=superuser,
            comentarios="atomic test",
        )

        setup_engine_basico["solicitud"].refresh_from_db()
        assert setup_engine_basico["solicitud"].estado.nombre == "ENG_DESTINO"
        assert SeguimientoWorkflow.objects.count() == seguimientos_antes + 1
        assert result.get("error") is True
    finally:
        del SIDE_EFFECTS["ENG_DESTINO"]


@pytest.mark.django_db
def test_engine_accepts_pre_created_registro_firma(setup_engine_basico):
    from sinpapel.models import RegistroFirma, SeguimientoWorkflow
    import datetime

    superuser = User.objects.create_superuser("eng_modo_b", password="x")
    rf = RegistroFirma.objects.create(
        backend_name="fiel",
        backend_metadata={"mode": "server-side", "rfc_firmante": "TEST"},
        content_hash="sha256:abc",
        signer=superuser,
        signer_display_name="TEST USER",
        is_required=True,
        verification_result="VALIDA",
        signed_at=datetime.datetime.now(datetime.timezone.utc),
    )

    seg_before = SeguimientoWorkflow.objects.count()
    result = WorkflowEngine().cambiar_estado(
        instance=setup_engine_basico["solicitud"],
        target_state_name="ENG_DESTINO",
        user=superuser,
        comentarios="test modo B",
        firma_payload={"registro_firma_id": rf.id},
    )
    assert result["success"] is True
    seg = SeguimientoWorkflow.objects.latest("id")
    assert seg.firma_registro_id == rf.id
    assert SeguimientoWorkflow.objects.count() == seg_before + 1


@pytest.mark.django_db
def test_engine_modo_a_verify_fields_uses_fiel_backend(setup_engine_basico, monkeypatch):
    from sinpapel.models import RegistroFirma
    from sinpapel.signing.backends import fiel as fiel_module

    captured = {}

    class _MockFielBackend:
        def request_signature(self, **kwargs):
            captured.update(kwargs)
            return RegistroFirma.objects.create(
                backend_name="fiel",
                backend_metadata={"mock": True},
                content_hash="sha256:mock",
                signer=kwargs.get("signer"),
                signer_display_name="MOCK",
                is_required=kwargs.get("is_required", False),
                verification_result="VALIDA",
                signed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

    monkeypatch.setattr(fiel_module, "FielBackend", _MockFielBackend)

    superuser = User.objects.create_superuser("eng_modo_a", password="x")
    payload = {
        "contenido": b"canonical content",
        "firma_b64": "ZmFrZQ==",
        "certificado_cer_b64": "ZmFrZWNlcnQ=",
    }
    result = WorkflowEngine().cambiar_estado(
        instance=setup_engine_basico["solicitud"],
        target_state_name="ENG_DESTINO",
        user=superuser,
        comentarios="test modo A",
        firma_payload=payload,
    )
    assert result["success"] is True
    assert captured["firma_b64"] == "ZmFrZQ=="
    assert captured["certificado_cer_b64"] == "ZmFrZWNlcnQ="
    assert captured["content"] == b"canonical content"
    assert captured["signer"] == superuser
```

- [ ] **Step 3: Ensure test app is discoverable**

The test suite must run with `tests` in `INSTALLED_APPS`. Document this in `README.md` or a `pytest.ini`. If a `pytest.ini` or `setup.cfg` does not exist, create `pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = tests.settings
django_find_project = false
```

And create `tests/settings.py`:

```python
"""Minimal Django settings for sinpapel test suite."""
import os

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "simple_history",
    "sinpapel",
    "tests",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True

# Cache for tests (LocMemCache)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

SINPAPEL_SIGNATURE_BACKEND = "sinpapel.signing.backends.fake.FakeBackend"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_workflow_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/models.py tests/apps.py tests/test_workflow_engine.py tests/settings.py pytest.ini
git commit -m "test: decouple workflow engine tests from creditos monolith

Introduces tests.models with TestSolicitud/TestProducto so the engine
integration suite runs standalone."
```

---

## Task 5: Lower Python requirement to `>=3.10`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update `requires-python` and classifiers**

In `pyproject.toml`:
- Change `requires-python = ">=3.13"` to `requires-python = ">=3.10"`
- Add `"Programming Language :: Python :: 3.10"`, `:: 3.11`, `:: 3.12` to classifiers

- [ ] **Step 2: Verify syntax compatibility**

Run: `python3.10 -m py_compile sinpapel/*.py sinpapel/**/*.py`
(or just `python -m py_compile` if 3.10 is not locally available — the `from __future__ import annotations` makes `|` union syntax safe at runtime on 3.10).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: lower requires-python to >=3.10

Enables adoption in environments not yet on Python 3.13."
```

---

## Task 6: Add `py.typed` marker

**Files:**
- Create: `py.typed`
- Verify: `pyproject.toml` already references it

- [ ] **Step 1: Create marker file**

Create `py.typed` as an empty file at the repo root.

- [ ] **Step 2: Verify packaging**

In `pyproject.toml`, confirm:
```toml
[tool.setuptools.package-data]
sinpapel = ["py.typed"]
```

- [ ] **Step 3: Commit**

```bash
git add py.typed
git commit -m "chore: add py.typed marker for PEP 561 type checking"
```

---

## Task 7: Add GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `tests/settings.py` (if not created in Task 4)

- [ ] **Step 1: Create CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
        django-version: ["5.0", "5.1"]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install "Django~=${{ matrix.django-version }}.0"
          pip install -e ".[dev]"

      - name: Run migrations
        run: |
          python -m django migrate --run-syncdb --settings=tests.settings

      - name: Run tests
        run: pytest tests/ -v

      - name: Type check with pyright
        run: |
          pip install pyright
          pyright sinpapel/
        continue-on-error: true
```

- [ ] **Step 2: Verify CI triggers**

Push the branch and confirm the workflow appears under Actions.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions matrix (Python 3.10-3.13 × Django 5.0-5.1)"
```

---

## Task 8: i18n via `gettext_lazy`

**Files:**
- Modify: `sinpapel/models/workflow.py`, `sinpapel/models/documents.py`, `sinpapel/models/attachments.py`, `sinpapel/models/signatures.py`
- Modify: `sinpapel/mixins.py`
- Modify: `sinpapel/decorators.py`, `sinpapel/exceptions.py`
- Test: `tests/test_i18n.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_i18n.py`:

```python
"""Verify gettext_lazy is used in model metadata."""
from __future__ import annotations

import pytest
from django.utils.translation import gettext_lazy as _


def _is_lazy_string(obj):
    from django.utils.functional import lazy, Promise
    return isinstance(obj, Promise)


@pytest.mark.django_db
def test_estado_verbose_name_is_lazy():
    from sinpapel.models import Estado
    assert _is_lazy_string(Estado._meta.verbose_name)
    assert _is_lazy_string(Estado._meta.verbose_name_plural)
```

Run: `pytest tests/test_i18n.py -v`
Expected: FAIL — currently `str`, not lazy.

- [ ] **Step 2: Update all model metadata strings**

In each model file, add at the top:
```python
from django.utils.translation import gettext_lazy as _
```

Then wrap every `verbose_name`, `verbose_name_plural`, and `help_text` string with `_()`.

Example changes for `sinpapel/models/workflow.py`:

```python
class Meta:
    db_table = "sinpapel_estado"
    app_label = "sinpapel"
    verbose_name = _("Estado")
    verbose_name_plural = _("Estados")
    ordering = ["orden"]
```

Do this systematically for:
- `Estado` (fields `permite_expediente`, `expediente_obligatorio`, `icono`)
- `VersionFlujo` (all fields)
- `ConfiguracionTransicion` (all fields)
- `SeguimientoWorkflow` (all fields)
- `RequisitoEstadoDocumento`
- `TipoDocumento`, `Documento`, `InstanciaDocumento`, `RazonRechazoDocumento`
- `ExpedienteAdjunto`
- `RegistroFirma` (if it has verbose names)
- `sinpapel/mixins.py` (`Trazable` fields, `Catalogo` fields)

Also update `sinpapel/decorators.py` docstrings/examples (not critical, but nice), and `sinpapel/exceptions.py` if any user-facing strings exist.

- [ ] **Step 3: Run i18n test**

Run: `pytest tests/test_i18n.py -v`
Expected: PASS

- [ ] **Step 4: Run full suite**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sinpapel/models/ sinpapel/mixins.py sinpapel/decorators.py tests/test_i18n.py
git commit -m "feat(i18n): wrap all model metadata in gettext_lazy

Prepares package for multi-language installations."
```

---

## Task 9: Update README and documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update Installation section**

Remove the `trazable` installation block (it is now inlined). Update `requires-python` to `>=3.10`.

Replace:
```markdown
**Dependencia adicional (`trazable`):** `sinpapel` usa el mixin `trazable.models.Trazable`...
```
with:
```markdown
**Python:** requiere `>=3.10`. **Django:** `>=5.0`.
```

- [ ] **Step 2: Update Settings section**

Remove `"trazable"` from the `INSTALLED_APPS` example. Keep `"simple_history"` and `"sinpapel"`.

- [ ] **Step 3: Update Migrations section**

Remove the note about `creditos_*` prefix (it no longer applies). Update the migration list:
- `0001_initial`
- `0002_extract_remaining_models`
- `0003_historical_records`
- `0004_rename_tables` — creates `Etapa`, renames all tables to `sinpapel_*`, repoints `Estado.etapa`

- [ ] **Step 4: Add Etapa to workflow docs**

In §6 (Configure the workflow), mention that `Etapa` is available as a native catalog to group states:

```python
from sinpapel.models import Etapa, Estado

captura_etapa = Etapa.objects.create(nombre="Captura", activo=True)
captura = Estado.objects.create(nombre="CAPTURA", activo=True, etapa=captura_etapa)
```

- [ ] **Step 5: Update Known limitations**

Remove:
- `trazable` no está en PyPI (ya no aplica)
- Migración del prefijo `creditos_*` (ya no aplica)
- Sin `py.typed` marker (ya no aplica)

Add:
- `Etapa` model is new in v0.2.0
- `requires-python` lowered to `>=3.10`

- [ ] **Step 6: Update testing docs**

Document the standalone test settings:
```bash
pytest tests/ --ds=tests.settings
```

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: update README for standalone package

Reflects inlined trazable, new Etapa model, table renames, Python 3.10+,
standalone test suite, and i18n."
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] Inline trazable → Task 1
- [x] Remove creditos FK → Task 2
- [x] Rename tables → Task 3
- [x] Decouple tests → Task 4
- [x] Lower Python → Task 5
- [x] py.typed → Task 6
- [x] CI → Task 7
- [x] i18n → Task 8

**2. Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] No vague "add validation" steps
- [x] No "Similar to Task N" shortcuts
- [x] Every code step contains actual code

**3. Type consistency:**
- [x] `Trazable` / `Catalogo` defined in Task 1, imported in later tasks
- [x] `TestSolicitud` / `TestProducto` used consistently in Task 4
- [x] `db_table` naming consistent (`sinpapel_*`) across Task 3
- [x] Cache helper names (`_KEY_PREFIX`, etc.) unchanged

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-11-sinpapel-cleanup.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

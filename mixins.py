"""Sinpapel — reusable model mixins (inlined from trazable package).

Provides Trazable (created/updated/author/modifier tracking) and Catalogo
(base catalog with nombre/activo/orden/color/metadata).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class CampoMetadato:
    """Definición de un campo capturable en el mixin MetadatosCapturables.

    Attributes:
        nombre: nombre del campo (usado como key en JSON y como atributo en proxy)
        tipo: tipo de dato esperado (str, int, bool, Decimal, date)
        requerido: si el campo debe estar presente para pasar validación
        default: valor por omisión cuando no está seteado
        choices: lista opcional de valores permitidos
        etiqueta: etiqueta para UI / forms
        ayuda: texto de ayuda para UI
    """

    nombre: str
    tipo: type
    requerido: bool = False
    default: Any = None
    choices: list[str] | None = None
    etiqueta: str = ""
    ayuda: str = ""


class MetadatosProxy:
    """Proxy de acceso a datos_capturados con schema validation.

    Se instancia vía `instance.meta` en modelos que heredan
    MetadatosCapturables. Lee/escribe del JSONField subyacente,
    validando tipo, choices y requeridos.
    """

    def __init__(self, instance, schema: list[CampoMetadato]) -> None:
        self._instance = instance
        self._schema = {c.nombre: c for c in schema}
        self._datos = instance.datos_capturados or {}

    def __getattr__(self, name: str):
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        campo = self._schema.get(name)
        if campo is None:
            raise AttributeError(f"Campo '{name}' no definido en SCHEMA_METADATOS")
        raw = self._datos.get(name, campo.default)
        return self._deserializar(campo, raw)

    def __setattr__(self, name: str, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        campo = self._schema.get(name)
        if campo is None:
            raise AttributeError(f"Campo '{name}' no definido en SCHEMA_METADATOS")
        self._validar(campo, value)
        self._datos[name] = self._serializar(value)
        self._instance.datos_capturados = self._datos

    def _validar(self, campo: CampoMetadato, value) -> None:
        if value is None:
            return
        if not isinstance(value, campo.tipo):
            raise TypeError(
                f"Campo '{campo.nombre}' espera {campo.tipo.__name__}, "
                f"recibió {type(value).__name__}"
            )
        if campo.choices is not None and value not in campo.choices:
            raise ValueError(
                f"Campo '{campo.nombre}' solo acepta {campo.choices}, "
                f"recibió '{value}'"
            )

    def errores(self) -> dict[str, str]:
        """Valida todos los campos requeridos y retorna dict de errores."""
        errores: dict[str, str] = {}
        for campo in self._schema.values():
            if campo.requerido:
                raw = self._datos.get(campo.nombre, campo.default)
                if raw is None or raw == "":
                    errores[campo.nombre] = f"El campo '{campo.nombre}' es obligatorio."
        return errores

    def _serializar(self, value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _deserializar(self, campo: CampoMetadato, raw):
        if raw is None:
            return None
        if campo.tipo is Decimal and isinstance(raw, str):
            return Decimal(raw)
        if campo.tipo is date and isinstance(raw, str):
            return date.fromisoformat(raw)
        return raw

    def to_dict(self, *, incluir_defaults: bool = True) -> dict[str, Any]:
        """Retorna dict con todos los campos del schema.

        Args:
            incluir_defaults: si True, incluye campos no seteados con su default.
        """
        resultado: dict[str, Any] = {}
        for campo in self._schema.values():
            raw = self._datos.get(campo.nombre)
            if raw is None:
                if not incluir_defaults:
                    continue
                raw = campo.default
            if raw is not None:
                resultado[campo.nombre] = self._deserializar(campo, raw)
            elif incluir_defaults:
                resultado[campo.nombre] = None
        return resultado


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
        verbose_name=_("Miniatura"),
    )
    metadatos = models.JSONField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.nombre

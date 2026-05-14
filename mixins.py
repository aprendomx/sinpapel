"""Sinpapel — reusable model mixins (inlined from trazable package).

Provides Trazable (created/updated/author/modifier tracking) and Catalogo
(base catalog with nombre/activo/orden/color/metadata).
"""
from dataclasses import dataclass
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

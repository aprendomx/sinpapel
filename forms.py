"""Sinpapel — Form/Serializer Factory for MetadatosCapturables.

Generates Django Forms and DRF Serializers dynamically from
SCHEMA_METADATOS definitions.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

from django import forms
from django.utils.translation import gettext_lazy as _

from sinpapel.mixins import CampoMetadato

F = TypeVar("F", bound=forms.Form)


class MetaFormFactory:
    """Genera Django Forms / DRF Serializers desde SCHEMA_METADATOS."""

    _DJANGO_FIELD_MAP: dict[type, type[forms.Field]] = {
        str: forms.CharField,
        int: forms.IntegerField,
        bool: forms.BooleanField,
        Decimal: forms.DecimalField,
        date: forms.DateField,
    }

    @classmethod
    def build_form(
        cls,
        schema: list[CampoMetadato],
        **form_class_kwargs: Any,
    ) -> type[F]:
        """Construye una subclase de django.forms.Form a partir de un schema.

        Args:
            schema: lista de CampoMetadato
            **form_class_kwargs: kwargs adicionales para la clase Form

        Returns:
            Subclase de forms.Form con los campos definidos
        """
        attrs: dict[str, forms.Field] = {}
        for campo in schema:
            if campo.choices is not None:
                field_class = forms.ChoiceField
            else:
                field_class = cls._DJANGO_FIELD_MAP[campo.tipo]
            kwargs = cls._build_field_kwargs(campo, is_django=True)
            attrs[campo.nombre] = field_class(**kwargs)

        return type("DynamicMetaForm", (forms.Form,), {**attrs, **form_class_kwargs})

    @classmethod
    def build_serializer(
        cls,
        schema: list[CampoMetadato],
        **serializer_class_kwargs: Any,
    ) -> type[Any]:
        """Construye una subclase de rest_framework.serializers.Serializer.

        Requiere que 'djangorestframework' esté instalado.

        Args:
            schema: lista de CampoMetadato
            **serializer_class_kwargs: kwargs adicionales para la clase Serializer

        Returns:
            Subclase de serializers.Serializer con los campos definidos

        Raises:
            ImportError: si djangorestframework no está instalado
        """
        try:
            from rest_framework import serializers
        except ImportError as exc:
            raise ImportError(
                "MetaFormFactory.build_serializer() requiere 'djangorestframework'. "
                "Instálalo con: pip install djangorestframework"
            ) from exc

        drf_field_map: dict[type, type[serializers.Field]] = {
            str: serializers.CharField,
            int: serializers.IntegerField,
            bool: serializers.BooleanField,
            Decimal: serializers.DecimalField,
            date: serializers.DateField,
        }

        attrs: dict[str, serializers.Field] = {}
        for campo in schema:
            if campo.choices is not None:
                field_class = serializers.ChoiceField
            else:
                field_class = drf_field_map[campo.tipo]
            kwargs = cls._build_field_kwargs(campo, is_django=False)
            attrs[campo.nombre] = field_class(**kwargs)

        return type("DynamicMetaSerializer", (serializers.Serializer,), {**attrs, **serializer_class_kwargs})

    @classmethod
    def _build_field_kwargs(cls, campo: CampoMetadato, *, is_django: bool) -> dict[str, Any]:
        """Construye kwargs para un campo Django o DRF desde CampoMetadato."""
        kwargs: dict[str, Any] = {
            "required": campo.requerido,
            "label": campo.etiqueta or campo.nombre.replace("_", " ").title(),
            "help_text": campo.ayuda,
        }

        if campo.default is not None:
            if is_django:
                kwargs["initial"] = campo.default
            else:
                kwargs["default"] = campo.default

        if campo.choices is not None:
            kwargs["choices"] = [(c, c) for c in campo.choices]

        if campo.tipo is Decimal and campo.choices is None:
            kwargs["max_digits"] = 15
            kwargs["decimal_places"] = 2

        return kwargs

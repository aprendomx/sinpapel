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


class _LazyDRFMap:
    """Descriptor que carga el mapa DRF bajo demanda."""

    def __get__(
        self, obj: Any | None, owner: type[Any] | None = None
    ) -> dict[type, type[Any]]:
        from rest_framework import serializers

        return {
            str: serializers.CharField,
            int: serializers.IntegerField,
            bool: serializers.BooleanField,
            Decimal: serializers.DecimalField,
            date: serializers.DateField,
        }


class MetaFormFactory:
    """Genera Django Forms / DRF Serializers desde SCHEMA_METADATOS."""

    _DJANGO_FIELD_MAP: dict[type, type[forms.Field]] = {
        str: forms.CharField,
        int: forms.IntegerField,
        bool: forms.BooleanField,
        Decimal: forms.DecimalField,
        date: forms.DateField,
    }

    _DRF_FIELD_MAP: dict[type, type[Any]] = _LazyDRFMap()  # type: ignore[assignment]

    @classmethod
    def build_form(
        cls,
        schema: list[CampoMetadato],
        name: str | None = None,
        **form_class_kwargs: Any,
    ) -> type[F]:
        """Construye una subclase de django.forms.Form a partir de un schema.

        Nota sobre ``default``:
            En Django Forms, ``default`` se mapea a ``initial``, lo cual solo
            pre-rellena el widget. No actúa como valor por omisión real
            durante la validación. En DRF, ``default`` sí es un valor por
            omisión verdadero.

        Args:
            schema: lista de CampoMetadato
            name: nombre opcional para la clase generada
            **form_class_kwargs: kwargs adicionales para la clase Form

        Returns:
            Subclase de forms.Form con los campos definidos
        """
        field_names = {c.nombre for c in schema}
        overlap = field_names & set(form_class_kwargs)
        if overlap:
            raise ValueError(
                f"Los siguientes kwargs colisionan con nombres de campo: {overlap}"
            )

        attrs: dict[str, forms.Field] = {}
        for campo in schema:
            if campo.choices is not None:
                field_class = forms.ChoiceField
            else:
                try:
                    field_class = cls._DJANGO_FIELD_MAP[campo.tipo]
                except KeyError:
                    raise ValueError(f"Tipo no soportado: {campo.tipo}") from None
            kwargs = cls._build_field_kwargs(campo, is_django=True)
            attrs[campo.nombre] = field_class(**kwargs)

        class_name = name or (
            "DynamicMetaForm" if not schema else f"DynamicMetaForm_{schema[0].nombre}"
        )
        return type(class_name, (forms.Form,), {**attrs, **form_class_kwargs})

    @classmethod
    def build_serializer(
        cls,
        schema: list[CampoMetadato],
        name: str | None = None,
        **serializer_class_kwargs: Any,
    ) -> type[Any]:
        """Construye una subclase de rest_framework.serializers.Serializer.

        Requiere que 'djangorestframework' esté instalado.

        Nota sobre ``default``:
            En DRF, ``default`` actúa como valor por omisión real durante la
            serialización/deserialización. En Django Forms, ``default`` se
            mapea a ``initial`` (solo pre-rellena el widget).

        Args:
            schema: lista de CampoMetadato
            name: nombre opcional para la clase generada
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

        field_names = {c.nombre for c in schema}
        overlap = field_names & set(serializer_class_kwargs)
        if overlap:
            raise ValueError(
                f"Los siguientes kwargs colisionan con nombres de campo: {overlap}"
            )

        attrs: dict[str, serializers.Field] = {}
        for campo in schema:
            if campo.choices is not None:
                field_class = serializers.ChoiceField
            else:
                try:
                    field_class = cls._DRF_FIELD_MAP[campo.tipo]
                except KeyError:
                    raise ValueError(f"Tipo no soportado: {campo.tipo}") from None
            kwargs = cls._build_field_kwargs(campo, is_django=False)
            attrs[campo.nombre] = field_class(**kwargs)

        class_name = name or (
            "DynamicMetaSerializer"
            if not schema
            else f"DynamicMetaSerializer_{schema[0].nombre}"
        )
        return type(
            class_name,
            (serializers.Serializer,),
            {**attrs, **serializer_class_kwargs},
        )

    @classmethod
    def _build_field_kwargs(
        cls, campo: CampoMetadato, *, is_django: bool
    ) -> dict[str, Any]:
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

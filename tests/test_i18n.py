"""Verify gettext_lazy is used in model metadata."""
from __future__ import annotations

import pytest


def _is_lazy_string(obj):
    from django.utils.functional import Promise
    return isinstance(obj, Promise)


@pytest.mark.django_db
def test_estado_verbose_name_is_lazy():
    from sinpapel.models import Estado
    assert _is_lazy_string(Estado._meta.verbose_name)
    assert _is_lazy_string(Estado._meta.verbose_name_plural)


@pytest.mark.django_db
def test_etapa_verbose_name_is_lazy():
    from sinpapel.models import Etapa
    assert _is_lazy_string(Etapa._meta.verbose_name)
    assert _is_lazy_string(Etapa._meta.verbose_name_plural)

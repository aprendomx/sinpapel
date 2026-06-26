"""Campo InstanciaDocumento.archivo para uploads de usuario (sinpapel-drf)."""
from __future__ import annotations


def test_archivo_field_config():
    from sinpapel.models import InstanciaDocumento

    field = InstanciaDocumento._meta.get_field("archivo")
    assert field.upload_to == "instancias_documento/"
    assert field.blank is True
    assert field.null is True

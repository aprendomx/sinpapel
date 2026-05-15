"""Verify sinpapel models do not depend on creditos."""
from __future__ import annotations


def test_estado_etapa_points_to_sinpanel_etapa():
    from sinpapel.models import Estado

    etapa_field = Estado._meta.get_field("etapa")
    remote_model = etapa_field.remote_field.model
    if isinstance(remote_model, str):
        assert "sinpapel" in remote_model, (
            "Estado.etapa must point to a sinpapel model, not creditos"
        )
    else:
        assert remote_model._meta.app_label == "sinpapel", (
            "Estado.etapa must point to a sinpapel model, not creditos"
        )

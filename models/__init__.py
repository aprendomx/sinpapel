"""Sinpapel models — re-exportados desde submódulos."""
from sinpapel.models.attachments import ExpedienteAdjunto
from sinpapel.models.documents import (
    Documento,
    InstanciaDocumento,
    RazonRechazoDocumento,
    TipoDocumento,
)
from sinpapel.models.predicates import CondicionTransicion
from sinpapel.models.signatures import RegistroFirma
from sinpapel.models.sla import SLAConfiguracion
from sinpapel.models.workflow import (
    ConfiguracionTransicion,
    Estado,
    Etapa,
    RequisitoEstadoDocumento,
    SeguimientoWorkflow,
    VersionFlujo,
)

__all__ = [
    # predicates
    "CondicionTransicion",
    # workflow
    "Estado",
    "Etapa",
    "VersionFlujo",
    "ConfiguracionTransicion",
    "SeguimientoWorkflow",
    "RequisitoEstadoDocumento",
    # documents
    "TipoDocumento",
    "Documento",
    "InstanciaDocumento",
    "RazonRechazoDocumento",
    # attachments
    "ExpedienteAdjunto",
    # signatures
    "RegistroFirma",
    # sla
    "SLAConfiguracion",
]

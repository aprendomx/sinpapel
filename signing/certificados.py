"""Lectura de certificados X.509 y del bundle de confianza FIEL (API pública).

Es la MISMA implementación que usa ``FielBackend`` (issue #7): un proyecto
puede validar su ``SINPAPEL_FIEL_TRUSTED_CA_BUNDLE`` en el despliegue, o armar
el bundle y comprobar que cubre una e.firma real, y obtener exactamente el
resultado que tendrá el backend al firmar.

Incluye la ruta tolerante de 0.8.6 (issue #6): certificados con atributos
``PrintableString`` no conformes —la AC6 del SAT y las e.firma que emite— se
leen re-etiquetando el tipo, y su firma se verifica siempre contra los bytes
``tbsCertificate`` originales.

No importa Django ni modelos: se puede usar desde scripts sin settings.

Estable dentro de la serie 0.8.x (ver ``docs/development/api-publica.md``).

Ejemplo::

    from sinpapel.signing import cargar_bundle_confianza, emitido_por, leer_certificado

    bundle = cargar_bundle_confianza("/etc/siaf/sat-ac-bundle.pem")
    print(len(bundle.cas), bundle.omitidos)

    efirma = leer_certificado(Path("persona.cer").read_bytes())
    ac = emitido_por(efirma, bundle.cas)  # None si el bundle no la cubre
"""
from __future__ import annotations

import base64
import binascii
import datetime
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Union

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding

from sinpapel.signing._x509_tolerante import CertificadoLeido, cargar_der
from sinpapel.signing.exceptions import SignatureBackendNotConfiguredError

__all__ = [
    "BundleCargado",
    "CertificadoLeido",
    "cargar_bundle_confianza",
    "emitido_por",
    "leer_certificado",
]

Ruta = Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]

_PEM_CERT = re.compile(
    rb"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", re.DOTALL
)


@dataclass(frozen=True)
class BundleCargado:
    """Resultado de :func:`cargar_bundle_confianza`.

    Attributes:
        cas: AC legibles, en el orden del bundle.
        omitidos: certificados ilegibles, como ``"archivo#índice"``.
        motivos: ``{"archivo#índice": motivo}`` de cada omitido.
        normalizados: ``"archivo#índice"`` de los leídos con la ruta
            tolerante (PrintableString no conforme, p. ej. AC6 del SAT).
    """

    cas: list[x509.Certificate]
    omitidos: list[str] = field(default_factory=list)
    motivos: dict[str, str] = field(default_factory=dict)
    normalizados: list[str] = field(default_factory=list)


def leer_certificado(datos: bytes) -> CertificadoLeido:
    """Lee UN certificado DER o PEM como lo hace ``FielBackend``.

    Si el parser estricto de ``cryptography`` lo rechaza por atributos
    ``PrintableString`` no conformes, usa la ruta tolerante. Para verificar
    la firma del certificado usa ``CertificadoLeido.tbs_original`` (o
    :func:`emitido_por`), nunca ``cert.tbs_certificate_bytes``.

    Raises:
        ValueError: no es un certificado legible, o el PEM trae más de uno
            (para eso está :func:`cargar_bundle_confianza`).
    """
    bloques = _PEM_CERT.findall(datos)
    if not bloques:
        return cargar_der(datos)
    if len(bloques) > 1:
        raise ValueError(
            f"el PEM contiene {len(bloques)} certificados; leer_certificado "
            "espera uno (usa cargar_bundle_confianza)"
        )
    return cargar_der(_b64(bloques[0]))


def cargar_bundle_confianza(rutas: Ruta | Iterable[Ruta]) -> BundleCargado:
    """Carga un bundle de AC de confianza como ``SINPAPEL_FIEL_TRUSTED_CA_BUNDLE``.

    ``rutas``: un path o una lista de paths a archivos PEM (uno o varios
    certificados) o DER (uno). Cada certificado se carga por separado: los
    ilegibles se omiten y se reportan en ``omitidos`` / ``motivos``.

    Raises:
        SignatureBackendNotConfiguredError: no quedó ningún certificado
            legible (incluye la lista vacía).
        OSError: un archivo no existe o no se puede leer.
    """
    if isinstance(rutas, (str, bytes, os.PathLike)):
        lista: list[Ruta] = [rutas]
    else:
        lista = list(rutas)

    resultado = BundleCargado(cas=[])
    for ruta in lista:
        nombre = os.fsdecode(ruta)
        with open(ruta, "rb") as fh:
            data = fh.read()
        bloques = _PEM_CERT.findall(data)
        candidatos = list(enumerate(bloques)) if bloques else [(0, None)]
        for i, bloque in candidatos:
            clave = f"{nombre}#{i}"
            try:
                der = data if bloque is None else _b64(bloque)
                leido = cargar_der(der)
            except ValueError as exc:
                resultado.omitidos.append(clave)
                resultado.motivos[clave] = str(exc)
                continue
            if leido.normalizado:
                resultado.normalizados.append(clave)
            resultado.cas.append(leido.cert)

    if not resultado.cas:
        raise SignatureBackendNotConfiguredError(
            "El bundle de confianza no contiene ningún certificado PEM/DER "
            f"legible (omitidos: {', '.join(resultado.omitidos) or 'ninguno'})"
        )
    return resultado


def emitido_por(
    cert: CertificadoLeido | x509.Certificate,
    cas: Iterable[x509.Certificate],
    *,
    en: datetime.datetime | None = None,
) -> x509.Certificate | None:
    """Devuelve la AC de ``cas`` que emitió ``cert``, o ``None``.

    Es la verificación de **un nivel** de ``FielBackend``: sujeto de la AC ==
    emisor del cert, AC vigente en ``en`` (default: ahora, UTC) y firma del
    cert válida con la llave pública de la AC sobre el ``tbsCertificate``
    original. No valida la vigencia del propio ``cert`` ni la cadena hasta
    la raíz.

    Pasa un :class:`CertificadoLeido` (de :func:`leer_certificado`) cuando el
    cert pueda venir de la ruta tolerante; con un ``x509.Certificate`` se usa
    su ``tbs_certificate_bytes``.
    """
    if isinstance(cert, x509.Certificate):
        x, tbs = cert, cert.tbs_certificate_bytes
    else:
        x, tbs = cert.cert, cert.tbs_original
    momento = en or datetime.datetime.now(datetime.timezone.utc)
    for ca in cas:
        if ca.subject != x.issuer:
            continue
        if not ca.not_valid_before_utc <= momento <= ca.not_valid_after_utc:
            continue
        try:
            ca.public_key().verify(  # type: ignore[union-attr, call-arg]
                x.signature,
                tbs,
                padding.PKCS1v15(),  # type: ignore[arg-type]
                x.signature_hash_algorithm,  # type: ignore[arg-type]
            )
        except Exception:
            continue
        return ca
    return None


def _b64(bloque: bytes) -> bytes:
    try:
        return base64.b64decode(b"".join(bloque.split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"bloque PEM con base64 inválido: {exc}") from exc

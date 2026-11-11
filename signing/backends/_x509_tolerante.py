"""Lectura tolerante de certificados X.509 con nombres mal codificados.

Algunas AC del SAT (AC6, vigente 2023-03-24 → 2031-03-24, y los certificados
que emite) codifican atributos del nombre como ``PrintableString`` con
caracteres que ese tipo no admite (p. ej. ``ó`` en UTF-8). ``cryptography``
aplica RFC 5280 de forma estricta y rechaza el certificado completo
(issue #6).

Estrategia: re-etiquetar **solo el byte de tipo** de esos ``PrintableString``
a ``UTF8String`` (o ``T61String`` si el contenido no es UTF-8 válido). La
longitud no cambia, así que todos los offsets del DER se conservan. El
certificado re-etiquetado se usa SOLO para leer campos (sujeto, emisor,
vigencia, llave pública); la firma del certificado se verifica siempre
contra los bytes ``tbsCertificate`` ORIGINALES (``tbs_original``), de modo
que la tolerancia no relaja ninguna verificación criptográfica.
"""
from __future__ import annotations

from dataclasses import dataclass

from cryptography import x509

_TAG_PRINTABLE = 0x13
_TAG_T61 = 0x14
_TAG_UTF8 = 0x0C
_CONSTRUCTED = 0x20
# Un Certificate real anida < 12 niveles; el tope evita RecursionError con
# entradas hostiles (el walker solo corre si el parser estricto ya falló).
_PROFUNDIDAD_MAX = 32

# X.680 §41.4: A–Z a–z 0–9 espacio ' ( ) + , - . / : = ?
_PRINTABLE = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '()+,-./:=?"
)


@dataclass(frozen=True)
class CertificadoLeido:
    """Certificado listo para usar.

    Attributes:
        cert: certificado parseado (re-etiquetado si ``normalizado``).
        tbs_original: bytes ``tbsCertificate`` tal como los firmó la AC.
            Úsalos —no ``cert.tbs_certificate_bytes``— para verificar la
            firma del certificado.
        normalizado: True si hubo que re-etiquetar algún atributo.
    """

    cert: x509.Certificate
    tbs_original: bytes
    normalizado: bool


def cargar_der(der: bytes) -> CertificadoLeido:
    """Carga un certificado DER; si el parser estricto falla, re-etiqueta.

    Raises:
        ValueError: el DER no es un certificado legible ni tras normalizar.
    """
    try:
        cert = x509.load_der_x509_certificate(der)
        return CertificadoLeido(cert, cert.tbs_certificate_bytes, False)
    except ValueError as estricto:
        error_estricto = estricto

    buf = bytearray(der)
    try:
        cambios = _retag_printable(buf, 0, len(buf))
    except _DerInvalido:
        raise error_estricto from None
    if not cambios:
        raise error_estricto
    try:
        cert = x509.load_der_x509_certificate(bytes(buf))
    except ValueError:
        raise error_estricto from None
    # Offsets idénticos: el tbs original es el mismo rango sobre ``der``.
    inicio, fin = _rango_tbs(der)
    return CertificadoLeido(cert, der[inicio:fin], True)


# ─── DER mínimo ──────────────────────────────────────────────────────────


class _DerInvalido(Exception):
    pass


def _leer_tlv(buf: bytes | bytearray, pos: int, fin: int) -> tuple[int, int, int, int]:
    """Devuelve (tag_byte, pos_tag, inicio_contenido, fin_contenido)."""
    if pos >= fin:
        raise _DerInvalido
    tag_pos = pos
    tag = buf[pos]
    pos += 1
    if tag & 0x1F == 0x1F:  # tag multibyte
        while True:
            if pos >= fin:
                raise _DerInvalido
            b = buf[pos]
            pos += 1
            if not b & 0x80:
                break
    if pos >= fin:
        raise _DerInvalido
    largo = buf[pos]
    pos += 1
    if largo & 0x80:
        n = largo & 0x7F
        if n == 0 or n > 4 or pos + n > fin:  # 0 = indefinido: no es DER
            raise _DerInvalido
        largo = int.from_bytes(buf[pos : pos + n], "big")
        pos += n
    if pos + largo > fin:
        raise _DerInvalido
    return tag, tag_pos, pos, pos + largo


def _retag_printable(buf: bytearray, pos: int, fin: int, profundidad: int = 0) -> int:
    """Re-etiqueta in-place los PrintableString no conformes. Devuelve cuántos."""
    if profundidad > _PROFUNDIDAD_MAX:
        raise _DerInvalido
    cambios = 0
    while pos < fin:
        tag, tag_pos, ini, sig = _leer_tlv(buf, pos, fin)
        if tag & _CONSTRUCTED:
            cambios += _retag_printable(buf, ini, sig, profundidad + 1)
        elif tag == _TAG_PRINTABLE:
            contenido = bytes(buf[ini:sig])
            if not _PRINTABLE.issuperset(contenido):
                try:
                    contenido.decode("utf-8")
                    buf[tag_pos] = _TAG_UTF8
                except UnicodeDecodeError:
                    buf[tag_pos] = _TAG_T61
                cambios += 1
        pos = sig
    return cambios


def _rango_tbs(der: bytes) -> tuple[int, int]:
    """Rango [inicio, fin) del TLV tbsCertificate dentro del Certificate."""
    _, _, ini, fin = _leer_tlv(der, 0, len(der))
    _, tbs_pos, _, tbs_fin = _leer_tlv(der, ini, fin)
    return tbs_pos, tbs_fin

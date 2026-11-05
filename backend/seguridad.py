"""Detección básica de datos sensibles y validación de imágenes antes de llamar al LLM."""

import base64
import binascii
import re

MAX_IMAGEN_BYTES = 4 * 1024 * 1024
# Firmas iniciales de cada formato admitido, para no confiar solo en el tipo declarado.
_FIRMAS_IMAGEN = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/webp": (b"RIFF",),
}

# Marca direcciones IP (cuatro octetos) y palabras asociadas a credenciales.
_PATRON_SENSIBLE = re.compile(
    r"(\b\d{1,3}(\.\d{1,3}){3}\b|password|secret|contrase)",
    re.IGNORECASE,
)

MENSAJE_DATOS_SENSIBLES = (
    "Detecté posibles datos sensibles en tu mensaje (una IP real o una contraseña). "
    "Por seguridad, no envíes esa información a un servicio externo. "
    "Reemplázala por valores de ejemplo (por ejemplo, 192.168.X.1 en lugar de la IP real) "
    "y vuelve a enviar tu consulta."
)


def contiene_datos_sensibles(texto: str) -> bool:
    """Indica si el texto parece incluir una IP real o una credencial."""
    return bool(_PATRON_SENSIBLE.search(texto or ""))


def validar_imagen(mime: str, data: str) -> None:
    """Comprueba que la imagen en base64 sea válida, del formato declarado y de hasta 4 MB."""
    try:
        contenido = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("La imagen adjunta no es válida.") from error
    if len(contenido) > MAX_IMAGEN_BYTES:
        raise ValueError("La imagen supera el límite de 4 MB.")
    firma_valida = contenido.startswith(_FIRMAS_IMAGEN.get(mime, ()))
    if mime == "image/webp":
        firma_valida = firma_valida and contenido[8:12] == b"WEBP"
    if not firma_valida:
        raise ValueError("El archivo no es una imagen PNG, JPG o WEBP válida.")

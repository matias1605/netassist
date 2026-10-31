"""Detección básica de datos sensibles antes de enviar la consulta al LLM."""

import re

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

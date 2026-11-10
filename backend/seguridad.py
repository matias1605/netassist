"""Política local de laboratorio; nunca certifica el contenido visual de capturas."""

import base64
import binascii
import io
import ipaddress
import re
import warnings
from PIL import Image

MAX_IMAGEN_BYTES = 4 * 1024 * 1024
MAX_IMAGEN_PIXELES = 16_000_000
MAX_MENSAJES = 40
MAX_CARACTERES = 48_000
MAX_MENSAJE = 12_000
MENSAJE_DATOS_SENSIBLES = (
    "El historial contiene posibles credenciales o direcciones fuera del laboratorio. "
    "Elimina las credenciales y sustituye los datos reales por ejemplos privados o de documentación "
    "en todos los turnos, o inicia una conversación nueva. No se envió al proveedor."
)
# Se bloquean valores, no preguntas conceptuales sobre estos comandos.
OCULTO = "[oculto]"
_CREDENCIAL = re.compile(
    r"\b(?:password|secret|contrase(?:ña|na)|token|api[_-]?key|authorization|community)"
    r"\s*(?:[:=]\s*(?!\[oculto\](?!\S))\S+|\s+(?:es\s+|is\s+)?(?![?¿]|de\b|en\b|para\b|\[oculto\](?!\S))\S+)", re.I
)
_IP = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]*:){2,}[0-9a-fA-F:.]+|\b(?:\d{1,3}\.){3}\d{1,3}\b")
_REDES_LAB = tuple(ipaddress.ip_network(red) for red in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24",
    "2001:db8::/32", "fc00::/7", "fe80::/10", "::1/128",
))


def _es_ip_real(texto: str) -> bool:
    """True si el texto es una dirección fuera de los rangos de laboratorio o documentación."""
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        return False  # No confundir un valor inválido con una dirección real.
    # Máscaras (255.255.255.0) y wildcards de OSPF/ACL (0.0.0.255) no son direcciones de equipos.
    mascara = ip.version == 4 and re.fullmatch(r"1*0*|0*1*", f"{int(ip):032b}")
    return not mascara and not ip.is_unspecified and not any(
        ip.version == red.version and ip in red for red in _REDES_LAB
    )


def contiene_datos_sensibles(texto: str) -> bool:
    if _CREDENCIAL.search(texto or ""):
        return True
    return any(_es_ip_real(coincidencia.group()) for coincidencia in _IP.finditer(texto or ""))


def ocultar_datos_sensibles(texto: str) -> str:
    """Sustituye valores de claves e IP reales por [oculto].

    Se aplica a las respuestas del propio asistente antes de reenviarlas como historial: el modelo
    a veces copia claves de ejemplo de las fichas (enable secret ClaveLab123) y, sin esto, toda la
    conversación quedaba bloqueada después. Los mensajes del usuario se siguen bloqueando, no ocultando.
    """
    texto = _CREDENCIAL.sub(lambda m: re.sub(r"\S+$", OCULTO, m.group(0)), texto or "")
    return _IP.sub(lambda m: OCULTO if _es_ip_real(m.group()) else m.group(), texto)


def validar_historial(mensajes: list[dict]) -> None:
    if not 1 <= len(mensajes) <= MAX_MENSAJES:
        raise ValueError(f"Usa entre 1 y {MAX_MENSAJES} mensajes; inicia otra conversación para continuar.")
    for mensaje in mensajes:
        if mensaje.get("role") not in {"user", "assistant"} or not isinstance(mensaje.get("content"), str) or not 1 <= len(mensaje["content"]) <= MAX_MENSAJE:
            raise ValueError("Cada mensaje debe tener un rol válido y entre 1 y 12000 caracteres.")
    if mensajes[-1]["role"] != "user":
        raise ValueError("El último mensaje debe ser del usuario.")
    if sum(len(m["content"]) for m in mensajes) > MAX_CARACTERES:
        raise ValueError("El historial supera 48000 caracteres. Inicia otra conversación; no se descartaron evidencias automáticamente.")


def validar_imagen(mime: str, data: str) -> None:
    if len(data) > 5_600_000:
        raise ValueError("La imagen supera el límite de 4 MB.")
    try:
        contenido = base64.b64decode(data, validate=True)
        if len(contenido) > MAX_IMAGEN_BYTES:
            raise ValueError("La imagen supera el límite de 4 MB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(contenido)) as imagen:
                if imagen.format != {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}.get(mime):
                    raise ValueError("El formato de la imagen no coincide con el declarado.")
                if imagen.width * imagen.height > MAX_IMAGEN_PIXELES or getattr(imagen, "n_frames", 1) != 1:
                    raise ValueError("Usa una imagen estática de hasta 16 millones de píxeles.")
                imagen.verify()
            with Image.open(io.BytesIO(contenido)) as imagen:
                imagen.load()
    except (binascii.Error, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("La imagen adjunta no se puede decodificar.") from error


def validar_entrada(entrada: dict) -> dict:
    validar_historial(entrada["mensajes"])
    imagen = entrada.get("imagen")
    if imagen:
        if imagen.get("laboratorio_confirmado") is not True:
            raise ValueError("Confirma que revisaste la captura y eliminaste credenciales y datos reales antes de enviarla.")
        validar_imagen(imagen["mime"], imagen["data"])
    return entrada

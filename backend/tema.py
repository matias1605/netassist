"""Filtro de alcance: NetAssist solo responde sobre redes, Cisco IOS y la práctica.

Funciona antes de llamar al modelo, así que una pregunta fuera de tema («¿quién es el
presidente del Perú?») recibe una respuesta fija aunque el modelo hubiera querido contestarla.

Para no rechazar de más, una pregunta solo se considera fuera de tema si se cumplen TODAS:
- no trae imagen (una captura sin texto se analiza siempre);
- no contiene ningún término de redes (vlan, ping, interfaz, router, configurar…);
- no es un saludo o agradecimiento;
- no es un seguimiento de la conversación («¿y eso por qué?», «explícalo mejor»);
- la búsqueda en las fichas con esa pregunta sola no encuentra nada.
"""

import re
import unicodedata
from typing import Any, Callable

MENSAJE_FUERA_DE_TEMA = (
    "Solo puedo ayudarte con redes y Cisco IOS: configuración de equipos, VLAN, conectividad, "
    "comandos y tu práctica de laboratorio. Cuéntame qué problema tienes con tu práctica o tu equipo."
)

# Datos que la app añade a cada mensaje: no cuentan como parte de la pregunta.
_SEPARADOR_PRACTICA = "Datos de mi práctica"

# Palabras exactas (cortas o ambiguas como prefijo).
_EXACTOS = {
    "ip", "ips", "pc", "pcs", "lan", "wan", "vpn", "mac", "nat", "pat", "acl", "dns", "dhcp", "ssh",
    "osi", "tcp", "udp", "rip", "stp", "vtp", "cdp", "lldp", "arp", "icmp", "http", "https", "ftp",
    "red", "redes", "gi", "fa", "g0", "f0", "sw", "isp", "ios", "cli", "vty", "ospf", "eigrp", "bgp",
    "hsrp", "svi", "nic", "wifi", "wlan", "ap", "qos", "mtu", "ttl", "url", "web", "cable", "cables",
    "trunk", "access", "show", "ping", "run", "nexo", "netassist", "lab", "down", "up", "shutdown",
}
# Raíces de palabras (configurar, configuración, conectividad, interfaces…).
_PREFIJOS = (
    "vlan", "switch", "router", "rout", "enrut", "cisco", "interfa", "puerto", "port", "config",
    "conect", "conex", "comando", "topolog", "diagrama", "subred", "subnet", "mascara", "gateway",
    "puerta de enlace", "enlace", "ethernet", "gigabit", "fastethernet", "serial", "consola", "console",
    "telnet", "servidor", "server", "host", "dominio", "hostname", "protocol", "paquete", "trama",
    "broadcast", "multicast", "unicast", "ipv4", "ipv6", "direccion", "direccionamiento", "ruta",
    "tracert", "traceroute", "packet", "tracer", "simulador", "laboratorio", "practica", "equipo",
    "dispositivo", "firewall", "spanning", "etherchannel", "vecin", "latencia", "ancho de banda",
    "velocidad", "duplex", "fibra", "inalambric", "wireless", "modem", "verific", "diagnost",
    "troubleshoot", "falla", "error", "contrasena", "password", "secret", "enable", "privilegi",
    "seguridad", "banner", "respald", "running", "startup", "reinici", "reload", "nvram", "flash",
)
# Seguimientos de la conversación: solo valen si ya hubo intercambio previo.
_SEGUIMIENTO = re.compile(
    r"\b(eso|esto|ese|esa|esos|esas|anterior|arriba|lo mismo|otra vez|de nuevo|explica\w*|detall\w*|"
    r"resum\w*|aclar\w*|ejemplo\w*|paso\w*|y si|sigue|siguiente|"
    r"no funciona|no entiendo|no me sale)\b"
)
_CORTESIA = re.compile(
    r"^\W*(hola|buenas|buenos dias|buenas tardes|buenas noches|gracias|muchas gracias|ok|okay|vale|"
    r"perfecto|genial|listo|entendido|adios|chau|hasta luego)\b"
)


def _normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def pregunta_actual(texto: str) -> str:
    """El texto que escribió la persona, sin los datos de la práctica que añade la app."""
    return (texto or "").split(_SEPARADOR_PRACTICA, 1)[0].strip()


def menciona_redes(texto: str) -> bool:
    """True si la pregunta contiene algún término de redes o del laboratorio."""
    normal = _normalizar(texto)
    if any(prefijo in normal for prefijo in _PREFIJOS if " " in prefijo):
        return True
    palabras = re.findall(r"[a-z0-9/.-]+", normal)
    if any(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", p) for p in palabras):  # una dirección IP
        return True
    if any(re.fullmatch(r"(gi|fa|g|f|e|s)\d+/\d+(/\d+)?", p) for p in palabras):  # Gi0/1, Fa0/2
        return True
    if any(re.fullmatch(r"(pc|r|sw|s|srv)[-_]?\d+", p) for p in palabras):  # PC1, R2, SW1
        return True
    return any(p in _EXACTOS or p.startswith(_PREFIJOS) for p in palabras)


def es_cortesia(texto: str) -> bool:
    return bool(_CORTESIA.match(_normalizar(texto)))


def es_seguimiento(texto: str) -> bool:
    return bool(_SEGUIMIENTO.search(_normalizar(texto)))


def es_fuera_de_tema(entrada: dict[str, Any], buscar: Callable[[str], list]) -> bool:
    """Decide si la última pregunta no tiene relación con redes (ver condiciones arriba)."""
    if entrada.get("imagen"):
        return False
    mensajes = entrada["mensajes"]
    ultima = next((m["content"] for m in reversed(mensajes) if m["role"] == "user"), "")
    pregunta = pregunta_actual(ultima)
    if not pregunta or menciona_redes(pregunta) or es_cortesia(pregunta):
        return False
    if len(mensajes) > 1 and es_seguimiento(pregunta):
        return False
    try:
        return not buscar(pregunta)
    except Exception:
        return False  # si la búsqueda falla, que decida el modelo con sus instrucciones

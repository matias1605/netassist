"""Reglas deterministas para VLAN, puertos de acceso y nombres del escenario.

Verifican coherencia con el escenario; no prueban ningún dispositivo ni sustituyen
la comprobación en simulador. Los campos vacíos se ignoran: los informa `faltantes`.
"""
import re

VLAN_MIN, VLAN_MAX = 2, 4094
VLAN_RESERVADAS = {1: "VLAN 1 es la predeterminada", **{n: "1002-1005 están reservadas (FDDI/Token Ring)" for n in range(1002, 1006)}}

_PUERTO = re.compile(r"^(fastethernet|fa|gigabitethernet|gig|gi)(\d{1,2})/(\d{1,2})(?:/(\d{1,2}))?$", re.IGNORECASE)
_NOMBRE_VLAN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_ALIAS = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,62}$")
_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
# Temas que el generador no cubre; el objetivo es texto libre y no debe aparentar que se atienden.
_FUERA_DE_ALCANCE = re.compile(r"\b(ospf|eigrp|bgp|rip|vpn|ipsec|nat|acl|dhcp|stp|hsrp|etherchannel|trunk|inter-?vlan|router-on-a-stick)\b", re.IGNORECASE)


def normalizar_puerto(texto: str) -> str | None:
    """Forma larga canónica (GigabitEthernet0/1) o None si la sintaxis no es válida."""
    coincidencia = _PUERTO.match(texto.strip())
    if not coincidencia:
        return None
    tipo = "FastEthernet" if coincidencia.group(1).lower() in {"fastethernet", "fa"} else "GigabitEthernet"
    return tipo + "/".join(parte for parte in coincidencia.groups()[1:] if parte is not None)


def validar_tarea(tarea) -> tuple[list[str], list[str]]:
    """Devuelve (errores, advertencias). Cualquier error impide generar la propuesta."""
    errores: list[str] = []
    advertencias: list[str] = []
    if tarea.equipo.alias and not _ALIAS.match(tarea.equipo.alias):
        errores.append("Alias del switch: empieza con letra y usa solo letras, números, guion o guion bajo.")
    if tarea.tipo == "configuracion" and tarea.equipo.modelo and "2960" not in tarea.equipo.modelo:
        advertencias.append("Las fichas disponibles cubren Catalyst 2960; verifica la sintaxis para este modelo.")

    objetivo = tarea.objetivo or ""
    fuera = sorted({m.group(1).upper() for m in _FUERA_DE_ALCANCE.finditer(objetivo)
                    if not re.search(r"\b(sin|no)\b[^.;]{0,40}$", objetivo[:m.start()], re.IGNORECASE)})
    if fuera:
        advertencias.append("El objetivo menciona " + ", ".join(fuera) + ", fuera del alcance (VLAN y puertos de acceso en un switch); la propuesta no lo incluye.")

    nombres_por_vlan: dict[int, str] = {}
    puertos: dict[str, int] = {}
    hosts: dict[str, int] = {}
    for numero, fila in enumerate(tarea.vlans, 1):
        etiqueta = f"Fila {numero}"
        if fila.id:
            if not fila.id.isascii() or not fila.id.isdigit():
                errores.append(f"{etiqueta}: la VLAN debe ser un número entero entre {VLAN_MIN} y {VLAN_MAX}.")
            else:
                vlan = int(fila.id)
                if vlan in VLAN_RESERVADAS:
                    errores.append(f"{etiqueta}: VLAN {vlan} no admitida ({VLAN_RESERVADAS[vlan]}).")
                elif not VLAN_MIN <= vlan <= VLAN_MAX:
                    errores.append(f"{etiqueta}: la VLAN {fila.id} está fuera del rango {VLAN_MIN}-{VLAN_MAX}.")
                elif fila.nombre:
                    previo = nombres_por_vlan.setdefault(vlan, fila.nombre)
                    if previo.lower() != fila.nombre.lower():
                        errores.append(f"{etiqueta}: la VLAN {vlan} tiene dos nombres distintos ({previo} y {fila.nombre}).")
        if fila.nombre and not _NOMBRE_VLAN.match(fila.nombre):
            errores.append(f"{etiqueta}: el nombre de VLAN admite letras, números, guion y guion bajo (máx. 32), sin espacios.")
        if fila.puerto:
            canonico = normalizar_puerto(fila.puerto)
            if canonico is None:
                errores.append(f"{etiqueta}: puerto «{fila.puerto}» inválido; usa p. ej. GigabitEthernet0/1 o Fa0/2.")
            elif canonico in puertos:
                errores.append(f"{etiqueta}: {canonico} ya está asignado en la fila {puertos[canonico]}; un puerto de acceso solo admite una VLAN.")
            else:
                puertos[canonico] = numero
        if fila.host:
            if not _HOST.match(fila.host):
                errores.append(f"{etiqueta}: nombre de equipo conectado inválido.")
            elif fila.host.lower() in hosts:
                errores.append(f"{etiqueta}: el equipo {fila.host} ya está conectado en la fila {hosts[fila.host.lower()]}.")
            else:
                hosts[fila.host.lower()] = numero
            if tarea.equipo.alias and fila.host.lower() == tarea.equipo.alias.lower():
                errores.append(f"{etiqueta}: el equipo conectado no puede llamarse igual que el switch.")
    return errores, advertencias

"""Propuesta estructurada y determinista a partir de datos ya validados.

Los comandos y el diagrama salen de plantillas, no del modelo de lenguaje. El estado de
validación es «reglas_aprobadas»: la comprobación en simulador sigue siendo manual.
"""
import re

from .validadores import normalizar_puerto


def _id_nodo(texto: str, usados: set[str]) -> str:
    base = re.sub(r"\W", "_", texto) or "N"
    if base[0].isdigit():
        base = "N" + base
    nodo, n = base, 2
    while nodo in usados:
        nodo, n = f"{base}_{n}", n + 1
    usados.add(nodo)
    return nodo


def _etiqueta(texto: str) -> str:
    return texto.replace('"', "'")


def generar_topologia(tarea) -> dict:
    """Nodos, enlaces y Mermaid derivados solo de lo declarado; no certifica conectividad."""
    usados: set[str] = set()
    switch = _id_nodo(tarea.equipo.alias, usados)
    nodos = [{"id": switch, "tipo": "switch", "etiqueta": tarea.equipo.alias}]
    enlaces = []
    for fila in tarea.vlans:
        host = _id_nodo(fila.host, usados)
        nodos.append({"id": host, "tipo": "host", "etiqueta": fila.host})
        enlaces.append({"origen": switch, "destino": host, "puerto": normalizar_puerto(fila.puerto), "vlan": int(fila.id), "vlan_nombre": fila.nombre})
    lineas = ["graph LR", f'    {switch}["{_etiqueta(tarea.equipo.alias)}"]']
    lineas += [f'    {n["id"]}["{_etiqueta(n["etiqueta"])}"]' for n in nodos[1:]]
    lineas += [f'    {e["origen"]} -- "{e["puerto"]} · VLAN {e["vlan"]}" --- {e["destino"]}' for e in enlaces]
    return {
        "nodos": nodos, "enlaces": enlaces,
        "datos_confirmados": ["Equipos, puertos y VLAN declarados en el formulario (no observados en dispositivos)."],
        "supuestos": ["Sin direccionamiento IP, trunk ni enrutamiento entre VLAN.", "El diagrama no certifica conectividad."],
        "mermaid": "\n".join(lineas),
    }


def generar_configuracion(tarea) -> dict:
    """Comandos IOS por equipo y verificaciones, a partir de plantillas fijas."""
    comandos = ["configure terminal"]
    vistas: set[int] = set()
    for fila in tarea.vlans:
        vlan = int(fila.id)
        if vlan not in vistas:
            vistas.add(vlan)
            comandos += [f"vlan {vlan}", f" name {fila.nombre}", " exit"]
    for fila in tarea.vlans:
        comandos += [f"interface {normalizar_puerto(fila.puerto)}", f" description {fila.host}",
                     " switchport mode access", f" switchport access vlan {fila.id}", " exit"]
    comandos.append("end")
    verificaciones = ["show vlan brief"] + [f"show interfaces {normalizar_puerto(f.puerto)} switchport" for f in tarea.vlans]
    return {
        "comandos_por_equipo": [{"equipo": tarea.equipo.alias, "comandos": comandos}],
        "verificaciones": verificaciones,
        "advertencias": [
            "Respalda antes con «copy running-config startup-config»: mover un puerto de VLAN puede desconectar el equipo.",
            "Propuesta no ejecutada: pruébala en simulador o laboratorio y adjunta las salidas de verificación.",
        ],
    }


def generar_propuesta(tarea, advertencias: list[str], fuentes: list[str]) -> dict:
    """Contrato de la fase 3: equipos, comandos, verificaciones, advertencias, fuentes y estado."""
    propuesta = {
        "tipo": tarea.tipo,
        "equipos": [{"alias": tarea.equipo.alias, "modelo": tarea.equipo.modelo, "ios": tarea.equipo.ios}],
        "datos_faltantes": [],
        "fuentes": fuentes,
        "estado_validacion": "reglas_aprobadas",
        "comprobacion_laboratorio": "no_realizada",
        "topologia": generar_topologia(tarea),
    }
    if tarea.tipo == "configuracion":
        propuesta.update(generar_configuracion(tarea))
    else:
        propuesta.update(comandos_por_equipo=[], verificaciones=[], advertencias=["Un diagrama de diseño no certifica conectividad."])
    propuesta["advertencias"] = propuesta["advertencias"] + advertencias
    return propuesta


def formatear_propuesta(propuesta: dict, explicacion: str = "") -> str:
    """Markdown compartido por web y Streamlit; el estado de validación nunca se presenta como éxito de laboratorio."""
    partes = []
    for equipo in propuesta["comandos_por_equipo"]:
        partes.append(f"**Comandos propuestos para {equipo['equipo']}:**\n```\n" + "\n".join(equipo["comandos"]) + "\n```")
    if propuesta["verificaciones"]:
        partes.append("**Verificaciones:**\n```\n" + "\n".join(propuesta["verificaciones"]) + "\n```")
    topologia = propuesta["topologia"]
    partes.append("**Topología (según los datos declarados):**\n```mermaid\n" + topologia["mermaid"] + "\n```")
    partes.append("**Advertencias:**\n" + "\n".join(f"- {a}" for a in propuesta["advertencias"]))
    if propuesta["fuentes"]:
        partes.append("**Fuentes:** " + ", ".join(propuesta["fuentes"]))
    if explicacion.strip():
        partes.append("**Explicación (IA):**\n" + explicacion.strip())
    return "\n\n".join(partes)

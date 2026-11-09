"""Informe exportable (Markdown) de un caso: requisitos, propuesta, fuentes, comprobación y evidencias.

Solo reúne lo que el caso tiene guardado. No añade conclusiones: separa lo declarado, lo propuesto,
lo observado en salidas pegadas y lo comprobado a mano en laboratorio.
"""
import re
import unicodedata
from datetime import datetime, timezone

ESTADOS = {
    "borrador": "Borrador (sin propuesta)", "propuesta": "Propuesta generada", "comprobado": "Comprobado en laboratorio",
    "comprobacion_fallida": "Comprobación en laboratorio fallida", "en_diagnostico": "En diagnóstico",
    "diagnostico_coherente": "Salidas coherentes con lo declarado",
}
COMPROBACION = {"no_realizada": "no realizada", "correcta": "correcta", "fallida": "fallida"}
LIMITACIONES = (
    "Los datos del caso son declarados por la persona, no observados en dispositivos. La validación por reglas comprueba coherencia de VLAN y "
    "puertos; las observaciones del diagnóstico comparan salidas pegadas con lo declarado. Ninguna prueba conectividad ni sustituye la "
    "comprobación en simulador o laboratorio. Los comandos propuestos no fueron ejecutados por NetAssist."
)


def _celda(texto) -> str:
    return str(texto).replace("|", "\\|").replace("\n", " ")


def _bloque(texto: str) -> str:
    """Bloque de código que una salida pegada no puede cerrar."""
    return "```\n" + re.sub(r"`{3,}", "'''", texto.strip("\n")) + "\n```"


def nombre_archivo(caso: dict) -> str:
    sin_tildes = unicodedata.normalize("NFKD", caso["tarea"]["nombre"]).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "-", sin_tildes).strip("-").lower()[:40] or "caso"
    return f"informe-{base}-{caso['caso_id'][:8]}.md"


def generar_informe(caso: dict, diagnostico: dict | None = None, evidencias: list[dict] | None = None) -> str:
    tarea, propuesta = caso["tarea"], caso["propuesta"]
    equipo = tarea["equipo"]
    partes = [
        f"# Informe del caso: {tarea['nombre'] or 'Sin nombre'}",
        f"- **Caso:** {caso['caso_id']}\n- **Estado:** {ESTADOS.get(caso['estado'], caso['estado'])}{' (archivado)' if caso.get('archivado') else ''}\n"
        f"- **Creado:** {caso['creado']}\n- **Última actualización:** {caso['actualizado']}\n"
        f"- **Informe generado:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "## Datos declarados",
        f"- **Tipo de tarea:** {tarea['tipo']}\n- **Equipo:** {equipo['alias']} · {equipo['modelo'] or 'modelo no indicado'} · IOS {equipo['ios'] or 'no indicado'}",
        "| VLAN | Nombre | Puerto | Equipo conectado |\n|---|---|---|---|\n"
        + "\n".join(f"| {_celda(v['id'])} | {_celda(v['nombre'])} | {_celda(v['puerto'])} | {_celda(v['host'])} |" for v in tarea["vlans"]),
        f"**Objetivo y requisitos:** {tarea['objetivo'] or 'no indicado'}",
        "## Propuesta",
    ]
    if propuesta is None:
        partes.append("Aún no hay propuesta generada para este caso.")
    else:
        partes.append(f"- **Validación por reglas:** {propuesta['estado_validacion'].replace('_', ' ')}\n"
                      f"- **Comprobación en laboratorio:** {COMPROBACION.get(propuesta['comprobacion_laboratorio'], propuesta['comprobacion_laboratorio'])}\n"
                      f"- **Propuesta creada:** {propuesta['creada']}")
        for equipo_cmd in propuesta["comandos_por_equipo"]:
            partes.append(f"**Comandos propuestos para {equipo_cmd['equipo']} (no ejecutados):**\n" + _bloque("\n".join(equipo_cmd["comandos"])))
        if propuesta["verificaciones"]:
            partes.append("**Verificaciones:**\n" + _bloque("\n".join(propuesta["verificaciones"])))
        partes.append("**Topología (según los datos declarados):**\n```mermaid\n" + propuesta["topologia"]["mermaid"] + "\n```")
        partes.append("**Advertencias:**\n" + "\n".join(f"- {a}" for a in propuesta["advertencias"]))
        partes.append("**Fuentes de la propuesta:** " + (", ".join(propuesta["fuentes"]) if propuesta["fuentes"] else "ninguna registrada"))
        if propuesta.get("explicacion", "").strip():
            partes.append("**Explicación (IA):**\n" + propuesta["explicacion"].strip())
        if propuesta.get("salida_laboratorio"):
            partes.append("## Comprobación manual en laboratorio\n" + _bloque(propuesta["salida_laboratorio"]))

    partes.append("## Diagnóstico con evidencia")
    if diagnostico is None or diagnostico["estado"] == "sin_evidencia":
        partes.append("Aún no se han registrado salidas de verificación.")
    else:
        partes.append(diagnostico["texto"])
    vigentes = [e for e in (evidencias or []) if e["vigente"]]
    obsoletas = len(evidencias or []) - len(vigentes)
    if vigentes:
        partes.append("## Evidencias registradas")
        for e in vigentes:
            observaciones = "\n".join(f"- ({o['severidad']}) {o['texto']}" for o in e["observaciones"])
            partes.append(f"### E{e['id']} · {e['paso']} · {e['resultado']}\nRegistrada: {e['creada']}\n\n{_bloque(e['salida'])}\n\n{observaciones}")
    if obsoletas:
        partes.append(f"{obsoletas} evidencia(s) anterior(es) quedaron fuera de vigencia porque cambiaron los datos declarados del caso.")
    partes += ["## Limitaciones", LIMITACIONES]
    return "\n\n".join(partes) + "\n"

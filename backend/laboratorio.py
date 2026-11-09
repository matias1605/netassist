"""Preparación compartida del espacio de laboratorio; sin ejecución ni persistencia."""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import ROOT_DIR
from .llm import MENSAJE_FALLBACK
from .seguridad import MENSAJE_DATOS_SENSIBLES, contiene_datos_sensibles, validar_historial


class PuertoLaboratorio(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    id: str = Field(default="", max_length=5)
    nombre: str = Field(default="", max_length=32)
    puerto: str = Field(default="", max_length=64)
    host: str = Field(default="", max_length=64)


class EquipoLaboratorio(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    alias: str = Field(default="", max_length=64)
    modelo: str = Field(default="", max_length=120)
    ios: str = Field(default="", max_length=80)


class TareaLaboratorio(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    tipo: Literal["configuracion", "topologia"] = "configuracion"
    nombre: str = Field(default="", max_length=120)
    equipo: EquipoLaboratorio
    vlans: list[PuertoLaboratorio] = Field(min_length=1, max_length=16)
    objetivo: str = Field(default="", max_length=1500)


def ejemplo_laboratorio() -> dict:
    datos = json.loads((ROOT_DIR / "docs" / "datos_prueba_vlan.json").read_text(encoding="utf-8"))
    for vlan in datos["vlans"]:
        vlan["id"] = str(vlan["id"])
    datos.pop("entorno", None)
    return TareaLaboratorio(**datos).model_dump()


def preparar_tarea(tarea: TareaLaboratorio) -> dict:
    """Detecta campos vacíos y prepara un borrador; no certifica VLAN ni puertos."""
    faltantes = []
    if not tarea.nombre:
        faltantes.append("Nombre de la práctica")
    if not tarea.equipo.alias:
        faltantes.append("Alias del switch")
    if tarea.tipo == "configuracion":
        if not tarea.equipo.modelo:
            faltantes.append("Modelo del switch")
        if not tarea.equipo.ios:
            faltantes.append("Versión de IOS")
    if not tarea.objetivo:
        faltantes.append("Objetivo y requisitos")
    for numero, vlan in enumerate(tarea.vlans, 1):
        for campo, titulo in (("id", "VLAN"), ("nombre", "Nombre de VLAN"), ("puerto", "Puerto de acceso"), ("host", "Equipo conectado")):
            if not getattr(vlan, campo):
                faltantes.append(f"Fila {numero}: {titulo}")
    datos = tarea.model_dump()
    instruccion = (
        "Genera una propuesta de configuración Cisco IOS: comandos por equipo, verificaciones y una advertencia breve. "
        "Usa las fichas disponibles; si faltan datos obligatorios, pídelos juntos antes de proponer cambios."
        if tarea.tipo == "configuracion" else
        "Genera únicamente una topología Mermaid (graph LR) y hasta dos frases de alcance. "
        "Muestra los equipos y enlaces declarados con puerto y VLAN; sin comandos de configuración."
    )
    prompt = (
        instruccion + " Responde de forma concisa y precisa. No inventes datos ni conectividad entre VLAN. "
        "Son datos ficticios de laboratorio para un switch con puertos de acceso, sin trunk, IP ni enrutamiento entre VLAN. "
        "Distingue propuesta de comprobación en laboratorio: no ejecutaste comandos ni verificaste dispositivos. "
        "Todavía no se aplicó una validación técnica automática de VLAN o interfaces.\n\n"
        + json.dumps(datos, ensure_ascii=False, indent=2)
    )
    validar_historial([{"role": "user", "content": prompt}])
    if contiene_datos_sensibles(prompt):
        raise ValueError(MENSAJE_DATOS_SENSIBLES)
    return {
        "datos": datos, "faltantes": faltantes, "prompt": prompt,
        "revision": "incompleta" if faltantes else "campos_completos",
        "validacion_tecnica": "pendiente", "comprobacion_laboratorio": "no_realizada",
    }


async def generar_tarea(tarea: TareaLaboratorio, confirmado: bool, cadena) -> dict:
    """Reprepara los datos recibidos y exige revisión explícita; nunca marca éxito de laboratorio."""
    revision = preparar_tarea(tarea)
    if not confirmado:
        raise ValueError("Revisa los datos y confirma antes de generar la propuesta.")
    if revision["faltantes"]:
        raise ValueError("Completa juntos estos datos: " + "; ".join(revision["faltantes"]))
    respuesta = await cadena.ainvoke({"mensajes": [{"role": "user", "content": revision["prompt"]}]})
    estado = "sin_propuesta" if respuesta in {MENSAJE_FALLBACK, MENSAJE_DATOS_SENSIBLES} else "respuesta_generada"
    return {**revision, "estado": estado, "respuesta": respuesta}

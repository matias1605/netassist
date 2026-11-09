"""Preparación compartida del espacio de laboratorio: validación, propuesta y guardado de casos.

No ejecuta comandos ni consulta dispositivos."""
import asyncio
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import ROOT_DIR
from .generador import formatear_propuesta, generar_propuesta
from .llm import MENSAJE_FALLBACK
from .seguridad import MENSAJE_DATOS_SENSIBLES, contiene_datos_sensibles, validar_historial
from .validadores import validar_tarea


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


def _instruccion(tarea: TareaLaboratorio, propuesta: dict | None) -> str:
    if tarea.tipo == "topologia":
        return ("Redacta hasta dos frases de alcance de esta topología de diseño; sin comandos de configuración ni diagrama, "
                "porque el diagrama ya se genera aparte con los enlaces declarados, su puerto y VLAN.")
    if propuesta is None:
        return ("Genera una propuesta de configuración Cisco IOS: comandos por equipo, verificaciones y una advertencia breve. "
                "Usa las fichas disponibles; si faltan datos obligatorios, pídelos juntos antes de proponer cambios.")
    comandos = "\n".join(propuesta["comandos_por_equipo"][0]["comandos"])
    return ("La propuesta de comandos ya fue generada por plantilla y aprobada por reglas de VLAN y puertos. "
            "Explica en pocas frases qué hace y qué verificar; no cambies, quites ni añadas comandos.\n"
            f"Comandos:\n{comandos}\nVerificaciones: " + "; ".join(propuesta["verificaciones"]) + ".")


def preparar_tarea(tarea: TareaLaboratorio) -> dict:
    """Detecta faltantes, aplica los validadores y prepara la propuesta determinista y el prompt."""
    faltantes = []
    if not tarea.nombre:
        faltantes.append("Nombre de la práctica")
    if not tarea.equipo.alias:
        faltantes.append("Alias del switch")
    # La versión de IOS y el objetivo son opcionales: el estudiante describe lo que quiere directamente en el chat.
    if tarea.tipo == "configuracion" and not tarea.equipo.modelo:
        faltantes.append("Modelo del switch")
    for numero, vlan in enumerate(tarea.vlans, 1):
        for campo, titulo in (("id", "VLAN"), ("nombre", "Nombre de VLAN"), ("puerto", "Puerto de acceso"), ("host", "Equipo conectado")):
            if not getattr(vlan, campo):
                faltantes.append(f"Fila {numero}: {titulo}")
    errores, advertencias = validar_tarea(tarea)
    validacion = "rechazada" if errores else "incompleta" if faltantes else "reglas_aprobadas"
    propuesta = generar_propuesta(tarea, advertencias, []) if validacion == "reglas_aprobadas" else None
    datos = tarea.model_dump()
    prompt = (
        _instruccion(tarea, propuesta) + " Responde de forma concisa y precisa. No inventes datos ni conectividad entre VLAN. "
        "Son datos ficticios de laboratorio para un switch con puertos de acceso, sin trunk, IP ni enrutamiento entre VLAN. "
        "Distingue propuesta de comprobación en laboratorio: no ejecutaste comandos ni verificaste dispositivos. "
        "La validación por reglas comprueba coherencia de VLAN y puertos, no el funcionamiento en dispositivos.\n\n"
        + json.dumps(datos, ensure_ascii=False, indent=2)
    )
    validar_historial([{"role": "user", "content": prompt}])
    if contiene_datos_sensibles(prompt):
        raise ValueError(MENSAJE_DATOS_SENSIBLES)
    return {
        "datos": datos, "faltantes": faltantes, "errores": errores, "advertencias": advertencias, "prompt": prompt,
        "revision": "rechazada" if errores else "incompleta" if faltantes else "campos_completos",
        "validacion_tecnica": validacion, "comprobacion_laboratorio": "no_realizada", "propuesta": propuesta,
        "texto_previo": formatear_propuesta(propuesta) if propuesta else "",
    }


def guardar_practica(tarea: TareaLaboratorio, almacen, caso_id: str | None = None, usuario: str | None = None) -> dict:
    """Guarda los datos de la práctica como caso (borrador) sin llamar a la IA.

    Exige que los datos pasen las reglas; el nombre guardado es siempre el que escribió la persona."""
    revision = preparar_tarea(tarea)
    if revision["errores"]:
        raise ValueError("Corrige estos datos: " + " ".join(revision["errores"]))
    if revision["faltantes"]:
        raise ValueError("Completa juntos estos datos: " + "; ".join(revision["faltantes"]))
    caso_id = almacen.guardar_caso(revision["datos"], caso_id, usuario)
    return {"caso_id": caso_id, "estado": "practica_guardada", "comprobacion_laboratorio": "no_realizada"}


def guardar_sesion(tarea: TareaLaboratorio, resumen: str, almacen, caso_id: str | None = None, usuario: str | None = None) -> dict:
    """Guarda como caso el resumen que Nexo dio en el chat, sin volver a llamar a la IA.

    Solo se guarda si los datos del formulario pasan las reglas; la propuesta determinista acompaña al resumen."""
    revision = preparar_tarea(tarea)
    if revision["errores"]:
        raise ValueError("Corrige estos datos: " + " ".join(revision["errores"]))
    if revision["faltantes"]:
        raise ValueError("Completa juntos estos datos: " + "; ".join(revision["faltantes"]))
    if contiene_datos_sensibles(resumen):
        raise ValueError(MENSAJE_DATOS_SENSIBLES)
    caso_id = almacen.guardar_caso(revision["datos"], caso_id, usuario)
    almacen.guardar_propuesta(caso_id, revision["propuesta"], resumen, usuario)
    return {"caso_id": caso_id, "estado": "resumen_guardado", "comprobacion_laboratorio": "no_realizada"}


async def _fuentes(rag, consulta: str = "configurar VLAN y puertos de acceso switchport") -> list[str]:
    if rag is None:
        return []
    try:
        fragmentos = await asyncio.to_thread(rag.buscar, consulta)
    except Exception:
        return []
    return sorted({str(f["archivo"]) for f in fragmentos})


async def generar_tarea(tarea: TareaLaboratorio, confirmado: bool, cadena, rag=None, almacen=None, caso_id: str | None = None, usuario: str | None = None) -> dict:
    """Exige revisión explícita y reglas aprobadas; con `almacen` guarda el caso y la propuesta."""
    revision = preparar_tarea(tarea)
    if not confirmado:
        raise ValueError("Revisa los datos y confirma antes de generar la propuesta.")
    if revision["faltantes"]:
        raise ValueError("Completa juntos estos datos: " + "; ".join(revision["faltantes"]))
    if revision["errores"]:
        raise ValueError("Corrige estos datos: " + " ".join(revision["errores"]))
    revision["propuesta"]["fuentes"] = await _fuentes(rag)
    respuesta = await cadena.ainvoke({"mensajes": [{"role": "user", "content": revision["prompt"]}]})
    estado = "propuesta_sin_explicacion" if respuesta in {MENSAJE_FALLBACK, MENSAJE_DATOS_SENSIBLES} else "respuesta_generada"
    explicacion = respuesta if estado == "respuesta_generada" else ""
    resultado = {**revision, "estado": estado, "respuesta": respuesta, "caso_id": None,
                 "texto": formatear_propuesta(revision["propuesta"], explicacion) + ("" if explicacion else "\n\n" + respuesta)}
    if almacen is not None:
        resultado["caso_id"] = almacen.guardar_caso(revision["datos"], caso_id, usuario)
        almacen.guardar_propuesta(resultado["caso_id"], revision["propuesta"], explicacion, usuario)
    return resultado

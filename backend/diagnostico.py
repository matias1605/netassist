"""Analizador determinista de salidas de `show vlan brief` y `show interfaces <puerto> switchport`.

Compara lo observado con lo declarado en el caso. No ejecuta comandos ni consulta dispositivos:
solo interpreta texto que la persona pegó. Una salida coherente con la configuración declarada no
prueba conectividad. Cada observación se devuelve con su severidad (ok, problema, aviso, ambiguo)
y, cuando procede, los comandos de corrección de la misma plantilla del generador.
"""
import re

from .validadores import normalizar_puerto

CLAVE_VLAN = "vlan_brief"
_PROMPT = re.compile(r"^\s*[\w.\-]+(?:\([\w\-]+\))?#\s*(show\s+.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_CABECERA_VLAN = re.compile(r"^\s*VLAN\s+Name\s+Status\s+Ports\s*$", re.IGNORECASE | re.MULTILINE)
_FILA_VLAN = re.compile(r"^(\d{1,4})\s+(\S+)\s+(active|act/unsup|suspended|act/lshut|sus/lshut|act/ishut|sus/ishut)\b\s*(.*)$", re.IGNORECASE)
_CONTINUACION = re.compile(r"^\s+([A-Za-z]{2}[\w/]*\d.*)$")
_NOMBRE_PUERTO = re.compile(r"^\s*Name:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)


def esperado_desde_tarea(tarea: dict) -> list[dict]:
    """Conexiones declaradas con puerto canónico; ignora filas que los validadores habrían rechazado."""
    filas = []
    for fila in tarea["vlans"]:
        puerto = normalizar_puerto(fila.get("puerto", ""))
        if puerto and str(fila.get("id", "")).isdigit():
            filas.append({"vlan": int(fila["id"]), "nombre": fila.get("nombre", ""), "puerto": puerto, "host": fila.get("host", "")})
    return filas


def pasos_base(esperado: list[dict]) -> list[dict]:
    """Pasos de verificación del escenario: uno por tabla de VLAN y uno por puerto declarado."""
    pasos = [{"clave": CLAVE_VLAN, "titulo": "Comprobar las VLAN declaradas", "comando": "show vlan brief"}]
    for fila in esperado:
        pasos.append({"clave": f"switchport:{fila['puerto']}", "titulo": f"Comprobar el puerto {fila['puerto']} ({fila['host']})",
                      "comando": f"show interfaces {fila['puerto']} switchport"})
    return pasos


def dividir_bloques(texto: str) -> list[str]:
    """Separa varias salidas pegadas juntas: por líneas de prompt (SW1#show …), por cada «Name:» de un
    switchport o por cada cabecera de la tabla de VLAN. Un marcador pegado a su prompt no abre otro bloque."""
    marcadores = sorted([(m.start(), True, m.end()) for m in _PROMPT.finditer(texto)]
                        + [(m.start(), False, m.end()) for m in _NOMBRE_PUERTO.finditer(texto)]
                        + [(m.start(), False, m.end()) for m in _CABECERA_VLAN.finditer(texto)])
    limites: list[int] = []
    ultimo_prompt_fin = None
    for inicio, es_prompt, fin in marcadores:
        if not es_prompt and ultimo_prompt_fin is not None and not texto[ultimo_prompt_fin:inicio].strip():
            continue
        limites.append(inicio)
        ultimo_prompt_fin = fin if es_prompt else None
    if not limites:
        return [texto.strip("\n")] if texto.strip() else []
    if limites[0] > 0 and texto[:limites[0]].strip():
        limites.insert(0, 0)
    limites.append(len(texto))
    return [b.strip("\n") for b in (texto[limites[i]:limites[i + 1]] for i in range(len(limites) - 1)) if b.strip()]


def _obs(severidad: str, texto: str, correccion: list[str] | None = None, **extra) -> dict:
    return {"severidad": severidad, "texto": texto, "correccion": correccion or [], **extra}


def _corregir_vlan(fila: dict) -> list[str]:
    return [f"vlan {fila['vlan']}", f" name {fila['nombre']}", " exit"]


def _corregir_puerto(fila: dict) -> list[str]:
    return [f"interface {fila['puerto']}", " switchport mode access", f" switchport access vlan {fila['vlan']}", " exit"]


def _tabla_vlan(texto: str) -> dict[int, dict]:
    vlans: dict[int, dict] = {}
    ultima = None
    for linea in texto.splitlines():
        fila = _FILA_VLAN.match(linea.strip())
        if fila:
            ultima = vlans.setdefault(int(fila.group(1)), {"nombre": fila.group(2), "estado": fila.group(3).lower(), "puertos": []})
            texto_puertos = fila.group(4)
        else:
            continuacion = _CONTINUACION.match(linea) if ultima is not None else None
            if not continuacion:
                continue
            texto_puertos = continuacion.group(1)
        for puerto in (p.strip() for p in texto_puertos.split(",")):
            if puerto:
                ultima["puertos"].append(normalizar_puerto(puerto) or puerto)
    return vlans


def _analizar_vlan(texto: str, esperado: list[dict]) -> dict:
    vlans = _tabla_vlan(texto)
    if not vlans:
        return {"tipo": "vlan_brief", "clave": CLAVE_VLAN, "observaciones": [
            _obs("ambiguo", "La tabla de VLAN está vacía o cortada. Pega la salida completa de «show vlan brief», con la cabecera y las filas.")]}
    observaciones = []
    declarados_por_vlan: dict[int, set[str]] = {}
    for fila in esperado:
        declarados_por_vlan.setdefault(fila["vlan"], set()).add(fila["puerto"])
    for numero in sorted(declarados_por_vlan):
        fila = next(f for f in esperado if f["vlan"] == numero)
        actual = vlans.get(numero)
        if actual is None:
            observaciones.append(_obs("problema", f"La VLAN {numero} ({fila['nombre']}) no aparece en la tabla.", _corregir_vlan(fila), vlan=numero))
        elif actual["nombre"].lower() != fila["nombre"].lower():
            observaciones.append(_obs("problema", f"La VLAN {numero} se llama «{actual['nombre']}» y el caso declara «{fila['nombre']}».", _corregir_vlan(fila), vlan=numero))
        else:
            observaciones.append(_obs("ok", f"La VLAN {numero} existe con el nombre declarado ({fila['nombre']}).", vlan=numero))
    for fila in esperado:
        puerto, numero = fila["puerto"], fila["vlan"]
        donde = next((v for v, datos in vlans.items() if puerto in datos["puertos"]), None)
        if donde == numero:
            observaciones.append(_obs("ok", f"{puerto} figura en la VLAN {numero}.", puerto=puerto, vlan=numero))
        elif donde is not None:
            observaciones.append(_obs("problema", f"{puerto} figura en la VLAN {donde} y el caso declara la VLAN {numero}.", _corregir_puerto(fila), puerto=puerto, vlan=numero))
        else:
            observaciones.append(_obs("ambiguo", f"{puerto} no figura en ninguna VLAN de la tabla (un puerto troncal o no conmutado no aparece). "
                                      f"Aclara con «show interfaces {puerto} switchport».", puerto=puerto, vlan=numero))
    for numero, ports in declarados_por_vlan.items():
        extra = [p for p in vlans.get(numero, {}).get("puertos", []) if p not in ports]
        if extra:
            observaciones.append(_obs("aviso", f"La VLAN {numero} incluye puertos no declarados en el caso: {', '.join(extra)}.", vlan=numero))
    return {"tipo": "vlan_brief", "clave": CLAVE_VLAN, "observaciones": observaciones}


def _campo(texto: str, nombre: str) -> str | None:
    m = re.search(rf"^\s*{nombre}:\s*(.+?)\s*$", texto, re.IGNORECASE | re.MULTILINE)
    return m.group(1) if m else None


def _analizar_switchport(texto: str, esperado: list[dict]) -> dict:
    crudo = _campo(texto, "Name")
    puerto = normalizar_puerto(crudo) if crudo else None
    if puerto is None:
        return {"tipo": "switchport", "clave": None, "observaciones": [
            _obs("ambiguo", "No se identifica la interfaz. Pega la salida completa de «show interfaces <puerto> switchport», incluida la línea «Name:».")]}
    fila = next((f for f in esperado if f["puerto"] == puerto), None)
    if fila is None:
        return {"tipo": "switchport", "clave": None, "observaciones": [
            _obs("ambiguo", f"{puerto} no está declarado en el caso. ¿Es el puerto correcto o falta añadirlo al caso?", puerto=puerto)]}
    clave = f"switchport:{puerto}"
    habilitado = _campo(texto, "Switchport")
    admin = _campo(texto, "Administrative Mode")
    operativo = _campo(texto, "Operational Mode")
    vlan = re.search(r"Access Mode VLAN:\s*(\d+|unassigned)(?:\s*\(([^)]*)\))?", texto, re.IGNORECASE)
    if habilitado is None or admin is None or vlan is None:
        return {"tipo": "switchport", "clave": clave, "observaciones": [
            _obs("ambiguo", f"La salida de {puerto} está incompleta (faltan Switchport, Administrative Mode o Access Mode VLAN). Pégala completa.", puerto=puerto)]}
    observaciones = []
    if habilitado.lower() != "enabled":
        observaciones.append(_obs("problema", f"{puerto} no está como puerto conmutado (Switchport: {habilitado}).", ["interface " + puerto, " switchport"] + _corregir_puerto(fila)[1:], puerto=puerto))
    elif admin.lower() != "static access":
        observaciones.append(_obs("problema", f"{puerto} está en modo «{admin}»; el caso declara puerto de acceso.", _corregir_puerto(fila), puerto=puerto))
    elif vlan.group(1).lower() == "unassigned" or int(vlan.group(1)) != fila["vlan"]:
        observaciones.append(_obs("problema", f"{puerto} está en la VLAN {vlan.group(1)} y el caso declara la VLAN {fila['vlan']}.", _corregir_puerto(fila), puerto=puerto, vlan=fila["vlan"]))
    else:
        observaciones.append(_obs("ok", f"{puerto} es puerto de acceso en la VLAN {fila['vlan']}, como declara el caso.", puerto=puerto, vlan=fila["vlan"]))
        if operativo and operativo.lower() == "down":
            observaciones.append(_obs("aviso", f"{puerto} figura sin enlace (Operational Mode: down). La configuración es coherente, pero no se confirma el enlace con {fila['host']}.", puerto=puerto))
    return {"tipo": "switchport", "clave": clave, "observaciones": observaciones}


def analizar_bloque(texto: str, esperado: list[dict]) -> dict:
    """Detecta el tipo de salida y la compara con lo declarado. `clave` es el paso afectado o None."""
    if _CABECERA_VLAN.search(texto):
        resultado = _analizar_vlan(texto, esperado)
    elif re.search(r"Administrative Mode:", texto, re.IGNORECASE) or (_NOMBRE_PUERTO.search(texto) and re.search(r"^\s*Switchport:", texto, re.IGNORECASE | re.MULTILINE)):
        resultado = _analizar_switchport(texto, esperado)
    else:
        return {"tipo": "desconocido", "clave": None, "resultado": "no_reconocida", "observaciones": [
            _obs("ambiguo", "No se reconoce la salida. Pega la salida completa de «show vlan brief» o de «show interfaces <puerto> switchport».")]}
    severidades = {o["severidad"] for o in resultado["observaciones"]}
    resultado["resultado"] = "problema" if "problema" in severidades else "ambiguo" if "ambiguo" in severidades else "ok"
    return resultado


def estado_paso(resultado: str) -> str:
    return {"ok": "completado", "problema": "con_hallazgos", "ambiguo": "ambiguo"}[resultado]


def resumir(pasos: list[dict]) -> dict:
    """Resumen del diagnóstico a partir de los pasos con su última evidencia vigente.

    Cada paso: clave, titulo, comando, estado y, si hay evidencia, `evidencia` con id y observaciones.
    """
    hallazgos, aclaraciones, avisos, siguientes, correcciones = [], [], [], [], []
    for paso in pasos:
        evidencia = paso.get("evidencia")
        for obs in (evidencia["observaciones"] if evidencia else []):
            item = {"evidencia_id": evidencia["id"], "paso": paso["clave"], "texto": obs["texto"]}
            if obs["severidad"] == "problema":
                hallazgos.append(item)
                if obs["correccion"] and obs["correccion"] not in correcciones:
                    correcciones.append(obs["correccion"])
            elif obs["severidad"] == "ambiguo":
                aclaraciones.append(item)
            elif obs["severidad"] == "aviso":
                avisos.append(item)
        if paso["estado"] == "pendiente":
            siguientes.append({"paso": paso["clave"], "accion": f"Ejecuta «{paso['comando']}» y pega la salida."})
        elif paso["estado"] == "con_hallazgos":
            siguientes.append({"paso": paso["clave"], "accion": f"Aplica la corrección y repite «{paso['comando']}»."})
        elif paso["estado"] == "ambiguo":
            siguientes.append({"paso": paso["clave"], "accion": f"Aclara y vuelve a pegar la salida de «{paso['comando']}»."})
    estados = {p["estado"] for p in pasos}
    if estados == {"pendiente"} or not pasos:
        estado = "sin_evidencia"
    elif "con_hallazgos" in estados:
        estado = "con_hallazgos"
    elif "ambiguo" in estados:
        estado = "requiere_aclaracion"
    elif "pendiente" in estados:
        estado = "en_curso"
    else:
        estado = "coherente"
    comandos = [c for bloque in correcciones for c in bloque]
    return {
        "estado": estado, "hallazgos": hallazgos, "aclaraciones": aclaraciones, "avisos": avisos, "siguientes": siguientes,
        "correccion_propuesta": (["configure terminal"] + comandos + ["end"]) if comandos else [],
    }


def formatear_diagnostico(diagnostico: dict) -> str:
    """Markdown compartido por web y Streamlit. «Coherente» nunca se presenta como conectividad probada."""
    etiquetas = {"sin_evidencia": "Sin evidencia", "en_curso": "En curso: faltan pasos", "con_hallazgos": "Hay discrepancias con lo declarado",
                 "requiere_aclaracion": "Se requiere aclaración", "coherente": "Salidas coherentes con lo declarado"}
    partes = [f"**Estado del diagnóstico:** {etiquetas[diagnostico['estado']]}"]
    iconos = {"pendiente": "⬜", "completado": "✅", "con_hallazgos": "❌", "ambiguo": "❓"}
    partes.append("**Pasos:**\n" + "\n".join(
        f"- {iconos[p['estado']]} {p['titulo']} · `{p['comando']}`" + (f" (evidencia E{p['evidencia']['id']})" if p.get("evidencia") else "")
        for p in diagnostico["pasos"]))
    if diagnostico["hallazgos"]:
        partes.append("**Hallazgos:**\n" + "\n".join(f"- [E{h['evidencia_id']}] {h['texto']}" for h in diagnostico["hallazgos"]))
    if diagnostico["correccion_propuesta"]:
        partes.append("**Corrección propuesta (no ejecutada):**\n```\n" + "\n".join(diagnostico["correccion_propuesta"]) + "\n```")
    if diagnostico["aclaraciones"]:
        partes.append("**Aclaraciones necesarias:**\n" + "\n".join(f"- [E{a['evidencia_id']}] {a['texto']}" for a in diagnostico["aclaraciones"]))
    if diagnostico["avisos"]:
        partes.append("**Avisos:**\n" + "\n".join(f"- [E{a['evidencia_id']}] {a['texto']}" for a in diagnostico["avisos"]))
    if diagnostico["siguientes"]:
        partes.append("**Siguientes pasos:**\n" + "\n".join(f"- {s['accion']}" for s in diagnostico["siguientes"]))
    if diagnostico.get("fuentes"):
        partes.append("**Fuentes:** " + ", ".join(diagnostico["fuentes"]))
    partes.append("Las observaciones comparan la salida pegada con los datos declarados del caso; no prueban conectividad ni sustituyen la comprobación en laboratorio.")
    return "\n\n".join(partes)

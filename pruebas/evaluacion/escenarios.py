"""Evaluación reproducible de la fase 6.

Ejecuta escenarios completos de NetAssist (API real, base SQLite temporal, validadores,
generador y analizador reales) con los proveedores de IA y el índice sustituidos por
dobles controlados. Sin red, claves ni modelos: mide el comportamiento del producto,
no la calidad del texto de un modelo de lenguaje.

    .venv/Scripts/python.exe pruebas/evaluacion/escenarios.py
"""
import base64
import copy
import io
import json
import logging
import re
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "pruebas" / "automatizadas")]

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from backend import llm, main  # noqa: E402
from backend.casos import AlmacenCasos  # noqa: E402
from backend.laboratorio import ejemplo_laboratorio  # noqa: E402
from backend.seguridad import MENSAJE_DATOS_SENSIBLES  # noqa: E402
from test_fase4 import SW_OK_1, SW_OK_2, VLAN_OK, VLAN_PUERTO_EN_DEFAULT  # noqa: E402

ANA, LUIS = "ana-evaluacion-0000001", "luis-evaluacion-000002"
COMANDOS_ESPERADOS = ["vlan 10", " name ADMINISTRACION", "vlan 20", " name LABORATORIO",
                      " switchport access vlan 10", " switchport access vlan 20", " switchport mode access"]


class Proveedores:
    """Dobles de Gemini y Groq: cuentan llamadas y fallan o responden según el guion."""

    def __init__(self):
        self.llamadas = {"gemini": 0, "groq": 0}

    def doble(self, nombre, guion):
        async def llamar(mensajes, prompt, imagen=None):
            self.llamadas[nombre] += 1
            if isinstance(guion, Exception):
                raise guion
            return guion
        return llamar


class Cadena:
    """Cadena mínima que usa la política de respaldo real (`generar_con_respaldo`)."""

    async def ainvoke(self, entrada):
        return await llm.generar_con_respaldo(entrada["mensajes"], "sistema de evaluación", entrada.get("imagen"))


@contextmanager
def entorno(gemini="Explicación Gemini.", groq="Explicación Groq.", rag="ok"):
    prov = Proveedores()
    with tempfile.TemporaryDirectory() as tmp:
        buscar = MagicMock(return_value=[{"archivo": "cisco_ios_basico.txt"}])
        if rag == "falla":
            buscar = MagicMock(side_effect=RuntimeError("índice no disponible"))
        parches = [
            patch.object(main, "almacen", AlmacenCasos(Path(tmp) / "casos.db")),
            patch.object(main, "cadena", Cadena()),
            patch.object(main.rag_service, "buscar", buscar),
            patch.object(llm, "_llamar_gemini", prov.doble("gemini", gemini)),
            patch.object(llm, "_llamar_groq", prov.doble("groq", groq)),
        ]
        for p in parches:
            p.start()
        main.app.state.rag_error = "caído" if rag == "indice_caido" else None
        try:
            yield TestClient(main.app), prov
        finally:
            for p in reversed(parches):
                p.stop()
            main.app.state.rag_error = None


def datos(**cambios):
    d = copy.deepcopy(ejemplo_laboratorio())
    d.update(cambios)
    return d


def generar(c, tarea, usuario=ANA, **extra):
    return c.post("/laboratorio/generar", json={"tarea": tarea, "confirmado": True, **extra}, headers={"X-Usuario": usuario})


def comandos(resp):
    return [x for e in resp["propuesta"]["comandos_por_equipo"] for x in e["comandos"]]


def png():
    salida = io.BytesIO()
    Image.new("RGB", (8, 8)).save(salida, format="PNG")
    return {"mime": "image/png", "data": base64.b64encode(salida.getvalue()).decode(), "laboratorio_confirmado": True}


def caso_nuevo(c):
    return generar(c, datos()).json()["caso_id"]


ESCENARIOS: list = []
# Configuración de entorno de cada escenario (por defecto: proveedores sanos e índice sano).
CONFIG: dict = {}


def escenario(id_, area, nombre, **config):
    def registrar(f):
        ESCENARIOS.append((id_, area, nombre, f))
        if config:
            CONFIG[id_] = config
        return f
    return registrar


FALLA = RuntimeError("proveedor caído")

# ---------------------------------------------------------------- Configuración
@escenario("CF1", "Configuración", "Datos completos: comandos y verificaciones deterministas")
def _(c, p):
    r = generar(c, datos())
    j = r.json()
    ok = (r.status_code == 200 and j["propuesta"]["estado_validacion"] == "reglas_aprobadas"
          and all(x in comandos(j) for x in COMANDOS_ESPERADOS) and len(j["propuesta"]["verificaciones"]) == 3)
    return ok, f"HTTP {r.status_code}; {len(comandos(j))} comandos; estado {j['propuesta']['estado_validacion']}"


@escenario("CF2", "Configuración", "Modelo ausente: se pide el dato y no se llama a la IA")
def _(c, p):
    t = datos()
    t["equipo"]["modelo"] = ""
    faltantes = c.post("/laboratorio/preparar", json=t).json()["faltantes"]
    r = generar(c, t)
    return r.status_code == 422 and faltantes == ["Modelo del switch"] and sum(p.llamadas.values()) == 0, f"HTTP {r.status_code}; faltantes {faltantes}; llamadas IA {sum(p.llamadas.values())}"


@escenario("CF3", "Configuración", "VLAN inválida (4095) rechazada sin llamar a la IA ni guardar el caso")
def _(c, p):
    t = datos()
    t["vlans"][0]["id"] = "4095"
    r = generar(c, t)
    ok = r.status_code == 422 and sum(p.llamadas.values()) == 0 and c.get("/casos", headers={"X-Usuario": ANA}).json() == []
    return ok, f"HTTP {r.status_code}; sin caso guardado"


@escenario("CF4", "Configuración", "Puerto repetido en dos VLAN rechazado")
def _(c, p):
    t = datos()
    t["vlans"][1]["puerto"] = t["vlans"][0]["puerto"]
    r = generar(c, t)
    return r.status_code == 422 and sum(p.llamadas.values()) == 0, f"HTTP {r.status_code}"


@escenario("CF5", "Configuración", "Objetivo fuera del alcance (OSPF): advertencia explícita")
def _(c, p):
    r = generar(c, datos(objetivo="Configurar OSPF entre dos routers"))
    adv = r.json()["propuesta"]["advertencias"] if r.status_code == 200 else []
    return any("OSPF" in a and "fuera del alcance" in a for a in adv), f"HTTP {r.status_code}; {len(adv)} advertencias"


@escenario("CF6", "Configuración", "Objetivo que excluye trunk/IP no genera falso aviso de alcance")
def _(c, p):
    adv = generar(c, datos()).json()["propuesta"]["advertencias"]
    return not any("fuera del alcance" in a for a in adv), f"{len(adv)} advertencias, ninguna de alcance"


@escenario("CF7", "Configuración", "Modelo distinto de 2960: advertencia, no bloqueo")
def _(c, p):
    t = datos()
    t["equipo"]["modelo"] = "Cisco Catalyst 3850"
    r = generar(c, t)
    return r.status_code == 200 and any("2960" in a for a in r.json()["propuesta"]["advertencias"]), f"HTTP {r.status_code}"


# ---------------------------------------------------------------- Topología
@escenario("TP1", "Topología", "Dos PC y un switch: nodos, enlaces y Mermaid")
def _(c, p):
    t = generar(c, datos(tipo="topologia")).json()["propuesta"]["topologia"]
    return len(t["nodos"]) == 3 and len(t["enlaces"]) == 2 and t["mermaid"].startswith("graph"), f"{len(t['nodos'])} nodos, {len(t['enlaces'])} enlaces"


@escenario("TP2", "Topología", "Datos incompletos (puerto y host ausentes): se piden juntos")
def _(c, p):
    t = datos(tipo="topologia")
    t["vlans"][0]["puerto"] = ""
    t["vlans"][1]["host"] = ""
    faltantes = c.post("/laboratorio/preparar", json=t).json()["faltantes"]
    r = generar(c, t)
    return r.status_code == 422 and len(faltantes) == 2 and sum(p.llamadas.values()) == 0, f"HTTP {r.status_code}; faltantes {faltantes}"


@escenario("TP3", "Topología", "Sin IP declarada: no se inventa direccionamiento")
def _(c, p):
    j = generar(c, datos(tipo="topologia")).json()
    texto = json.dumps(j["propuesta"]) + j["texto"]
    ok = any("Sin direccionamiento IP" in s for s in j["propuesta"]["topologia"]["supuestos"]) and not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", texto)
    return ok, "supuesto declarado; ninguna dirección IPv4 en la salida"


@escenario("TP4", "Topología", "Enlace no declarado: solo aparecen los enlaces del formulario")
def _(c, p):
    t = generar(c, datos(tipo="topologia")).json()["propuesta"]["topologia"]
    ok = sorted(e["puerto"] for e in t["enlaces"]) == ["GigabitEthernet0/1", "GigabitEthernet0/2"] and "El diagrama no certifica conectividad." in t["supuestos"]
    return ok, f"{len(t['enlaces'])} enlaces declarados"


# ---------------------------------------------------------------- Continuidad
@escenario("CT1", "Continuidad", "Reabrir el caso conserva datos y propuesta")
def _(c, p):
    cid = caso_nuevo(c)
    j = c.get(f"/casos/{cid}", headers={"X-Usuario": ANA}).json()
    return j["caso_id"] == cid and bool(j.get("propuesta")) and j["tarea"]["equipo"]["alias"] == "SW1", f"estado {j.get('estado')}"


@escenario("CT2", "Continuidad", "Misma salida pegada dos veces: no se duplica ni repite el paso")
def _(c, p):
    cid, h = caso_nuevo(c), {"X-Usuario": ANA}
    c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_OK}, headers=h)
    r = c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_OK}, headers=h)
    n = len(c.get(f"/casos/{cid}/evidencias", headers=h).json())
    return n == 1 and bool(r.json().get("omitidos")), f"{n} evidencia; omitidos {len(r.json().get('omitidos', []))}"


@escenario("CT3", "Continuidad", "Hallazgo → corrección → resolución confirmada con historial")
def _(c, p):
    cid, h = caso_nuevo(c), {"X-Usuario": ANA}
    c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_PUERTO_EN_DEFAULT}, headers=h)
    antes = c.get(f"/casos/{cid}/diagnostico", headers=h).json()["estado"]
    c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_OK + SW_OK_1 + SW_OK_2}, headers=h)
    despues = c.get(f"/casos/{cid}/diagnostico", headers=h).json()["estado"]
    historial = len(c.get(f"/casos/{cid}/evidencias", headers=h).json())
    return antes == "con_hallazgos" and despues == "coherente" and historial >= 4, f"{antes} → {despues}; {historial} evidencias en historial"


@escenario("CT4", "Continuidad", "Salida cortada: ambigua, pide aclaración y no afirma error")
def _(c, p):
    cid, h = caso_nuevo(c), {"X-Usuario": ANA}
    c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_OK.replace("Gi0/2", "    ")}, headers=h)
    estado = c.get(f"/casos/{cid}/diagnostico", headers=h).json()["estado"]
    return estado == "requiere_aclaracion", f"estado {estado}"


@escenario("CT5", "Continuidad", "Informe exportable con comandos, fuentes y evidencias")
def _(c, p):
    cid, h = caso_nuevo(c), {"X-Usuario": ANA}
    c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_OK + SW_OK_1 + SW_OK_2}, headers=h)
    md = c.get(f"/casos/{cid}/informe", headers=h).json()["markdown"]
    return all(x in md for x in ("switchport access vlan 10", "cisco_ios_basico.txt", "coherentes con lo declarado")), f"{len(md)} caracteres"


# ---------------------------------------------------------------- Proveedores
@escenario("PV1", "Proveedores", "Primario caído: responde el respaldo", gemini=FALLA)
def _(c, p):
    j = generar(c, datos()).json()
    return j["estado"] == "respuesta_generada" and p.llamadas == {"gemini": 1, "groq": 1} and "Groq" in j["respuesta"], f"llamadas {p.llamadas}"


@escenario("PV2", "Proveedores", "Primario devuelve respuesta vacía: responde el respaldo", gemini="")
def _(c, p):
    j = generar(c, datos()).json()
    return j["estado"] == "respuesta_generada" and p.llamadas["groq"] == 1, f"llamadas {p.llamadas}"


@escenario("PV3", "Proveedores", "Ambos caídos: se conserva la propuesta determinista y el caso", gemini=FALLA, groq=FALLA)
def _(c, p):
    r = generar(c, datos())
    j = r.json()
    ok = r.status_code == 200 and j["estado"] == "propuesta_sin_explicacion" and all(x in comandos(j) for x in COMANDOS_ESPERADOS) and bool(j["caso_id"])
    return ok, f"estado {j['estado']}; caso guardado {bool(j['caso_id'])}"


@escenario("PV4", "Proveedores", "Solo el respaldo y captura: aviso de que no se analizó la imagen", gemini=FALLA)
def _(c, p):
    r = c.post("/chat", json={"messages": [{"role": "user", "content": "¿Qué ves en esta topología?"}], "imagen": png()})
    return r.json()["reply"].startswith("No pude analizar la imagen") and p.llamadas["groq"] == 1, f"llamadas {p.llamadas}"


@escenario("PV5", "Proveedores", "Chat con ambos proveedores caídos: aviso fijo", gemini=FALLA, groq=FALLA)
def _(c, p):
    r = c.post("/chat", json={"messages": [{"role": "user", "content": "¿Cómo activo una interfaz?"}]})
    return r.json()["reply"] == llm.MENSAJE_FALLBACK, "mensaje de contingencia"


# ---------------------------------------------------------------- Conocimiento
@escenario("CN1", "Conocimiento", "Fuente válida: las fuentes citadas existen en el corpus")
def _(c, p):
    fuentes = generar(c, datos()).json()["propuesta"]["fuentes"]
    return bool(fuentes) and all((RAIZ / "docs" / f).exists() for f in fuentes), f"fuentes {fuentes}"


@escenario("CN2", "Conocimiento", "Búsqueda del índice falla: la propuesta sigue, sin fuentes", rag="falla")
def _(c, p):
    r = generar(c, datos())
    return r.status_code == 200 and r.json()["propuesta"]["fuentes"] == [], f"HTTP {r.status_code}"


@escenario("CN3", "Conocimiento", "Índice no disponible: 503 y no se llama a la IA", rag="indice_caido")
def _(c, p):
    r = generar(c, datos())
    return r.status_code == 503 and sum(p.llamadas.values()) == 0, f"HTTP {r.status_code}"


@escenario("CN4", "Conocimiento", "Diagnóstico disponible aunque el índice falle", rag="falla")
def _(c, p):
    cid = caso_nuevo(c)
    r = c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_OK}, headers={"X-Usuario": ANA})
    return r.status_code == 200, f"HTTP {r.status_code}"


# ---------------------------------------------------------------- Seguridad
@escenario("SG1", "Seguridad", "Datos sensibles en el chat: bloqueo antes del proveedor")
def _(c, p):
    r = c.post("/chat", json={"messages": [{"role": "user", "content": "Mi router es 192.168.1.1 y la contraseña es cisco123"}]})
    return r.json()["reply"] == MENSAJE_DATOS_SENSIBLES and sum(p.llamadas.values()) == 0, f"llamadas IA {sum(p.llamadas.values())}"


@escenario("SG2", "Seguridad", "Datos sensibles en el formulario: no se guarda ni se envía")
def _(c, p):
    r = generar(c, datos(objetivo="Contraseña enable secret cisco123 en el switch"))
    ok = r.status_code in (400, 422) and sum(p.llamadas.values()) == 0 and c.get("/casos", headers={"X-Usuario": ANA}).json() == []
    return ok, f"HTTP {r.status_code}"


@escenario("SG3", "Seguridad", "Otro usuario no accede al caso (404) ni lo ve listado")
def _(c, p):
    cid, h = caso_nuevo(c), {"X-Usuario": LUIS}
    codigos = [c.get(f"/casos/{cid}", headers=h).status_code, c.get(f"/casos/{cid}/informe", headers=h).status_code,
               c.post(f"/casos/{cid}/evidencias", json={"salida": VLAN_OK}, headers=h).status_code]
    return codigos == [404, 404, 404] and c.get("/casos", headers=h).json() == [], f"códigos {codigos}"


def ejecutar() -> list[dict]:
    logging.disable(logging.CRITICAL)
    resultados = []
    for id_, area, nombre, f in ESCENARIOS:
        with entorno(**CONFIG.get(id_, {})) as (cliente, prov):
            inicio = time.perf_counter()
            try:
                ok, detalle = f(cliente, prov)
            except Exception as error:  # un escenario roto cuenta como fallo, no detiene la evaluación
                ok, detalle = False, f"Excepción {type(error).__name__}: {error}"
            ms = (time.perf_counter() - inicio) * 1000
        resultados.append({"id": id_, "area": area, "nombre": nombre, "ok": bool(ok), "detalle": detalle, "ms": round(ms, 1)})
    return resultados


def metricas(resultados: list[dict]) -> dict:
    ms = sorted(r["ms"] for r in resultados)
    areas: dict[str, list[bool]] = {}
    for r in resultados:
        areas.setdefault(r["area"], []).append(r["ok"])
    return {
        "escenarios": len(resultados), "superados": sum(r["ok"] for r in resultados),
        "por_area": {a: f"{sum(v)}/{len(v)}" for a, v in areas.items()},
        "latencia_ms": {"mediana": round(statistics.median(ms), 1), "p95": ms[max(0, int(len(ms) * 0.95) - 1)], "maxima": ms[-1]},
    }


def informe(resultados: list[dict]) -> str:
    m = metricas(resultados)
    filas = "\n".join(f"| {r['id']} | {r['area']} | {r['nombre']} | {'✅' if r['ok'] else '❌'} | {r['detalle']} | {r['ms']:.0f} |" for r in resultados)
    lat = m["latencia_ms"]
    return ("# Resultado de la evaluación de la fase 6\n\nEjecución reproducible con dobles de proveedor e índice (sin red).\n\n"
            f"**Escenarios superados: {m['superados']}/{m['escenarios']}** · latencia local mediana {lat['mediana']} ms, p95 {lat['p95']} ms, máxima {lat['maxima']} ms (sin red ni modelo).\n\n"
            "| Área | Superados |\n|---|---|\n" + "\n".join(f"| {a} | {v} |" for a, v in m["por_area"].items()) +
            "\n\n| # | Área | Escenario | Resultado | Detalle | ms |\n|---|---|---|---|---|---|\n" + filas + "\n")


if __name__ == "__main__":
    res = ejecutar()
    texto = informe(res)
    (RAIZ / "pruebas" / "resultado_fase6.md").write_text(texto, encoding="utf-8")
    (RAIZ / "pruebas" / "resultado_fase6.json").write_text(json.dumps({"metricas": metricas(res), "escenarios": res}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(texto)
    sys.exit(0 if all(r["ok"] for r in res) else 1)

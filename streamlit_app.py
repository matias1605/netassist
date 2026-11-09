"""Interfaz de NetAssist en Streamlit.

Ejecutar en local:  streamlit run streamlit_app.py
En Streamlit Community Cloud las claves se cargan desde los Secrets de la app.
"""

import asyncio
import base64
import json
import os
import re

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="NetAssist", page_icon="🛠️", layout="centered")


def _cargar_secrets() -> None:
    """Copia los Secrets de Streamlit al entorno antes de leer la configuración del backend."""
    try:
        secretos = dict(st.secrets)
    except Exception:
        return  # Sin secrets.toml: se usa el archivo .env local.
    for clave, valor in secretos.items():
        if isinstance(valor, (str, int, float)):
            os.environ.setdefault(clave, str(valor))


_cargar_secrets()

from backend.cadena import crear_cadena  # noqa: E402  (después de cargar los secrets)
from backend.config import SUPPORT_CONTACT  # noqa: E402
from backend.rag import RagService  # noqa: E402
from backend.seguridad import MENSAJE_DATOS_SENSIBLES, validar_imagen  # noqa: E402

BIENVENIDA = (
    "¡Hola! Soy NetAssist. Cuéntame qué problema tienes y, si puedes, incluye el modelo "
    "del equipo Cisco, la versión de IOS y el error exacto."
)
TIPOS_IMAGEN = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
PATRON_MERMAID = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


@st.cache_resource(show_spinner="Cargando las fichas de Cisco IOS…")
def cargar_asistente():
    """Indexa las fichas una sola vez por servidor y arma la cadena de LangChain."""
    rag = RagService()
    resumen = rag.initialize()
    return crear_cadena(rag), resumen


def _altura_diagrama(fuente: str) -> int:
    """Calcula una altura aproximada: los diagramas horizontales ocupan poco alto."""
    lineas = [linea for linea in fuente.splitlines()[1:] if linea.strip()]
    if fuente.lstrip().lower().startswith(("graph lr", "graph rl", "flowchart lr", "flowchart rl")):
        return min(140 + 22 * max(0, len(lineas) - 4), 420)
    return min(120 + 70 * len(lineas), 640)


def dibujar_mermaid(fuente: str) -> None:
    """Dibuja un diagrama mermaid con la librería oficial desde CDN."""
    components.html(
        f"""
        <div id="diagrama" style="display:flex;justify-content:center"></div>
        <p style="text-align:center;font:12px sans-serif;color:#666">Topología generada por NetAssist</p>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>
        <script>
          mermaid.initialize({{ startOnLoad: false, securityLevel: "strict", theme: "neutral" }});
          mermaid.render("topologia", {json.dumps(fuente)})
            .then(({{ svg }}) => {{ document.getElementById("diagrama").innerHTML = svg; }})
            .catch(() => {{ document.getElementById("diagrama").textContent = {json.dumps(fuente)}; }});
        </script>
        """,
        height=_altura_diagrama(fuente),
        scrolling=True,
    )


def mostrar_respuesta(texto: str) -> None:
    """Muestra el texto y reemplaza los bloques mermaid por el diagrama dibujado."""
    posicion = 0
    for coincidencia in PATRON_MERMAID.finditer(texto):
        anterior = texto[posicion : coincidencia.start()].strip()
        if anterior:
            st.markdown(anterior)
        dibujar_mermaid(coincidencia.group(1).strip())
        posicion = coincidencia.end()
    resto = texto[posicion:].strip()
    if resto:
        st.markdown(resto)


def nueva_conversacion() -> None:
    st.session_state.mensajes = []


if "mensajes" not in st.session_state:
    nueva_conversacion()

# --- Barra lateral -----------------------------------------------------------------------
with st.sidebar:
    st.title("🛠️ NetAssist")
    st.caption("Asistente de soporte de redes Cisco IOS · Redes y Conectividad I · USMP · Equipo 04")
    st.button("Nueva conversación", on_click=nueva_conversacion, use_container_width=True)
    st.divider()
    st.markdown(
        "**Cómo usarlo**\n"
        "- Describe el síntoma: *«la PC1 no hace ping a la PC2»*.\n"
        "- Puedes adjuntar una captura de Packet Tracer (PNG, JPG o WEBP, máx. 4 MB).\n"
        "- No escribas IP reales ni contraseñas: se bloquean por seguridad."
    )
    st.divider()
    st.markdown(f"**Soporte humano:** {SUPPORT_CONTACT}")

try:
    cadena, resumen = cargar_asistente()
except Exception:
    st.error(f"No se pudo cargar la base de conocimiento. {SUPPORT_CONTACT}")
    st.stop()

with st.sidebar:
    st.caption(f"Base de conocimiento: {resumen['fragmentos']} fichas indexadas en ChromaDB.")

# --- Historial ---------------------------------------------------------------------------
with st.chat_message("assistant"):
    st.markdown(BIENVENIDA)

for mensaje in st.session_state.mensajes:
    with st.chat_message(mensaje["role"]):
        if mensaje.get("imagen"):
            st.image(mensaje["imagen"], width=320)
        if mensaje["role"] == "assistant":
            mostrar_respuesta(mensaje["content"])
        else:
            st.markdown(mensaje["content"])

# --- Nuevo mensaje -----------------------------------------------------------------------
entrada = st.chat_input(
    "Describe tu problema de red…",
    accept_file=True,
    file_type=list(TIPOS_IMAGEN),
)

if entrada:
    texto = (entrada.text or "").strip() or "¿Qué ves en esta imagen?"
    archivo = entrada.files[0] if entrada.files else None
    imagen = None
    imagen_bytes = None

    if archivo is not None:
        imagen_bytes = archivo.getvalue()
        mime = TIPOS_IMAGEN.get(archivo.name.rsplit(".", 1)[-1].lower(), "")
        datos = base64.b64encode(imagen_bytes).decode("ascii")
        try:
            validar_imagen(mime, datos)
        except ValueError as error:
            st.error(str(error))
            st.stop()
        imagen = {"mime": mime, "data": datos}

    with st.chat_message("user"):
        if imagen_bytes:
            st.image(imagen_bytes, width=320)
        st.markdown(texto)

    # Solo viajan al modelo los mensajes que no fueron bloqueados.
    historial = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.mensajes
        if not m.get("bloqueado")
    ]
    historial.append({"role": "user", "content": texto})

    with st.chat_message("assistant"):
        with st.spinner("Consultando las fichas de Cisco IOS…"):
            respuesta = asyncio.run(cadena.ainvoke({"mensajes": historial, "imagen": imagen}))
        mostrar_respuesta(respuesta)

    bloqueado = respuesta == MENSAJE_DATOS_SENSIBLES
    st.session_state.mensajes.append(
        {"role": "user", "content": texto, "imagen": imagen_bytes, "bloqueado": bloqueado}
    )
    st.session_state.mensajes.append(
        {"role": "assistant", "content": respuesta, "bloqueado": bloqueado}
    )

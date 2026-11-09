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

st.set_page_config(page_title="NetAssist", page_icon="🛠️", layout="wide", initial_sidebar_state="collapsed")


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
AVATAR_BOT = "🛠️"
AVATAR_USUARIO = "🧑‍💻"
AVATARES = {"assistant": AVATAR_BOT, "user": AVATAR_USUARIO}
PATRON_MERMAID = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


@st.cache_resource(show_spinner="Cargando las fichas de Cisco IOS…")
def cargar_asistente():
    """Indexa las fichas una sola vez por servidor y arma la cadena de LangChain."""
    rag = RagService()
    resumen = rag.initialize()
    return crear_cadena(rag), resumen


def _altura_diagrama(fuente: str) -> int:
    """Calcula la altura del diagrama vertical: unos 90 px por cada nivel de equipos."""
    enlaces = sum(1 for linea in fuente.splitlines() if "--" in linea)
    return min(50 + 90 * (enlaces + 1), 900)


def dibujar_mermaid(fuente: str) -> None:
    """Dibuja un diagrama mermaid con la librería oficial desde CDN."""
    # La ventana de la burbuja es angosta: los diagramas horizontales se dibujan en vertical.
    fuente = re.sub(r"^\s*(graph|flowchart)\s+(LR|RL)\b", r"\1 TD", fuente, flags=re.IGNORECASE)
    components.html(
        f"""
        <style>
          html, body {{ margin: 0; padding: 0; background: transparent; }}
          #diagrama {{ display: flex; justify-content: center; }}
          #diagrama svg {{ display: block; height: auto; margin: 0 auto; }}
          p {{ text-align: center; font: 12px sans-serif; color: #5b6b7f; margin: 6px 0 0; }}
        </style>
        <div id="diagrama"></div>
        <p>Topología generada por NetAssist</p>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>
        <script>
          mermaid.initialize({{ startOnLoad: false, securityLevel: "strict", theme: "neutral" }});
          mermaid.render("topologia", {json.dumps(fuente)})
            .then(({{ svg }}) => {{ document.getElementById("diagrama").innerHTML = svg; }})
            .catch(() => {{ document.getElementById("diagrama").textContent = {json.dumps(fuente)}; }});
        </script>
        """,
        height=_altura_diagrama(fuente),
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


def marcar_mensaje_usuario() -> None:
    """Marca oculta para que el CSS distinga los mensajes del usuario (los emoji no traen una)."""
    st.html('<span class="msg-usuario"></span>')


def nueva_conversacion() -> None:
    st.session_state.mensajes = []


def alternar_chat() -> None:
    st.session_state.chat_abierto = not st.session_state.chat_abierto


if "mensajes" not in st.session_state:
    nueva_conversacion()
if "chat_abierto" not in st.session_state:
    st.session_state.chat_abierto = False

# --- Estilos de la burbuja ---------------------------------------------------------------
# Los contenedores con key reciben la clase .st-key-<key>; con ella se fijan abajo a la derecha.
st.html(
    """
    <style>
      [data-testid="stSidebarCollapsedControl"], [data-testid="stSidebar"] { display: none; }
      .st-key-boton-burbuja {
        position: fixed; right: 24px; bottom: 24px; z-index: 1001; width: auto !important;
      }
      .st-key-boton-burbuja button {
        width: 64px; height: 64px; border-radius: 50%; border: none;
        background: #1F4E79; color: #fff; font-size: 28px;
        box-shadow: 0 6px 18px rgba(0, 0, 0, .28);
      }
      .st-key-boton-burbuja button:hover { background: #163A5C; color: #fff; }
      .st-key-boton-burbuja button:focus:not(:active) { color: #fff; border: none; }
      .st-key-ventana-chat {
        position: fixed; right: 24px; bottom: 100px; z-index: 1000;
        width: min(420px, calc(100vw - 32px)) !important;
        max-height: calc(100vh - 124px); overflow: hidden;
        background: #fff; border-radius: 18px; padding: 0; gap: 0;
        box-shadow: 0 14px 40px rgba(16, 42, 67, .28);
        border: 1px solid #e3e8ef;
      }
      .st-key-cabecera-chat {
        background: linear-gradient(135deg, #1F4E79, #2E6DA4);
        padding: 14px 16px; border-radius: 18px 18px 0 0;
      }
      .st-key-cabecera-chat p { color: #fff; margin: 0; line-height: 1.3; }
      .st-key-cabecera-chat small, .st-key-cabecera-chat em { color: #d6e4f2; font-style: normal; }
      .st-key-cabecera-chat button {
        background: rgba(255, 255, 255, .12); color: #fff;
        border: 1px solid rgba(255, 255, 255, .55); border-radius: 999px;
        padding: 2px 12px; min-height: 0; font-size: 13px;
      }
      .st-key-cabecera-chat button:hover { background: rgba(255, 255, 255, .25); color: #fff; border-color: #fff; }
      .st-key-cuerpo-chat { background: #f5f7fa; padding: 12px 12px 4px; }
      .st-key-cuerpo-chat [data-testid="stChatMessage"] {
        padding: 10px 12px; margin-bottom: 4px; border-radius: 14px;
        background: #fff; border: 1px solid #e3e8ef; gap: 8px;
      }
      .st-key-cuerpo-chat [data-testid="stChatMessage"]:has(.msg-usuario) {
        flex-direction: row-reverse; background: #e3eefa; border-color: #c9dcf0; margin-left: 28px;
      }
      .st-key-cuerpo-chat [data-testid="stChatMessage"]:not(:has(.msg-usuario)) { margin-right: 12px; }
      .st-key-cuerpo-chat .stElementContainer:has(.msg-usuario) { display: none; }
      .st-key-cuerpo-chat [data-testid="stChatMessageContent"] { min-width: 0; }
      .st-key-cuerpo-chat [data-testid="stChatMessageContent"] p { font-size: 14.5px; line-height: 1.5; }
      .st-key-cuerpo-chat [data-testid="stImage"], .st-key-cuerpo-chat [data-testid="stImageContainer"] {
        margin-left: auto; margin-right: auto;
      }
      .st-key-cuerpo-chat img { border-radius: 10px; }
      .st-key-cuerpo-chat iframe { display: block; margin: 0 auto; }
      .st-key-pie-chat { padding: 10px 12px 12px; border-top: 1px solid #e3e8ef; background: #fff; }
      .st-key-pie-chat [data-testid="stChatInput"] > div { border-radius: 14px; }
      .portal-hero {
        position: relative; overflow: hidden; margin: 18px 0 30px; padding: 38px 42px;
        border: 1px solid #d6e0e8; border-radius: 24px;
        background:
          linear-gradient(120deg, rgba(10, 31, 51, .97), rgba(20, 67, 87, .94)),
          repeating-linear-gradient(0deg, transparent 0 27px, rgba(255,255,255,.04) 28px),
          repeating-linear-gradient(90deg, transparent 0 27px, rgba(255,255,255,.04) 28px);
        box-shadow: 0 18px 42px rgba(16, 42, 67, .16);
      }
      .portal-hero::after {
        content: ""; position: absolute; width: 220px; height: 220px; right: -72px; top: -90px;
        border: 1px solid rgba(255, 183, 77, .35); border-radius: 50%;
        box-shadow: 0 0 0 18px rgba(255, 183, 77, .06), 0 0 0 36px rgba(255, 183, 77, .04);
      }
      .portal-kicker {
        position: relative; z-index: 1; margin: 0 0 12px; color: #ffbd5a;
        font: 700 12px/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
        letter-spacing: .14em; text-transform: uppercase;
      }
      .portal-hero h1 {
        position: relative; z-index: 1; max-width: 700px; margin: 0; color: #fff;
        font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.2rem, 5vw, 4.2rem);
        line-height: .98; letter-spacing: -.045em;
      }
      .portal-hero p { position: relative; z-index: 1; max-width: 680px; color: #c9dce6; font-size: 1.05rem; line-height: 1.6; margin: 18px 0 0; }
      .portal-section-label {
        margin: 0 0 14px; color: #12324b; font: 700 12px/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
        letter-spacing: .12em; text-transform: uppercase;
      }
      .practice-card {
        min-height: 154px; padding: 22px 20px; border: 1px solid #d6e0e8; border-radius: 16px;
        background: #fff; box-shadow: 0 8px 20px rgba(16, 42, 67, .06);
        transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
      }
      .practice-card:hover { transform: translateY(-4px); border-color: #efad45; box-shadow: 0 14px 28px rgba(16, 42, 67, .12); }
      .practice-number { color: #ef9f2d; font: 700 12px ui-monospace, SFMono-Regular, Consolas, monospace; }
      .practice-card h3 { margin: 18px 0 9px; color: #12324b; font-size: 1.12rem; }
      .practice-card p { margin: 0; color: #607487; font-size: .92rem; line-height: 1.5; }
      .help-panel {
        margin-top: 30px; padding: 24px 26px; border-left: 4px solid #ef9f2d;
        border-radius: 0 16px 16px 0; background: #fffaf1; box-shadow: 0 8px 20px rgba(90, 62, 17, .06);
      }
      .help-panel h2 { margin: 0 0 14px; color: #12324b; font-size: 1.35rem; }
      .help-panel ul { margin: 0; padding-left: 22px; color: #526779; line-height: 1.8; }
      .knowledge-note { margin-top: 18px; color: #718493; font-size: .8rem; }
      @media (max-width: 640px) {
        .portal-hero { padding: 28px 24px; border-radius: 18px; }
        .portal-hero h1 { font-size: 2.45rem; }
        .practice-card { min-height: auto; margin-bottom: 12px; }
      }
      @media (max-width: 640px) {
        .st-key-ventana-chat { right: 16px; bottom: 96px; }
        .st-key-boton-burbuja { right: 16px; bottom: 16px; }
      }
    </style>
    """
)

try:
    cadena, resumen = cargar_asistente()
except Exception:
    st.error(f"No se pudo cargar la base de conocimiento. {SUPPORT_CONTACT}")
    st.stop()

# --- Página de fondo: portal del laboratorio ---------------------------------------------
st.markdown(
    """
    <section class="portal-hero">
      <div class="portal-kicker">USMP · Equipo 04 · Cisco IOS</div>
      <h1>Laboratorio de Redes y Conectividad I</h1>
      <p>Practica, prueba y diagnostica redes con una guía clara. Cuando algo no responda, NetAssist te ayuda a encontrar el siguiente paso.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="portal-section-label">Rutas de aprendizaje</p>', unsafe_allow_html=True)
practicas = [
    ("01", "Conectividad e interfaces", "Direccionamiento IP, interfaces caídas y pruebas con ping."),
    ("02", "Rutas estáticas y DNS", "Comunicación entre redes remotas y resolución de nombres."),
    ("03", "VLAN y SVI", "Segmentación del switch y acceso remoto de administración."),
]
for columna, (numero, titulo, descripcion) in zip(st.columns(3), practicas):
    with columna:
        st.markdown(
            f'<article class="practice-card"><div class="practice-number">{numero}</div>'
            f"<h3>{titulo}</h3><p>{descripcion}</p></article>",
            unsafe_allow_html=True,
        )

st.markdown(
    f"""
    <section class="help-panel">
      <h2>Antes de pedir ayuda</h2>
      <ul>
        <li>Describe el síntoma: <em>«la PC1 no hace ping a la PC2»</em> o <em>«la interfaz aparece down»</em>.</li>
        <li>Adjunta una captura de Packet Tracer (PNG, JPG o WEBP, máximo 4 MB).</li>
        <li><strong>No escribas IP reales ni contraseñas:</strong> el asistente las bloquea por seguridad.</li>
        <li>Si el problema persiste, contacta al soporte humano: {SUPPORT_CONTACT}</li>
      </ul>
    </section>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="knowledge-note">● Base de conocimiento activa · {resumen["fragmentos"]} fichas de Cisco IOS en ChromaDB</p>',
    unsafe_allow_html=True,
)

# --- Botón flotante ----------------------------------------------------------------------
with st.container(key="boton-burbuja"):
    st.button(
        "✕" if st.session_state.chat_abierto else "💬",
        on_click=alternar_chat,
        help="Cerrar NetAssist" if st.session_state.chat_abierto else "Abrir NetAssist",
    )

# --- Ventana del chat --------------------------------------------------------------------
if st.session_state.chat_abierto:
    with st.container(key="ventana-chat"):
        with st.container(
            key="cabecera-chat",
            horizontal=True,
            vertical_alignment="center",
            horizontal_alignment="distribute",
        ):
            st.markdown("**🛠️ NetAssist**  \n<small>Soporte de redes Cisco IOS</small>", unsafe_allow_html=True)
            st.button("Nuevo chat", on_click=nueva_conversacion, help="Borra la conversación")

        conversacion = st.container(height=420, border=False, key="cuerpo-chat")
        with conversacion:
            with st.chat_message("assistant", avatar=AVATAR_BOT):
                st.markdown(BIENVENIDA)
            for mensaje in st.session_state.mensajes:
                with st.chat_message(mensaje["role"], avatar=AVATARES[mensaje["role"]]):
                    if mensaje["role"] == "user":
                        marcar_mensaje_usuario()
                    if mensaje.get("imagen"):
                        st.image(mensaje["imagen"], width="stretch")
                    if mensaje["role"] == "assistant":
                        mostrar_respuesta(mensaje["content"])
                    else:
                        st.markdown(mensaje["content"])

        with st.container(key="pie-chat"):
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

            # Solo viajan al modelo los mensajes que no fueron bloqueados.
            historial = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.mensajes
                if not m.get("bloqueado")
            ]
            historial.append({"role": "user", "content": texto})

            with conversacion:
                with st.chat_message("user", avatar=AVATAR_USUARIO):
                    marcar_mensaje_usuario()
                    if imagen_bytes:
                        st.image(imagen_bytes, width="stretch")
                    st.markdown(texto)
                with st.chat_message("assistant", avatar=AVATAR_BOT):
                    with st.spinner("Consultando las fichas de Cisco IOS…"):
                        respuesta = asyncio.run(
                            cadena.ainvoke({"mensajes": historial, "imagen": imagen})
                        )
                    mostrar_respuesta(respuesta)

            bloqueado = respuesta == MENSAJE_DATOS_SENSIBLES
            st.session_state.mensajes.append(
                {"role": "user", "content": texto, "imagen": imagen_bytes, "bloqueado": bloqueado}
            )
            st.session_state.mensajes.append(
                {"role": "assistant", "content": respuesta, "bloqueado": bloqueado}
            )

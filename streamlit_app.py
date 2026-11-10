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

st.set_page_config(page_title="NetAssist", page_icon="🛠️", layout="wide", initial_sidebar_state="expanded")


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

from backend.casos import AlmacenCasos  # noqa: E402
from backend.config import CASOS_DB_PATH  # noqa: E402
from backend.cadena import crear_cadena, crear_cadena_detallada  # noqa: E402  (después de cargar los secrets)
from backend.acciones import obtener_acciones  # noqa: E402
from laboratorio_ui import mostrar_laboratorio
from backend.config import SUPPORT_CONTACT  # noqa: E402
from backend.rag import RagService  # noqa: E402
from backend.llm import MENSAJE_FALLBACK  # noqa: E402
from backend.seguridad import MENSAJE_DATOS_SENSIBLES, ocultar_datos_sensibles, validar_imagen  # noqa: E402
from topologia_ui import leyenda, preparar_topologia  # noqa: E402
from estilos_streamlit import NEXO_URI, cabecera_chat, estilos, fichas_consultadas, marca_estado, panel_izquierdo  # noqa: E402

BIENVENIDA = (
    "¡Hola! Soy NetAssist. Cuéntame qué problema tienes y, si puedes, incluye el modelo "
    "del equipo Cisco, la versión de IOS y el error exacto."
)
TIPOS_IMAGEN = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
AVATAR_BOT = NEXO_URI
AVATAR_USUARIO = "🧑‍💻"
AVATARES = {"assistant": AVATAR_BOT, "user": AVATAR_USUARIO}
PATRON_MERMAID = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


@st.cache_resource(show_spinner="Cargando las fichas de Cisco IOS…")
def cargar_asistente():
    """Indexa las fichas una sola vez por servidor y arma la cadena de LangChain."""
    rag = RagService()
    resumen = rag.initialize()
    return crear_cadena(rag), crear_cadena_detallada(rag), resumen, rag


@st.cache_resource
def cargar_almacen():
    return AlmacenCasos(CASOS_DB_PATH)


def _js(texto: str) -> str:
    """Cadena JSON segura dentro de <script> (escapar < impide cerrar la etiqueta)."""
    return json.dumps(texto).replace("<", chr(92) + "u003c")


def dibujar_mermaid(fuente: str) -> None:
    """Dibuja la topología con Mermaid: colores e iconos por tipo de equipo y leyenda.

    El modelo decide qué se dibuja; topologia_ui solo le da estilo. Si el diagrama con estilo
    falla, se dibuja el original, y si también falla, se muestra el código tal cual.
    """
    original = re.sub(r"^\s*(graph|flowchart)\s+(LR|RL)\b", r"\1 TD", fuente.strip(), flags=re.IGNORECASE)
    try:
        con_estilo, altura, presentes = preparar_topologia(fuente)
    except Exception:
        con_estilo, altura, presentes = original, 340, []
    components.html(
        f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
        <style>
          html, body {{ margin: 0; padding: 0; background: transparent; font-family: "Source Sans Pro", sans-serif; }}
          .marco {{ border: 1px solid #e2eaf1; border-radius: 14px; padding: 14px 10px 10px;
                    background: radial-gradient(rgb(20 149 138 / 10%) 1px, transparent 1px) 0 0 / 16px 16px, #fbfdfe; }}
          #diagrama {{ display: flex; justify-content: center; }}
          #diagrama svg {{ display: block; height: auto; margin: 0 auto; }}
          #diagrama .node rect {{ rx: 10px; ry: 10px; filter: drop-shadow(0 3px 6px rgb(15 26 43 / 14%)); }}
          /* Sin cambiar tamaño ni grosor del texto aquí: Mermaid mide las cajas con su propia fuente. */
          #diagrama .edgeLabel, #diagrama .edgeLabel p {{ color: #0f6f68; background: #e6f6f4 !important; border-radius: 6px; }}
          .pie {{ display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 6px; margin-top: 10px;
                  font-size: 11.5px; color: #5b6b7f; }}
          .ley {{ display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: 999px;
                  border: 1px solid #d9e1eb; background: #fff; color: #1d2b3b; font-weight: 600; }}
          .ley-router i {{ color: #0f1a2b; }} .ley-switch i {{ color: #14958a; }} .ley-servidor i {{ color: #2a7fd6; }}
          .ley-pc i {{ color: #6b7c8f; }} .ley-nube i {{ color: #9fb3c8; }}
          .falla {{ color: #e5484d; font-weight: 600; }}
        </style>
        <div class="marco">
          <div id="diagrama"></div>
          <div class="pie">{leyenda(presentes)}<span>Topología generada por NetAssist</span></div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>
        <script>
          mermaid.initialize({{
            startOnLoad: false, securityLevel: "strict", theme: "base",
            flowchart: {{ curve: "linear", nodeSpacing: 40, rankSpacing: 60, padding: 12 }},
            themeVariables: {{
              fontFamily: "Source Sans Pro, sans-serif", fontSize: "13px",
              primaryColor: "#ffffff", primaryBorderColor: "#9fb3c8", primaryTextColor: "#1d2b3b",
              lineColor: "#14958a", edgeLabelBackground: "#e6f6f4"
            }}
          }});
          const destino = document.getElementById("diagrama");
          // Mermaid mide cada caja al dibujar: hay que esperar a la fuente de los iconos o el texto se corta.
          const fuentes = Promise.race([
            Promise.all([
              document.fonts.load('900 13px "Font Awesome 6 Free"'),
              document.fonts.load('13px "Source Sans Pro"'),
            ]),
            new Promise((listo) => setTimeout(listo, 1500)),
          ]).catch(() => null);
          fuentes
            .then(() => mermaid.render("topologia", {_js(con_estilo)}))
            .catch(() => mermaid.render("topologia2", {_js(original)}))
            .then(({{ svg }}) => {{ destino.innerHTML = svg; }})
            .catch(() => {{ destino.textContent = {_js(original)}; }});
        </script>
        """,
        height=altura,
    )


def estado_de_respuesta(detalle: dict) -> str:
    """Verde si se apoyó en las fichas; rojo si se bloqueó, falló o no coincide con ninguna ficha."""
    return "duda" if detalle["bloqueado"] or detalle["fragmentos"] == 0 else "ok"


def lleva_fichas(detalle: dict) -> bool:
    """Las fichas consultadas se muestran solo en respuestas reales (no en bloqueos ni fallos)."""
    return (not detalle["bloqueado"] and not detalle.get("fuera_de_tema")
            and detalle["respuesta"] != MENSAJE_FALLBACK)


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
    st.session_state.borrador_accion = ""
    st.session_state.estado_chat = "listo"


def alternar_chat() -> None:
    st.session_state.chat_abierto = not st.session_state.chat_abierto


TEMAS = [
    ("Generar la configuración", lambda n: f"Genera la configuración Cisco IOS de mi práctica «{n}»."),
    ("Explicar cada comando", lambda n: "Explícame qué hace cada comando de la configuración de mi práctica."),
    ("Comandos para comprobarlo", lambda n: "Dame los comandos para comprobar mi práctica en el simulador y qué debería ver en cada uno."),
    ("Dibujar la topología", lambda n: "Genera la topología de mi práctica."),
    ("Errores comunes", lambda n: "¿Qué errores comunes debo evitar en esta práctica y cómo los reviso?"),
]


def enviar_tema(indice: int) -> None:
    """Envía directamente la sugerencia elegida, sin pasar por un borrador."""
    nombre = st.session_state.get("lab_nombre") or "mi práctica"
    st.session_state.solicitud_accion = TEMAS[indice][1](nombre)


def preparar_accion(prompt: str) -> None:
    """Carga un borrador editable sin enviar consultas al proveedor."""
    st.session_state.borrador_accion = prompt


def enviar_borrador() -> None:
    """Consume el borrador una sola vez, antes de volver a crear el editor."""
    st.session_state.solicitud_accion = st.session_state.get("borrador_accion", "").strip()
    st.session_state.borrador_accion = ""


if "mensajes" not in st.session_state:
    nueva_conversacion()
if "chat_abierto" not in st.session_state:
    st.session_state.chat_abierto = False

# --- Estilos: mismo diseño que la web (ver estilos_streamlit.py) -------------------------
st.html(estilos())

try:
    cadena, cadena_detallada, resumen, rag = cargar_asistente()
except Exception:
    st.error(f"No se pudo cargar la base de conocimiento. {SUPPORT_CONTACT}")
    st.stop()

with st.sidebar:
    st.html(panel_izquierdo(SUPPORT_CONTACT))

# --- Página de fondo: portal del laboratorio ---------------------------------------------
st.title("Laboratorio de Redes y Conectividad I")
st.caption("Portal de prácticas con equipos Cisco IOS · USMP · Equipo 04")
st.markdown(
    "Aquí encontrarás las prácticas del laboratorio. Si algo no funciona durante una práctica, "
    "pulsa la mascota **Nexo** de abajo a la derecha y pregúntale a **NetAssist**, el asistente "
    "de soporte del laboratorio."
)

mostrar_laboratorio(cadena, cargar_almacen())

st.divider()
st.subheader("Prácticas")
practicas = [
    ("🔌 Conectividad e interfaces", "Direccionamiento IP, interfaces caídas y pruebas con ping."),
    ("🧭 Rutas estáticas y DNS", "Comunicación entre redes remotas y resolución de nombres."),
    ("🔀 VLAN y SVI", "Segmentación del switch y acceso remoto de administración."),
]
for columna, (titulo, descripcion) in zip(st.columns(3), practicas):
    with columna.container(border=True):
        st.markdown(f"**{titulo}**")
        st.caption(descripcion)

st.subheader("Antes de pedir ayuda")
st.markdown(
    "- Describe el síntoma: *«la PC1 no hace ping a la PC2»*, *«la interfaz aparece down»*.\n"
    "- Puedes adjuntar una captura de Packet Tracer (PNG, JPG o WEBP, máx. 4 MB).\n"
    "- **Solo datos ficticios:** usa direcciones privadas o de documentación; elimina credenciales también de las capturas.\n"
    f"- Si el problema persiste, contacta a soporte: {SUPPORT_CONTACT}"
)

# --- Botón flotante ----------------------------------------------------------------------
with st.container(key="boton-burbuja-abierta" if st.session_state.chat_abierto else "boton-burbuja-cerrada"):
    st.button(
        "✕" if st.session_state.chat_abierto else "Abrir",
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
            st.html(cabecera_chat())
            st.button("Borrar chat", on_click=nueva_conversacion, help="Borra toda la conversación (no se guarda)")
            # Marca invisible: el CSS colorea la cabecera según el estado (listo, pensando, ok, duda).
            estado_slot = st.empty()
            estado_slot.html(marca_estado(st.session_state.get("estado_chat", "listo")))

        conversacion = st.container(height=420, border=False, key="cuerpo-chat")
        with conversacion:
            if not (st.session_state.mensajes and st.session_state.mensajes[0].get("saludo")):
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
                        if "fuentes" in mensaje:
                            st.html(fichas_consultadas(mensaje["fuentes"]))
                    else:
                        st.markdown(mensaje["content"])

        with st.container(key="pie-chat"):
            with st.container(key="sugerencias-chat"):
                st.html('<p class="nx-sug-intro">Dudas frecuentes</p>')
                with st.container(horizontal=True, gap="small", key="chips-sugerencias"):
                    for i, tema in enumerate(TEMAS):
                        st.button(tema[0], key=f"tema-{i}", on_click=enviar_tema, args=(i,), width="content")
            entrada = st.chat_input(
                "Describe tu problema de red…",
                accept_file=True,
                file_type=list(TIPOS_IMAGEN),
            )

        texto_accion = st.session_state.pop("solicitud_accion", "")
        if entrada or texto_accion:
            texto = ((entrada.text if entrada else texto_accion) or "").strip() or "¿Qué ves en esta imagen?"
            archivo = entrada.files[0] if entrada and entrada.files else None
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
                imagen = {"mime": mime, "data": datos, "laboratorio_confirmado": True}

            # Solo viajan al modelo los mensajes que no fueron bloqueados. En las respuestas del
            # asistente se ocultan las claves de ejemplo que copió de las fichas, para que no
            # bloqueen el resto de la conversación; los mensajes del usuario se revisan tal cual.
            historial = [
                {
                    "role": m["role"],
                    "content": ocultar_datos_sensibles(m["content"]) if m["role"] == "assistant" else m["content"],
                }
                for m in st.session_state.mensajes
                if not m.get("bloqueado") and not m.get("saludo")
            ]
            practica = st.session_state.get("practica")
            contexto = ("\n\nDatos de mi práctica (formulario del laboratorio, ficticios):\n"
                        + json.dumps(practica, ensure_ascii=False, indent=2)) if practica else ""
            historial.append({"role": "user", "content": texto + contexto})

            with conversacion:
                with st.chat_message("user", avatar=AVATAR_USUARIO):
                    marcar_mensaje_usuario()
                    if imagen_bytes:
                        st.image(imagen_bytes, width="stretch")
                    st.markdown(texto)
                with st.chat_message("assistant", avatar=AVATAR_BOT):
                    estado_slot.html(marca_estado("pensando"))
                    with st.spinner("Consultando las fichas de Cisco IOS…"):
                        try:
                            detalle = asyncio.run(
                                cadena_detallada.ainvoke({"mensajes": historial, "imagen": imagen})
                            )
                        except ValueError as error:
                            st.session_state.estado_chat = "duda"
                            estado_slot.html(marca_estado("duda"))
                            st.error(str(error))
                            st.stop()
                    respuesta = detalle["respuesta"]
                    st.session_state.estado_chat = estado_de_respuesta(detalle)
                    estado_slot.html(marca_estado(st.session_state.estado_chat))
                    mostrar_respuesta(respuesta)
                    if lleva_fichas(detalle):
                        st.html(fichas_consultadas(detalle["fuentes"]))

            bloqueado = detalle["bloqueado"] or respuesta == MENSAJE_DATOS_SENSIBLES
            st.session_state.mensajes.append(
                {"role": "user", "content": texto, "imagen": imagen_bytes, "bloqueado": bloqueado}
            )
            st.session_state.mensajes.append(
                {
                    "role": "assistant",
                    "content": respuesta,
                    "bloqueado": bloqueado,
                    **({"fuentes": detalle["fuentes"]} if lleva_fichas(detalle) else {}),
                }
            )

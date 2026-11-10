"""Formulario «Prepara tu práctica» en Streamlit: guarda los datos y abre el chat con Nexo."""
import asyncio
import json
import logging

import streamlit as st
from pydantic import ValidationError

from backend.casos import validar_usuario
from estilos_streamlit import ENCABEZADO_LAB, card_head, form_sec
from backend.laboratorio import TareaLaboratorio, ejemplo_laboratorio, guardar_practica
from backend.llm import MENSAJE_FALLBACK
from backend.seguridad import MENSAJE_DATOS_SENSIBLES
from backend.tema import MENSAJE_FUERA_DE_TEMA

logger = logging.getLogger(__name__)
CLAVE_LOCAL = "netassist-local-usuario"


def _cargar_datos(datos):
    for clave in ("tipo", "nombre", "objetivo"):
        st.session_state[f"lab_{clave}"] = datos[clave]
    for clave in ("alias", "modelo", "ios"):
        st.session_state[f"lab_{clave}"] = datos["equipo"][clave]
    st.session_state.lab_filas = datos["vlans"]
    st.session_state.lab_editor_version = st.session_state.get("lab_editor_version", 0) + 1


def _ejemplo(nombre, alias, modelo, ios, vlans, objetivo):
    return {"tipo": "configuracion", "nombre": nombre, "equipo": {"alias": alias, "modelo": modelo, "ios": ios},
            "vlans": [{"id": str(i), "nombre": n, "puerto": p, "host": h} for i, n, p, h in vlans], "objetivo": objetivo}


_SIN_IP = "puertos de acceso; sin comunicación entre VLAN, sin enlaces trunk y sin direccionamiento IP"
EJEMPLOS = [
    ("Administración y Laboratorio", "Dos grupos separados en un switch", ejemplo_laboratorio),
    ("Aulas de la universidad", "Tres aulas aisladas", lambda: _ejemplo(
        "Segmentación de aulas de la universidad", "SW-AULAS", "Cisco Catalyst 2960", "15.0",
        [(10, "AULA_A", "GigabitEthernet0/1", "PC_AULA_A"), (20, "AULA_B", "GigabitEthernet0/2", "PC_AULA_B"),
         (30, "DOCENTES", "GigabitEthernet0/3", "PC_DOCENTE")], "Separar aulas y docentes con " + _SIN_IP)),
    ("Oficina pequeña", "Ventas, Contabilidad y Gerencia", lambda: _ejemplo(
        "Segmentación de una oficina pequeña", "SW-OFICINA", "Cisco Catalyst 2960", "15.0",
        [(10, "VENTAS", "FastEthernet0/1", "PC_VENTAS"), (20, "CONTABILIDAD", "FastEthernet0/2", "PC_CONTA"),
         (30, "GERENCIA", "FastEthernet0/3", "PC_GERENTE")], "Separar los departamentos con " + _SIN_IP)),
    ("Biblioteca y Cómputo", "Invitados separados del personal", lambda: _ejemplo(
        "Segmentación de biblioteca y sala de cómputo", "SW-BIBLIO", "Cisco Catalyst 2960", "15.0",
        [(10, "BIBLIOTECA", "GigabitEthernet0/1", "PC_BIBLIO"), (20, "COMPUTO", "GigabitEthernet0/2", "PC_COMPUTO"),
         (30, "INVITADOS", "GigabitEthernet0/3", "PC_INVITADO"), (40, "PERSONAL", "GigabitEthernet0/4", "PC_PERSONAL")],
        "Separar invitados, personal y salas con " + _SIN_IP)),
]


def _cargar_ejemplo(indice=0):
    st.session_state.lab_caso_id = None
    _cargar_datos(EJEMPLOS[indice][2]())


def saludo_de_practica(datos):
    """Saludo de respaldo, sin IA: se usa solo si el modelo no responde."""
    equipo = datos["equipo"]
    lineas = "\n".join(f"- VLAN {v['id']} **{v['nombre']}**: {v['puerto']} → {v['host']}" for v in datos["vlans"])
    return (f"¡Hola! Ya tengo los datos de tu práctica **«{datos['nombre']}»** "
            f"({equipo['alias']} · {equipo['modelo']}):\n\n{lineas}\n\n"
            "¿Qué dudas tienes? Escríbelas abajo o elige una de las sugerencias.")


def saludo_con_ia(cadena, datos):
    """Nexo lee la práctica guardada y saluda con lo que entendió; si el modelo falla, usa el saludo fijo."""
    pedido = ("Acabo de guardar mi práctica en el formulario y quiero que me saludes. "
              "Resume lo que entendiste y pregúntame qué duda tengo.\n\n"
              "Datos de mi práctica (formulario del laboratorio, ficticios):\n" + json.dumps(datos, ensure_ascii=False, indent=2))
    try:
        respuesta = asyncio.run(cadena.ainvoke({"mensajes": [{"role": "user", "content": pedido}]}))
    except Exception:
        logger.warning("No se pudo generar el saludo con IA.")
        return saludo_de_practica(datos)
    if not respuesta or respuesta in {MENSAJE_FALLBACK, MENSAJE_DATOS_SENSIBLES, MENSAJE_FUERA_DE_TEMA}:
        return saludo_de_practica(datos)
    return respuesta


def mostrar_laboratorio(cadena, almacen=None):
    if "lab_filas" not in st.session_state:
        _cargar_ejemplo()
    # Una sola clave fija: las prácticas guardadas persisten entre sesiones (uso individual).
    st.session_state.lab_usuario = CLAVE_LOCAL
    st.html(ENCABEZADO_LAB)
    with st.expander("Probar con un ejemplo"):
        st.caption("Elige un ejemplo: rellenará «Prepara tu práctica» y podrás editarlo.")
        for fila in (EJEMPLOS[:2], EJEMPLOS[2:]):
            for col, (titulo, descripcion, obtener) in zip(st.columns(2), fila):
                indice = EJEMPLOS.index((titulo, descripcion, obtener))
                datos_ej = obtener()
                with col.container(border=True):
                    st.markdown(f"**{titulo}**")
                    st.caption(descripcion)
                    st.caption(" · ".join(f"VLAN {v['id']} {v['nombre']}" for v in datos_ej["vlans"]))
                    st.button("Usar este ejemplo", key=f"lab_ej_{indice}", on_click=_cargar_ejemplo, args=(indice,))
    try:
        validar_usuario(st.session_state.lab_usuario)
    except ValueError as error:
        st.error(str(error))
        return

    # --- 01 · Prepara tu práctica ---------------------------------------------------------
    with st.container(key="lab-form"):
        st.html(card_head("01", "Prepara tu práctica", "Define el equipo y los grupos de puertos."))
        st.text_input("Nombre de la práctica", max_chars=120, key="lab_nombre", placeholder="Separar Administración y Laboratorio")
        st.html(form_sec("El equipo", "Cisco IOS"))
        col_alias, col_modelo = st.columns(2)
        col_alias.text_input("Alias del switch", max_chars=64, key="lab_alias", placeholder="Ej. SW1")
        col_modelo.text_input("Modelo del switch", max_chars=120, key="lab_modelo", placeholder="Ej. Catalyst 2960")
        st.html(form_sec("Grupos de puertos", "VLAN de acceso"))
        filas = st.data_editor(
            st.session_state.lab_filas, num_rows="dynamic", hide_index=True,
            column_config={"id": st.column_config.TextColumn("VLAN"), "nombre": st.column_config.TextColumn("Nombre"), "puerto": st.column_config.TextColumn("Puerto de acceso"), "host": st.column_config.TextColumn("Equipo conectado")},
            key=f"lab_editor_{st.session_state.lab_editor_version}", width="stretch",
        )
        st.caption("Añade o elimina filas en la tabla; entre 1 y 16 conexiones.")
        with st.expander("Más detalles (tipo de tarea, versión de IOS y objetivo)"):
            st.selectbox("Tipo de tarea", ["configuracion", "topologia"], format_func=lambda x: "Generar configuración" if x == "configuracion" else "Generar topología", key="lab_tipo")
            st.text_input("Versión de IOS", max_chars=80, key="lab_ios")
            st.caption("Modelo e IOS son obligatorios para configuración. Si no los conoces, déjalos vacíos y revisa qué falta.")
            st.text_area("Objetivo y requisitos", max_chars=1500, key="lab_objetivo")
        datos = {"tipo": st.session_state.lab_tipo, "nombre": st.session_state.lab_nombre,
                 "equipo": {clave: st.session_state[f"lab_{clave}"] for clave in ("alias", "modelo", "ios")},
                 "vlans": [{k: str(v or "") for k, v in fila.items()} for fila in filas], "objetivo": st.session_state.lab_objetivo}
        if st.button("Guardar práctica y hablar con Nexo", key="lab_guardar", type="primary"):
            try:
                tarea = TareaLaboratorio(**datos)
                resultado = guardar_practica(tarea, almacen, st.session_state.get("lab_caso_id"), st.session_state.lab_usuario) if almacen else None
                if resultado:
                    st.session_state.lab_caso_id = resultado["caso_id"]
                st.session_state.practica = tarea.model_dump()
                with st.spinner("Nexo está leyendo tu práctica…"):
                    saludo = saludo_con_ia(cadena, st.session_state.practica)
                st.session_state.mensajes = [{
                    "role": "assistant", "content": saludo, "saludo": True,
                    "sugerencias": [("Generar la configuración", "Genera la configuración Cisco IOS de mi práctica."),
                                    ("Dibujar la topología", "Genera la topología de mi práctica.")],
                }]
                st.session_state.chat_abierto = True
            except ValidationError:
                st.error("Revisa la longitud de los campos y registra entre 1 y 16 conexiones.")
            except ValueError as error:
                st.error(str(error))

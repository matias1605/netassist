"""Formulario y resultados del laboratorio en Streamlit; reglas en backend.laboratorio."""
import asyncio
import json
import logging

import streamlit as st
from pydantic import ValidationError

from backend.laboratorio import TareaLaboratorio, ejemplo_laboratorio, preparar_tarea, generar_tarea

logger = logging.getLogger(__name__)


def _cargar_ejemplo():
    datos = ejemplo_laboratorio()
    for clave in ("tipo", "nombre", "objetivo"):
        st.session_state[f"lab_{clave}"] = datos[clave]
    for clave in ("alias", "modelo", "ios"):
        st.session_state[f"lab_{clave}"] = datos["equipo"][clave]
    st.session_state.lab_filas = datos["vlans"]
    st.session_state.lab_editor_version = st.session_state.get("lab_editor_version", 0) + 1
    _descartar()


def _descartar():
    st.session_state.lab_revision = None
    st.session_state.lab_resultado = None
    st.session_state.lab_confirmado = False


def mostrar_laboratorio(cadena, mostrar_respuesta):
    if "lab_filas" not in st.session_state:
        _cargar_ejemplo()
    st.subheader("Espacio de laboratorio")
    st.caption("VLAN y puertos de acceso · Solo datos ficticios · Un switch, sin IP, trunk ni enrutamiento entre VLAN")
    datos_col, salida_col = st.columns([1.15, 1], gap="large")
    with datos_col:
        st.markdown("### 1. Datos de la práctica")
        st.button("Cargar ejemplo de laboratorio", on_click=_cargar_ejemplo)
        st.selectbox("Tipo de tarea", ["configuracion", "topologia"], format_func=lambda x: "Generar configuración" if x == "configuracion" else "Generar topología", key="lab_tipo")
        st.text_input("Nombre de la práctica", max_chars=120, key="lab_nombre")
        st.text_input("Alias del switch", max_chars=64, key="lab_alias")
        st.text_input("Modelo", max_chars=120, key="lab_modelo")
        st.text_input("Versión de IOS", max_chars=80, key="lab_ios")
        st.caption("Modelo e IOS son obligatorios para configuración. Si no los conoces, déjalos vacíos y revisa qué falta.")
        filas = st.data_editor(
            st.session_state.lab_filas, num_rows="dynamic", hide_index=True,
            column_config={"id": st.column_config.TextColumn("VLAN"), "nombre": st.column_config.TextColumn("Nombre"), "puerto": st.column_config.TextColumn("Puerto de acceso"), "host": st.column_config.TextColumn("Equipo conectado")},
            key=f"lab_editor_{st.session_state.lab_editor_version}", width="stretch",
        )
        st.caption("Añade o elimina filas en la tabla; entre 1 y 16 conexiones.")
        st.text_area("Objetivo y requisitos", max_chars=1500, key="lab_objetivo")
        datos = {"tipo": st.session_state.lab_tipo, "nombre": st.session_state.lab_nombre,
                 "equipo": {clave: st.session_state[f"lab_{clave}"] for clave in ("alias", "modelo", "ios")},
                 "vlans": [{k: str(v or "") for k, v in fila.items()} for fila in filas], "objetivo": st.session_state.lab_objetivo}
        firma = json.dumps(datos, sort_keys=True, ensure_ascii=False)
        if firma != st.session_state.get("lab_firma"):
            _descartar()
            st.session_state.lab_firma = firma
        if st.button("Revisar datos", key="lab_revisar", type="primary"):
            try:
                st.session_state.lab_revision = preparar_tarea(TareaLaboratorio(**datos))
            except ValidationError:
                st.error("Revisa la longitud de los campos y registra entre 1 y 16 conexiones.")
            except ValueError as error:
                st.error(str(error))
    with salida_col:
        st.markdown("### 2. Revisión")
        revision = st.session_state.get("lab_revision")
        if revision:
            if revision["faltantes"]:
                st.warning("Completa estos datos: " + "; ".join(revision["faltantes"]))
            else:
                st.info("Campos completos. Revisa la solicitud antes de generar.")
            st.caption("Validación técnica de VLAN y puertos: pendiente. Revisar campos no consulta a la IA.")
            with st.expander("Datos y solicitud que se enviarán"):
                st.code(revision["prompt"], language=None)
            confirmado = st.checkbox("Revisé estos datos ficticios y quiero generar una propuesta.", key="lab_confirmado")
            if st.button("Generar propuesta", disabled=not confirmado or bool(revision["faltantes"]), type="primary"):
                st.session_state.lab_resultado = None
                try:
                    with st.spinner("Generando propuesta…"):
                        st.session_state.lab_resultado = asyncio.run(generar_tarea(TareaLaboratorio(**revision["datos"]), confirmado, cadena))
                except ValueError as error:
                    st.error(str(error))
                except Exception as error:
                    logger.error("Falló laboratorio Streamlit. tipo=%s", type(error).__name__)
                    st.error("No se pudo generar la propuesta. Intenta nuevamente.")
            st.button("Descartar revisión", on_click=_descartar)
        else:
            st.caption("Completa el formulario y pulsa Revisar datos. Este paso no consulta a la IA.")
        st.markdown("### 3. Resultado")
        resultado = st.session_state.get("lab_resultado")
        if resultado:
            if resultado["estado"] == "respuesta_generada":
                st.warning("Respuesta generada · Propuesta pendiente de verificación")
            else:
                st.warning("Sin propuesta · Revisa el aviso")
            mostrar_respuesta(resultado["respuesta"])
        else:
            st.caption("Sin propuesta para estos datos.")
        st.caption("Comprobación en laboratorio: no realizada. Generar una respuesta no ejecuta comandos ni certifica conectividad.")

"""Formulario y resultados del laboratorio en Streamlit; reglas en backend.laboratorio."""
import asyncio
import json
import logging

import streamlit as st
from pydantic import ValidationError

from backend.generador import formatear_propuesta
from backend.laboratorio import TareaLaboratorio, ejemplo_laboratorio, preparar_tarea, generar_tarea

logger = logging.getLogger(__name__)


def _firma(datos):
    return json.dumps(datos, sort_keys=True, ensure_ascii=False)


def _cargar_datos(datos):
    for clave in ("tipo", "nombre", "objetivo"):
        st.session_state[f"lab_{clave}"] = datos[clave]
    for clave in ("alias", "modelo", "ios"):
        st.session_state[f"lab_{clave}"] = datos["equipo"][clave]
    st.session_state.lab_filas = datos["vlans"]
    st.session_state.lab_editor_version = st.session_state.get("lab_editor_version", 0) + 1
    _descartar()


def _reabrir(almacen):
    """Carga un caso guardado y su última propuesta; el resultado queda hasta que se edite un dato."""
    try:
        caso = almacen.obtener_caso(st.session_state.lab_caso_sel)
    except LookupError:
        st.session_state.lab_aviso = "Caso no encontrado."
        return
    _cargar_datos(caso["tarea"])
    st.session_state.lab_caso_id = caso["caso_id"]
    st.session_state.lab_firma = _firma(caso["tarea"])
    st.session_state.lab_aviso = ""
    if caso["propuesta"]:
        st.session_state.lab_resultado = {"estado": "reabierto", "texto": caso["propuesta"]["texto"], "caso_id": caso["caso_id"],
                                          "comprobacion_laboratorio": caso["propuesta"]["comprobacion_laboratorio"]}


def _cargar_ejemplo():
    st.session_state.lab_caso_id = None
    datos = ejemplo_laboratorio()
    for clave in ("tipo", "nombre", "objetivo"):
        st.session_state[f"lab_{clave}"] = datos[clave]
    for clave in ("alias", "modelo", "ios"):
        st.session_state[f"lab_{clave}"] = datos["equipo"][clave]
    st.session_state.lab_filas = datos["vlans"]
    st.session_state.lab_editor_version = st.session_state.get("lab_editor_version", 0) + 1
    _descartar()


def _analizar_evidencia(almacen):
    """Registra las salidas pegadas como evidencia del caso abierto; no ejecuta nada en dispositivos."""
    caso_id = st.session_state.get("lab_caso_id")
    st.session_state.lab_diag_aviso = ""
    try:
        resultado = almacen.registrar_evidencia(caso_id, st.session_state.get("lab_evidencia", ""))
    except LookupError:
        st.session_state.lab_diag_aviso = "Caso no encontrado."
        return
    except ValueError as error:
        st.session_state.lab_diag_aviso = str(error)
        return
    st.session_state.lab_diag_omitidos = [o["motivo"] for o in resultado["omitidos"]]
    if resultado["registradas"]:
        st.session_state.lab_evidencia = ""


def _descartar():
    st.session_state.lab_diag_omitidos = []
    st.session_state.lab_diag_aviso = ""
    st.session_state.lab_revision = None
    st.session_state.lab_resultado = None
    st.session_state.lab_confirmado = False


def mostrar_laboratorio(cadena, mostrar_respuesta, rag=None, almacen=None):
    if "lab_filas" not in st.session_state:
        _cargar_ejemplo()
    st.subheader("Espacio de laboratorio")
    st.caption("VLAN y puertos de acceso · Solo datos ficticios · Un switch, sin IP, trunk ni enrutamiento entre VLAN")
    datos_col, salida_col = st.columns([1.15, 1], gap="large")
    with datos_col:
        st.markdown("### 1. Datos de la práctica")
        st.button("Cargar ejemplo de laboratorio", on_click=_cargar_ejemplo)
        if almacen is not None:
            casos = almacen.listar_casos()
            if casos:
                st.selectbox("Casos guardados", [c["id"] for c in casos], key="lab_caso_sel",
                             format_func=lambda i: next(f"{c['nombre'] or 'Sin nombre'} · {c['estado']} · {c['actualizado'][:16]}" for c in casos if c["id"] == i))
                st.button("Reabrir caso", on_click=_reabrir, args=(almacen,))
            if st.session_state.get("lab_aviso"):
                st.warning(st.session_state.lab_aviso)
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
        firma = _firma(datos)
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
            if revision["errores"]:
                st.error("Corrige estos datos: " + " ".join(revision["errores"]))
            if revision["faltantes"]:
                st.warning("Completa estos datos: " + "; ".join(revision["faltantes"]))
            elif not revision["errores"]:
                st.info("Campos completos y reglas aprobadas. Revisa la solicitud antes de generar.")
            for aviso in revision["advertencias"]:
                st.caption("⚠ " + aviso)
            etiquetas = {"reglas_aprobadas": "reglas aprobadas", "rechazada": "rechazada", "incompleta": "incompleta"}
            st.caption(f"Validación por reglas: {etiquetas[revision['validacion_tecnica']]}. No equivale a una prueba en el simulador. Revisar no consulta a la IA.")
            if revision["propuesta"]:
                with st.expander("Propuesta determinista (sin IA)"):
                    mostrar_respuesta(formatear_propuesta(revision["propuesta"]))
            with st.expander("Datos y solicitud que se enviarán"):
                st.code(revision["prompt"], language=None)
            confirmado = st.checkbox("Revisé estos datos ficticios y quiero generar una propuesta.", key="lab_confirmado")
            if st.button("Generar propuesta", disabled=not confirmado or bool(revision["faltantes"]) or bool(revision["errores"]), type="primary"):
                st.session_state.lab_resultado = None
                try:
                    with st.spinner("Generando propuesta…"):
                        st.session_state.lab_resultado = asyncio.run(generar_tarea(TareaLaboratorio(**revision["datos"]), confirmado, cadena, rag, almacen, st.session_state.get("lab_caso_id")))
                    if st.session_state.lab_resultado["caso_id"]:
                        st.session_state.lab_caso_id = st.session_state.lab_resultado["caso_id"]
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
                st.warning("Propuesta con explicación de IA · Validada por reglas, pendiente de comprobar en laboratorio")
            elif resultado["estado"] == "reabierto":
                comprobacion = resultado["comprobacion_laboratorio"]
                st.warning("Caso reabierto · " + ("Comprobación en laboratorio: " + comprobacion if comprobacion != "no_realizada" else "pendiente de comprobar en laboratorio"))
            else:
                st.warning("Propuesta sin explicación de IA · Revisa el aviso")
            if resultado.get("caso_id"):
                st.caption(f"Caso guardado: {resultado['caso_id'][:8]}")
            mostrar_respuesta(resultado["texto"])
        else:
            st.caption("Sin propuesta para estos datos.")
        st.caption("Comprobación en laboratorio: no realizada. Generar una respuesta no ejecuta comandos ni certifica conectividad.")
        st.markdown("### 4. Diagnóstico con evidencia")
        caso_abierto = st.session_state.get("lab_caso_id")
        if almacen is None or not caso_abierto:
            st.caption("Genera o reabre un caso para diagnosticarlo con las salidas de tu simulador.")
        else:
            st.caption("Ejecuta los comandos en tu simulador y pega las salidas (show vlan brief, show interfaces <puerto> switchport). Se comparan con los datos declarados; no se consulta ningún dispositivo.")
            st.text_area("Salidas de verificación", max_chars=8000, height=180, key="lab_evidencia")
            st.button("Analizar salidas", on_click=_analizar_evidencia, args=(almacen,))
            if st.session_state.get("lab_diag_aviso"):
                st.error(st.session_state.lab_diag_aviso)
            for motivo in st.session_state.get("lab_diag_omitidos", []):
                st.warning("No se registró: " + motivo)
            try:
                diagnostico = almacen.obtener_diagnostico(caso_abierto)
            except LookupError:
                diagnostico = None
            if diagnostico and diagnostico["estado"] != "sin_evidencia":
                mostrar_respuesta(diagnostico["texto"])

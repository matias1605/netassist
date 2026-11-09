"""Formulario y resultados del laboratorio en Streamlit; reglas en backend.laboratorio."""
import asyncio
import json
import logging
import secrets

import streamlit as st
from pydantic import ValidationError

from backend.casos import validar_usuario
from backend.generador import formatear_propuesta
from backend.informes import ESTADOS, generar_informe, nombre_archivo
from estilos_streamlit import ENCABEZADO_LAB, card_head, form_sec
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
        caso = almacen.obtener_caso(st.session_state.lab_caso_sel, st.session_state.lab_usuario)
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
        resultado = almacen.registrar_evidencia(caso_id, st.session_state.get("lab_evidencia", ""), st.session_state.lab_usuario)
    except LookupError:
        st.session_state.lab_diag_aviso = "Caso no encontrado."
        return
    except ValueError as error:
        st.session_state.lab_diag_aviso = str(error)
        return
    st.session_state.lab_diag_omitidos = [o["motivo"] for o in resultado["omitidos"]]
    if resultado["registradas"]:
        st.session_state.lab_evidencia = ""


def _archivar(almacen, caso_id, archivado):
    try:
        almacen.archivar_caso(caso_id, archivado, st.session_state.lab_usuario)
        st.session_state.lab_aviso = "Caso archivado; vuelve a verlo con «Incluir archivados»." if archivado else "Caso restaurado."
    except LookupError:
        st.session_state.lab_aviso = "Caso no encontrado."


def _descartar():
    st.session_state.lab_diag_omitidos = []
    st.session_state.lab_diag_aviso = ""
    st.session_state.lab_revision = None
    st.session_state.lab_resultado = None
    st.session_state.lab_confirmado = False


def mostrar_laboratorio(cadena, mostrar_respuesta, rag=None, almacen=None):
    if "lab_filas" not in st.session_state:
        _cargar_ejemplo()
    if "lab_usuario" not in st.session_state:
        st.session_state.lab_usuario = secrets.token_urlsafe(24)
    st.html(ENCABEZADO_LAB)
    with st.expander("Probar con un ejemplo"):
        st.caption("Se rellenará «Prepara tu práctica» automáticamente.")
        st.button("Cargar ejemplo de laboratorio", on_click=_cargar_ejemplo)
    with st.expander("Mi clave de casos"):
        st.text_input("Clave personal de casos", key="lab_usuario", max_chars=64,
                      help="Separa tus casos de los de otras personas. No es una contraseña de cuenta: guárdala para reabrir tus casos en otra sesión.")
    try:
        validar_usuario(st.session_state.lab_usuario)
    except ValueError as error:
        st.error(str(error))
        return
    if st.session_state.get("lab_usuario_activo") != st.session_state.lab_usuario:
        st.session_state.lab_usuario_activo = st.session_state.lab_usuario
        st.session_state.lab_caso_id = None
        _descartar()
    if almacen is not None:
        with st.expander("Mis prácticas guardadas"):
            estados = ["(todos)"] + list(ESTADOS)
            filtro = st.selectbox("Estado", estados, key="lab_filtro_estado", format_func=lambda e: e if e == "(todos)" else ESTADOS[e])
            st.checkbox("Incluir archivados", key="lab_ver_archivados")
            casos = almacen.listar_casos(st.session_state.lab_usuario, None if filtro == "(todos)" else filtro, st.session_state.lab_ver_archivados)
            if casos:
                st.selectbox("Casos guardados", [c["id"] for c in casos], key="lab_caso_sel",
                             format_func=lambda i: next(f"{c['nombre'] or 'Sin nombre'} · {ESTADOS.get(c['estado'], c['estado'])}{' · archivado' if c['archivado'] else ''} · {c['actualizado'][:16]}" for c in casos if c["id"] == i))
                st.button("Reabrir caso", on_click=_reabrir, args=(almacen,))
            else:
                st.caption("No hay casos con este filtro.")
            if st.session_state.get("lab_aviso"):
                st.warning(st.session_state.lab_aviso)

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

    # --- 02 · Tu práctica: revisión, resultado y comprobaciones -----------------------------
    with st.container(key="lab-practica"):
        st.html(card_head("02", "Tu práctica", "Revisa los datos, genera la propuesta y comprueba con tu simulador."))
        tab_revision, tab_config, tab_comprob = st.tabs(["Revisión", "Configuración", "Comprobaciones"])
        with tab_revision:
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
                            st.session_state.lab_resultado = asyncio.run(generar_tarea(TareaLaboratorio(**revision["datos"]), confirmado, cadena, rag, almacen, st.session_state.get("lab_caso_id"), st.session_state.lab_usuario))
                        if st.session_state.lab_resultado["caso_id"]:
                            st.session_state.lab_caso_id = st.session_state.lab_resultado["caso_id"]
                    except ValueError as error:
                        st.error(str(error))
                    except Exception as error:
                        logger.error("Falló laboratorio Streamlit. tipo=%s", type(error).__name__)
                        st.error("No se pudo generar la propuesta. Intenta nuevamente.")
                if st.session_state.get("lab_resultado"):
                    st.success("Propuesta lista: mírala en la pestaña «Configuración».")
                st.button("Descartar revisión", on_click=_descartar)
            else:
                st.caption("Completa el formulario y pulsa Revisar datos. Este paso no consulta a la IA.")
        with tab_config:
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
            caso_abierto = st.session_state.get("lab_caso_id")
            if almacen is not None and caso_abierto:
                try:
                    caso_actual = almacen.obtener_caso(caso_abierto, st.session_state.lab_usuario)
                    informe = generar_informe(caso_actual, almacen.obtener_diagnostico(caso_abierto, usuario=st.session_state.lab_usuario),
                                              almacen.listar_evidencias(caso_abierto, st.session_state.lab_usuario))
                    st.download_button("Descargar informe (.md)", informe, file_name=nombre_archivo(caso_actual), mime="text/markdown")
                    st.button("Restaurar caso" if caso_actual["archivado"] else "Archivar caso", on_click=_archivar, args=(almacen, caso_abierto, not caso_actual["archivado"]))
                except LookupError:
                    st.session_state.lab_caso_id = None
        with tab_comprob:
            st.markdown("#### Diagnóstico con evidencia")
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
                    diagnostico = almacen.obtener_diagnostico(caso_abierto, usuario=st.session_state.lab_usuario)
                except LookupError:
                    diagnostico = None
                if diagnostico and diagnostico["estado"] != "sin_evidencia":
                    mostrar_respuesta(diagnostico["texto"])

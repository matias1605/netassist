"""Pruebas de servicios y Streamlit de la fase 2, sin proveedores ni modelos reales."""
import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from backend import main
from backend.casos import AlmacenCasos
from backend.laboratorio import TareaLaboratorio, ejemplo_laboratorio, preparar_tarea, generar_tarea
from backend.llm import MENSAJE_FALLBACK


class LaboratorioTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.datos = ejemplo_laboratorio()
        self.tarea = TareaLaboratorio(**self.datos)
        self.cadena = MagicMock(ainvoke=AsyncMock(return_value="Propuesta de SW1 pendiente de verificar."))

    def test_ejemplo_y_revision_sin_generacion(self):
        revision = preparar_tarea(self.tarea)
        self.assertFalse(revision["faltantes"])
        self.assertEqual(revision["validacion_tecnica"], "reglas_aprobadas")
        self.assertEqual(revision["comprobacion_laboratorio"], "no_realizada")
        self.assertIn("concisa y precisa", revision["prompt"])
        self.assertIn("GigabitEthernet0/2", revision["prompt"])
        self.cadena.ainvoke.assert_not_called()

    async def test_confirma_y_no_certifica_laboratorio(self):
        resultado = await generar_tarea(self.tarea, True, self.cadena)
        self.assertEqual(resultado["estado"], "respuesta_generada")
        self.assertEqual(resultado["comprobacion_laboratorio"], "no_realizada")
        self.assertEqual(resultado["validacion_tecnica"], "reglas_aprobadas")
        entrada = self.cadena.ainvoke.call_args.args[0]
        self.assertEqual(len(entrada["mensajes"]), 1)
        self.assertEqual(entrada["mensajes"][0]["content"], preparar_tarea(self.tarea)["prompt"])

    async def test_sin_confirmacion_no_genera(self):
        with self.assertRaises(ValueError):
            await generar_tarea(self.tarea, False, self.cadena)
        self.cadena.ainvoke.assert_not_called()

    async def test_faltantes_juntos_no_generan(self):
        self.datos["equipo"]["modelo"] = " "
        self.datos["equipo"]["ios"] = ""
        self.datos["vlans"][0]["puerto"] = ""
        tarea = TareaLaboratorio(**self.datos)
        # La versión de IOS es opcional: solo faltan el modelo y el puerto.
        self.assertEqual(len(preparar_tarea(tarea)["faltantes"]), 2)
        with self.assertRaisesRegex(ValueError, "Modelo.*Puerto"):
            await generar_tarea(tarea, True, self.cadena)
        self.cadena.ainvoke.assert_not_called()

    def test_topologia_no_inventa_modelo(self):
        self.datos["tipo"] = "topologia"
        self.datos["equipo"]["modelo"] = self.datos["equipo"]["ios"] = ""
        revision = preparar_tarea(TareaLaboratorio(**self.datos))
        self.assertFalse(revision["faltantes"])
        self.assertIn("sin comandos de configuración", revision["prompt"])
        self.assertEqual(revision["datos"]["equipo"]["modelo"], "")

    def test_datos_bloqueados_y_limites(self):
        for campo, valor in (("objetivo", "token=privado"), ("objetivo", "x"*1501), ("vlans", []), ("vlans", self.datos["vlans"]*9), ("tipo", "ejecutar")):
            datos = copy.deepcopy(self.datos)
            datos[campo] = valor
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                preparar_tarea(TareaLaboratorio(**datos))

    async def test_respaldo_total_no_es_propuesta(self):
        self.cadena.ainvoke.return_value = MENSAJE_FALLBACK
        resultado = await generar_tarea(self.tarea, True, self.cadena)
        self.assertEqual(resultado["estado"], "propuesta_sin_explicacion")
        self.assertEqual(resultado["comprobacion_laboratorio"], "no_realizada")


class ApiLaboratorioTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main.app.state.rag_error = None
        self.datos = ejemplo_laboratorio()
        # Aísla la base de casos: las pruebas nunca escriben en la base real.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(main, "almacen", AlmacenCasos(Path(tmp.name) / "casos.db"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ejemplo_y_preparar_no_llaman_ia(self):
        with patch.object(main, "cadena", MagicMock(ainvoke=AsyncMock())) as cadena:
            self.assertEqual(self.client.get("/laboratorio/ejemplo").json(), self.datos)
            resultado = self.client.post("/laboratorio/preparar", json=self.datos)
            self.assertEqual(resultado.status_code, 200)
            self.assertEqual(resultado.json()["datos"], self.datos)
            cadena.ainvoke.assert_not_called()

    def test_exige_revision_y_datos_completos(self):
        with patch.object(main, "cadena", MagicMock(ainvoke=AsyncMock())) as cadena:
            self.assertEqual(self.client.post("/laboratorio/generar", json={"tarea": self.datos}).status_code, 422)
            self.datos["equipo"]["modelo"] = ""
            self.assertEqual(self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True}).status_code, 422)
            cadena.ainvoke.assert_not_called()

    def test_estado_resultado_y_fallos(self):
        with patch.object(main, "cadena", MagicMock(ainvoke=AsyncMock(return_value="Propuesta"))):
            resultado = self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True})
            self.assertEqual(resultado.json()["estado"], "respuesta_generada")
            self.assertEqual(resultado.json()["comprobacion_laboratorio"], "no_realizada")
        with patch.object(main, "cadena", MagicMock(ainvoke=AsyncMock(side_effect=RuntimeError("secreto")))):
            resultado = self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True})
            self.assertEqual(resultado.status_code, 503)
            self.assertNotIn("secreto", resultado.text)
        main.app.state.rag_error = "no disponible"
        self.assertEqual(self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True}).status_code, 503)

    def test_datos_sensibles_no_generan(self):
        self.datos["objetivo"] = "password=ejemplo"
        with patch.object(main, "cadena", MagicMock(ainvoke=AsyncMock())) as cadena:
            self.assertEqual(self.client.post("/laboratorio/preparar", json=self.datos).status_code, 422)
            self.assertEqual(self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True}).status_code, 422)
            cadena.ainvoke.assert_not_called()


class StreamlitLaboratorioTests(unittest.TestCase):
    def app(self):
        codigo = '''
import streamlit as st
from laboratorio_ui import mostrar_laboratorio
class Cadena:
    async def ainvoke(self, entrada):
        st.session_state.llamadas = st.session_state.get("llamadas", 0) + 1
        return "Propuesta de SW1"
mostrar_laboratorio(Cadena(), st.markdown)
'''
        return AppTest.from_string(codigo, default_timeout=30).run()

    def button(self, app, label):
        return next(b for b in app.button if b.label == label)

    def test_revisar_confirmar_generar_y_editar_invalida(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.button(app, "Revisar datos").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(self.button(app, "Generar propuesta").disabled)
        app.checkbox(key="lab_confirmado").check().run()
        self.button(app, "Generar propuesta").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["llamadas"], 1)
        self.assertEqual(app.session_state["lab_resultado"]["estado"], "respuesta_generada")
        app.text_input(key="lab_alias").set_value("SW_EDITADO").run()
        self.assertIsNone(app.session_state["lab_revision"])
        self.assertIsNone(app.session_state["lab_resultado"])
        self.assertFalse(app.session_state["lab_confirmado"])

    def test_faltantes_descartar_y_recargar_ejemplo(self):
        app = self.app()
        app.text_input(key="lab_modelo").set_value("").run()
        self.button(app, "Revisar datos").click().run()
        self.assertTrue(self.button(app, "Generar propuesta").disabled)
        self.assertIn("Modelo", app.warning[0].value)
        self.button(app, "Descartar revisión").click().run()
        self.assertIsNone(app.session_state["lab_revision"])
        self.button(app, "Cargar ejemplo de laboratorio").click().run()
        self.assertEqual(app.text_input(key="lab_modelo").value, ejemplo_laboratorio()["equipo"]["modelo"])
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()

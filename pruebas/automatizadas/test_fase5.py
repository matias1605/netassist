"""Pruebas de la fase 5: acceso por usuario, estados, archivado e informe exportable."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from backend import casos, main
from backend.casos import AlmacenCasos, CasoNoEncontrado
from backend.informes import generar_informe, nombre_archivo
from backend.laboratorio import ejemplo_laboratorio
from test_fase4 import SW_OK_1, SW_OK_2, VLAN_OK, VLAN_PUERTO_EN_DEFAULT

ANA = "ana-clave-de-prueba-0001"
LUIS = "luis-clave-de-prueba-0002"


def propuesta_minima():
    from backend.generador import generar_propuesta
    from backend.laboratorio import TareaLaboratorio
    propuesta = generar_propuesta(TareaLaboratorio(**ejemplo_laboratorio()), [], ["cisco_ios_basico.txt"])
    return propuesta


class AccesoPorUsuarioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "casos.db"
        self.almacen = AlmacenCasos(self.ruta)
        self.caso = self.almacen.guardar_caso(ejemplo_laboratorio(), usuario=ANA)

    def test_ajeno_equivale_a_inexistente_en_todas_las_operaciones(self):
        operaciones = [
            lambda: self.almacen.obtener_caso(self.caso, LUIS),
            lambda: self.almacen.obtener_diagnostico(self.caso, usuario=LUIS),
            lambda: self.almacen.registrar_evidencia(self.caso, VLAN_OK, LUIS),
            lambda: self.almacen.listar_evidencias(self.caso, LUIS),
            lambda: self.almacen.guardar_propuesta(self.caso, propuesta_minima(), usuario=LUIS),
            lambda: self.almacen.registrar_comprobacion(self.caso, "correcta", "salida", LUIS),
            lambda: self.almacen.guardar_caso(ejemplo_laboratorio(), self.caso, LUIS),
            lambda: self.almacen.archivar_caso(self.caso, True, LUIS),
            lambda: self.almacen.obtener_caso(self.caso),  # sin clave tampoco
        ]
        for numero, operacion in enumerate(operaciones):
            with self.subTest(operacion=numero), self.assertRaises(CasoNoEncontrado):
                operacion()
        self.assertEqual(self.almacen.listar_evidencias(self.caso, ANA), [])  # nada se escribió
        self.assertEqual(self.almacen.obtener_caso(self.caso, ANA)["estado"], "borrador")

    def test_listado_solo_muestra_casos_propios(self):
        self.almacen.guardar_caso(ejemplo_laboratorio(), usuario=LUIS)
        self.assertEqual(len(self.almacen.listar_casos(ANA)), 1)
        self.assertEqual(len(self.almacen.listar_casos(LUIS)), 1)
        self.assertEqual(self.almacen.listar_casos(), [])

    def test_clave_invalida_se_rechaza_y_no_se_guarda_en_claro(self):
        for clave in ("corta", "con espacios en la clave", "ñ" * 20, "x" * 65):
            with self.subTest(clave=clave[:6]), self.assertRaises(ValueError):
                self.almacen.listar_casos(clave)
        with closing(sqlite3.connect(self.ruta)) as con:
            self.assertNotIn(ANA, con.execute("SELECT propietario FROM casos").fetchone()[0])

    def test_casos_anteriores_sin_propietario_siguen_accesibles_y_se_adoptan(self):
        antigua = Path(self.tmp.name) / "v2.db"
        with closing(sqlite3.connect(antigua)) as con, con:
            for migracion in casos.MIGRACIONES[:2]:
                con.executescript("BEGIN;" + migracion + "COMMIT;")
            con.execute("PRAGMA user_version = 2")
            con.execute("INSERT INTO casos(id, nombre, tipo, creado, actualizado) VALUES (?,?,?,?,?)", ("a" * 32, "previo", "configuracion", "x", "x"))
        migrada = AlmacenCasos(antigua)
        self.assertEqual([c["id"] for c in migrada.listar_casos(ANA)], ["a" * 32])
        migrada.guardar_caso(ejemplo_laboratorio(), "a" * 32, ANA)  # regenerar lo adopta
        with self.assertRaises(CasoNoEncontrado):
            migrada.obtener_caso("a" * 32, LUIS)

    def test_archivar_oculta_y_restaura_sin_perder_datos(self):
        self.almacen.registrar_evidencia(self.caso, VLAN_OK, ANA)
        self.almacen.archivar_caso(self.caso, True, ANA)
        self.assertEqual(self.almacen.listar_casos(ANA), [])
        archivados = self.almacen.listar_casos(ANA, archivados=True)
        self.assertTrue(archivados[0]["archivado"])
        self.assertEqual(archivados[0]["evidencias"], 1)
        self.almacen.archivar_caso(self.caso, False, ANA)
        self.assertEqual(len(self.almacen.listar_casos(ANA)), 1)

    def test_filtro_por_estado_y_resumen_de_lista(self):
        otro = self.almacen.guardar_caso(ejemplo_laboratorio(), usuario=ANA)
        self.almacen.guardar_propuesta(otro, propuesta_minima(), usuario=ANA)
        self.almacen.registrar_comprobacion(otro, "correcta", "show vlan brief", ANA)
        self.assertEqual([c["id"] for c in self.almacen.listar_casos(ANA, estado="comprobado")], [otro])
        self.assertEqual(self.almacen.listar_casos(ANA, estado="comprobado")[0]["comprobacion"], "correcta")
        self.assertEqual(len(self.almacen.listar_casos(ANA)), 2)


class InformeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.almacen = AlmacenCasos(Path(self.tmp.name) / "casos.db")
        self.caso = self.almacen.guardar_caso(ejemplo_laboratorio(), usuario=ANA)

    def informe(self, fuentes=None):
        caso = self.almacen.obtener_caso(self.caso, ANA)
        diag = self.almacen.obtener_diagnostico(self.caso, fuentes, ANA)
        return generar_informe(caso, diag, self.almacen.listar_evidencias(self.caso, ANA)), caso

    def test_caso_sin_propuesta_ni_evidencia(self):
        texto, caso = self.informe()
        self.assertIn("Aún no hay propuesta", texto)
        self.assertIn("Aún no se han registrado salidas", texto)
        self.assertIn("ADMINISTRACION", texto)
        self.assertIn("Limitaciones", texto)
        self.assertTrue(nombre_archivo(caso).startswith("informe-") and nombre_archivo(caso).endswith(".md"))

    def test_informe_completo_recupera_requisitos_propuesta_fuentes_y_evidencias(self):
        self.almacen.guardar_propuesta(self.caso, propuesta_minima(), "Explica la VLAN.", ANA)
        self.almacen.registrar_evidencia(self.caso, VLAN_PUERTO_EN_DEFAULT, ANA)
        self.almacen.registrar_comprobacion(self.caso, "fallida", "salida pegada del laboratorio", ANA)
        texto, _ = self.informe(["cisco_ios_basico.txt"])
        for esperado in ("Separar ambos grupos", "switchport access vlan 10", "cisco_ios_basico.txt", "Explica la VLAN.", "Comprobación en laboratorio:** fallida",
                         "salida pegada del laboratorio", "### E1", "[E1]", "Hay discrepancias", "no fueron ejecutados"):
            with self.subTest(esperado=esperado):
                self.assertIn(esperado, texto)

    def test_salida_con_triple_comilla_no_rompe_el_bloque(self):
        self.almacen.registrar_evidencia(self.caso, VLAN_OK + "\n```\ninyección\n```", ANA)
        texto, _ = self.informe()
        self.assertEqual(texto.count("```") % 2, 0)

    def test_evidencias_obsoletas_se_indican_sin_listarlas(self):
        self.almacen.registrar_evidencia(self.caso, VLAN_OK, ANA)
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["id"] = "30"
        self.almacen.guardar_caso(datos, self.caso, ANA)
        texto, _ = self.informe()
        self.assertIn("fuera de vigencia", texto)
        self.assertNotIn("### E1", texto)

    def test_celdas_de_tabla_escapan_barras(self):
        datos = ejemplo_laboratorio()
        datos["nombre"] = "Práctica | con barra"
        self.almacen.guardar_caso(datos, self.caso, ANA)
        texto, caso = self.informe()
        self.assertNotIn("/", nombre_archivo(caso))


class ApiUsuariosTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        almacen = AlmacenCasos(Path(self.tmp.name) / "casos.db")
        for objetivo, valor, nuevo in ((main, "almacen", almacen), (main, "cadena", MagicMock(ainvoke=AsyncMock(return_value="Explicación.")))):
            p = patch.object(objetivo, valor, nuevo)
            p.start()
            self.addCleanup(p.stop)
        r = patch.object(main.rag_service, "buscar", MagicMock(return_value=[{"archivo": "cisco_ios_basico.txt"}]))
        r.start()
        self.addCleanup(r.stop)
        main.app.state.rag_error = None
        self.client = TestClient(main.app)
        self.datos = ejemplo_laboratorio()
        respuesta = self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True}, headers={"X-Usuario": ANA})
        self.assertEqual(respuesta.status_code, 200)
        self.caso = respuesta.json()["caso_id"]

    def cabecera(self, usuario):
        return {"X-Usuario": usuario}

    def test_otro_usuario_recibe_404_en_todas_las_rutas(self):
        c = self.caso
        luis = self.cabecera(LUIS)
        respuestas = [
            self.client.get(f"/casos/{c}", headers=luis),
            self.client.get(f"/casos/{c}/diagnostico", headers=luis),
            self.client.get(f"/casos/{c}/evidencias", headers=luis),
            self.client.get(f"/casos/{c}/informe", headers=luis),
            self.client.post(f"/casos/{c}/evidencias", json={"salida": VLAN_OK}, headers=luis),
            self.client.post(f"/casos/{c}/comprobacion", json={"resultado": "correcta", "salida": "x"}, headers=luis),
            self.client.post(f"/casos/{c}/archivado", json={"archivado": True}, headers=luis),
            self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True, "caso_id": c}, headers=luis),
            self.client.get(f"/casos/{c}"),
        ]
        self.assertEqual([r.status_code for r in respuestas], [404] * len(respuestas))
        self.assertEqual(self.client.get("/casos", headers=luis).json(), [])
        self.assertEqual(self.client.get(f"/casos/{c}", headers=self.cabecera(ANA)).status_code, 200)

    def test_clave_invalida_422(self):
        self.assertEqual(self.client.get("/casos", headers={"X-Usuario": "corta"}).status_code, 422)

    def test_flujo_lista_filtro_archivado_e_informe(self):
        ana = self.cabecera(ANA)
        self.client.post(f"/casos/{self.caso}/evidencias", json={"salida": VLAN_OK + SW_OK_1 + SW_OK_2}, headers=ana)
        lista = self.client.get("/casos", headers=ana).json()
        self.assertEqual((lista[0]["id"], lista[0]["evidencias"]), (self.caso, 3))
        self.assertEqual(self.client.get("/casos?estado=comprobado", headers=ana).json(), [])
        informe = self.client.get(f"/casos/{self.caso}/informe", headers=ana).json()
        self.assertTrue(informe["nombre_archivo"].endswith(".md"))
        self.assertIn("coherentes con lo declarado", informe["markdown"])
        self.assertIn("cisco_ios_basico.txt", informe["markdown"])
        archivado = self.client.post(f"/casos/{self.caso}/archivado", json={"archivado": True}, headers=ana)
        self.assertTrue(archivado.json()["archivado"])
        self.assertEqual(self.client.get("/casos", headers=ana).json(), [])
        self.assertEqual(len(self.client.get("/casos?archivados=true", headers=ana).json()), 1)

    def test_cors_permite_la_cabecera_de_usuario(self):
        r = self.client.options("/casos", headers={"Origin": main.FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-usuario"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("x-usuario", r.headers["access-control-allow-headers"].lower())


class StreamlitUsuariosTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = str(Path(self.tmp.name) / "casos.db").replace("\\", "/")

    def app(self):
        codigo = f'''
import streamlit as st
from backend.casos import AlmacenCasos
from laboratorio_ui import mostrar_laboratorio
class Cadena:
    async def ainvoke(self, entrada):
        return "Explicación de SW1"
mostrar_laboratorio(Cadena(), st.markdown, None, AlmacenCasos("{self.ruta}"))
'''
        return AppTest.from_string(codigo, default_timeout=30).run()

    def test_la_clave_de_sesion_separa_casos_y_se_puede_reutilizar(self):
        almacen = AlmacenCasos(self.ruta)
        almacen.guardar_caso(ejemplo_laboratorio(), usuario=ANA)
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["lab_usuario"])
        self.assertNotEqual(app.session_state["lab_usuario"], ANA)
        self.assertFalse(any(s.label == "Casos guardados" for s in app.selectbox))  # no ve los de Ana
        app.text_input(key="lab_usuario").set_value(ANA).run()
        self.assertTrue(any(s.label == "Casos guardados" for s in app.selectbox))
        app.text_input(key="lab_usuario").set_value("corta").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Clave" in e.value for e in app.error))


if __name__ == "__main__":
    unittest.main()

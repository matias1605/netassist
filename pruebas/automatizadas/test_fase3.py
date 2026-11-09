"""Pruebas de la fase 3: validadores, generador por plantilla, persistencia y API de casos."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from backend import main
from backend.casos import MIGRACIONES, AlmacenCasos, CasoNoEncontrado
from backend.laboratorio import TareaLaboratorio, ejemplo_laboratorio, generar_tarea, preparar_tarea
from backend.validadores import normalizar_puerto


def tarea_con(**cambios):
    datos = ejemplo_laboratorio()
    for clave, valor in cambios.items():
        datos[clave] = valor
    return TareaLaboratorio(**datos)


class ValidadoresTests(unittest.TestCase):
    def errores(self, tarea):
        return preparar_tarea(tarea)["errores"]

    def test_caso_de_referencia_aprobado(self):
        revision = preparar_tarea(tarea_con())
        self.assertEqual(revision["errores"], [])
        self.assertEqual(revision["validacion_tecnica"], "reglas_aprobadas")
        self.assertEqual(revision["comprobacion_laboratorio"], "no_realizada")

    def test_vlan_invalidas_se_rechazan(self):
        for valor in ("0", "1", "4095", "1003", "abc", "-5", "10.5", "²"):
            datos = ejemplo_laboratorio()
            datos["vlans"][0]["id"] = valor
            with self.subTest(vlan=valor):
                revision = preparar_tarea(TareaLaboratorio(**datos))
                self.assertTrue(revision["errores"])
                self.assertEqual(revision["validacion_tecnica"], "rechazada")
                self.assertIsNone(revision["propuesta"])

    def test_puertos_invalidos_y_duplicados(self):
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["puerto"] = "Eth9"
        self.assertTrue(any("inválido" in e for e in self.errores(TareaLaboratorio(**datos))))
        datos = ejemplo_laboratorio()
        datos["vlans"][1]["puerto"] = "gi0/1"  # mismo puerto que GigabitEthernet0/1 con otra VLAN
        self.assertTrue(any("ya está asignado" in e for e in self.errores(TareaLaboratorio(**datos))))
        self.assertEqual(normalizar_puerto("Fa0/2"), "FastEthernet0/2")
        self.assertEqual(normalizar_puerto("gig1/0/3"), "GigabitEthernet1/0/3")
        self.assertIsNone(normalizar_puerto("Gi0"))

    def test_nombres_y_hosts(self):
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["nombre"] = "con espacio"
        datos["vlans"][1]["host"] = datos["vlans"][0]["host"]
        datos["equipo"]["alias"] = "1SW"
        mensajes = " ".join(self.errores(TareaLaboratorio(**datos)))
        self.assertIn("nombre de VLAN", mensajes)
        self.assertIn("ya está conectado", mensajes)
        self.assertIn("Alias", mensajes)

    def test_vlan_con_dos_nombres(self):
        datos = ejemplo_laboratorio()
        datos["vlans"][1]["id"] = datos["vlans"][0]["id"]
        self.assertTrue(any("dos nombres" in e for e in self.errores(TareaLaboratorio(**datos))))

    def test_modelo_no_2960_solo_advierte(self):
        datos = ejemplo_laboratorio()
        datos["equipo"]["modelo"] = "Catalyst 3750"
        revision = preparar_tarea(TareaLaboratorio(**datos))
        self.assertEqual(revision["errores"], [])
        self.assertTrue(revision["advertencias"])
        self.assertIn(revision["advertencias"][0], revision["propuesta"]["advertencias"])

    def test_incompleto_no_es_aprobado(self):
        datos = ejemplo_laboratorio()
        datos["equipo"]["modelo"] = ""
        revision = preparar_tarea(TareaLaboratorio(**datos))
        self.assertEqual(revision["validacion_tecnica"], "incompleta")
        self.assertIsNone(revision["propuesta"])


class GeneradorTests(unittest.TestCase):
    def test_comandos_por_plantilla(self):
        propuesta = preparar_tarea(tarea_con())["propuesta"]
        comandos = propuesta["comandos_por_equipo"][0]
        self.assertEqual(comandos["equipo"], "SW1")
        self.assertEqual(comandos["comandos"][0], "configure terminal")
        self.assertEqual(comandos["comandos"][-1], "end")
        for esperado in ("vlan 10", " name ADMINISTRACION", "interface GigabitEthernet0/2", " switchport access vlan 20"):
            self.assertIn(esperado, comandos["comandos"])
        self.assertIn("show vlan brief", propuesta["verificaciones"])
        self.assertEqual(propuesta["estado_validacion"], "reglas_aprobadas")
        self.assertEqual(propuesta["datos_faltantes"], [])

    def test_abreviatura_se_normaliza_y_vlan_no_se_repite(self):
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["puerto"] = "Gi0/1"
        datos["vlans"][1]["id"], datos["vlans"][1]["nombre"] = "10", "ADMINISTRACION"
        comandos = preparar_tarea(TareaLaboratorio(**datos))["propuesta"]["comandos_por_equipo"][0]["comandos"]
        self.assertIn("interface GigabitEthernet0/1", comandos)
        self.assertEqual(comandos.count("vlan 10"), 1)

    def test_topologia_derivada_de_los_datos(self):
        propuesta = preparar_tarea(tarea_con(tipo="topologia"))["propuesta"]
        self.assertEqual(propuesta["comandos_por_equipo"], [])
        topologia = propuesta["topologia"]
        self.assertTrue(topologia["mermaid"].startswith("graph LR"))
        self.assertIn('SW1 -- "GigabitEthernet0/1 · VLAN 10" --- PC_ADMIN', topologia["mermaid"])
        self.assertEqual(len(topologia["enlaces"]), 2)
        self.assertNotIn("192.", topologia["mermaid"])
        self.assertTrue(any("no certifica" in s for s in topologia["supuestos"]))

    def test_ids_mermaid_seguros(self):
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["host"] = "PC.admin-1"
        mermaid = preparar_tarea(TareaLaboratorio(**datos))["propuesta"]["topologia"]["mermaid"]
        self.assertIn('PC_admin_1["PC.admin-1"]', mermaid)


class AlmacenTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "datos" / "casos.db"
        self.almacen = AlmacenCasos(self.ruta)
        self.cadena = MagicMock(ainvoke=AsyncMock(return_value="Explicación breve."))
        self.rag = MagicMock(buscar=MagicMock(return_value=[{"archivo": "cisco_ios_basico.txt", "texto": "x", "distancia": 0.1}]))

    async def test_guardar_reabrir_y_fuentes(self):
        resultado = await generar_tarea(tarea_con(), True, self.cadena, self.rag, self.almacen)
        caso = self.almacen.obtener_caso(resultado["caso_id"])
        self.assertEqual(caso["tarea"], ejemplo_laboratorio())
        self.assertEqual(caso["propuesta"]["fuentes"], ["cisco_ios_basico.txt"])
        self.assertEqual(caso["propuesta"]["explicacion"], "Explicación breve.")
        self.assertEqual(caso["propuesta"]["comprobacion_laboratorio"], "no_realizada")
        self.assertEqual(caso["estado"], "propuesta")
        # Persistencia real: una instancia nueva sobre el mismo archivo ve el caso.
        self.assertEqual(AlmacenCasos(self.ruta).listar_casos()[0]["id"], resultado["caso_id"])

    async def test_regenerar_conserva_caso_y_actualiza_datos(self):
        primero = await generar_tarea(tarea_con(), True, self.cadena, self.rag, self.almacen)
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["id"] = "30"
        segundo = await generar_tarea(TareaLaboratorio(**datos), True, self.cadena, self.rag, self.almacen, primero["caso_id"])
        self.assertEqual(segundo["caso_id"], primero["caso_id"])
        self.assertEqual(len(self.almacen.listar_casos()), 1)
        self.assertEqual(self.almacen.obtener_caso(primero["caso_id"])["tarea"]["vlans"][0]["id"], "30")

    async def test_rechazo_y_faltantes_no_guardan_ni_llaman_ia(self):
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["id"] = "4095"
        with self.assertRaisesRegex(ValueError, "Corrige"):
            await generar_tarea(TareaLaboratorio(**datos), True, self.cadena, self.rag, self.almacen)
        datos = ejemplo_laboratorio()
        datos["equipo"]["ios"] = ""
        with self.assertRaisesRegex(ValueError, "IOS"):
            await generar_tarea(TareaLaboratorio(**datos), True, self.cadena, self.rag, self.almacen)
        self.cadena.ainvoke.assert_not_called()
        self.assertEqual(self.almacen.listar_casos(), [])

    async def test_fallo_de_rag_no_impide_propuesta(self):
        self.rag.buscar.side_effect = RuntimeError("sin índice")
        resultado = await generar_tarea(tarea_con(), True, self.cadena, self.rag, self.almacen)
        self.assertEqual(resultado["propuesta"]["fuentes"], [])

    async def test_proveedores_caidos_conserva_propuesta_determinista(self):
        from backend.llm import MENSAJE_FALLBACK
        self.cadena.ainvoke.return_value = MENSAJE_FALLBACK
        resultado = await generar_tarea(tarea_con(), True, self.cadena, self.rag, self.almacen)
        self.assertEqual(resultado["estado"], "propuesta_sin_explicacion")
        self.assertTrue(resultado["propuesta"]["comandos_por_equipo"])
        self.assertEqual(self.almacen.obtener_caso(resultado["caso_id"])["propuesta"]["explicacion"], "")

    def test_ids_invalidos_y_desconocidos(self):
        for caso_id in ("x", "../../etc", "0" * 32, "A" * 32):
            with self.subTest(caso_id=caso_id), self.assertRaises(CasoNoEncontrado):
                self.almacen.obtener_caso(caso_id)

    def test_datos_sensibles_no_se_guardan(self):
        datos = ejemplo_laboratorio()
        datos["objetivo"] = "password=ejemplo"
        with self.assertRaises(ValueError):
            self.almacen.guardar_caso(datos)
        self.assertEqual(self.almacen.listar_casos(), [])

    async def test_comprobacion_manual(self):
        resultado = await generar_tarea(tarea_con(), True, self.cadena, self.rag, self.almacen)
        caso_id = resultado["caso_id"]
        with self.assertRaises(ValueError):
            self.almacen.registrar_comprobacion(caso_id, "correcta", "  ")
        with self.assertRaises(ValueError):
            self.almacen.registrar_comprobacion(caso_id, "correcta", "token=privado")
        self.almacen.registrar_comprobacion(caso_id, "correcta", "SW1#show vlan brief\n10 ADMINISTRACION active Gi0/1")
        caso = self.almacen.obtener_caso(caso_id)
        self.assertEqual(caso["estado"], "comprobado")
        self.assertEqual(caso["propuesta"]["comprobacion_laboratorio"], "correcta")
        self.assertIn("show vlan brief", caso["propuesta"]["salida_laboratorio"])

    def test_comprobacion_sin_propuesta(self):
        caso_id = self.almacen.guardar_caso(ejemplo_laboratorio())
        with self.assertRaisesRegex(ValueError, "propuesta"):
            self.almacen.registrar_comprobacion(caso_id, "correcta", "salida")

    def test_esquema_versionado_y_claves_foraneas(self):
        con = sqlite3.connect(self.ruta)
        self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], len(MIGRACIONES))
        con.close()
        AlmacenCasos(self.ruta)  # reabrir no repite la migración
        caso_id = self.almacen.guardar_caso(ejemplo_laboratorio())
        con = self.almacen._conectar()
        with con:
            con.execute("DELETE FROM casos WHERE id=?", (caso_id,))
        self.assertEqual(con.execute("SELECT COUNT(*) FROM conexiones").fetchone()[0], 0)
        con.close()


class ApiCasosTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        almacen = AlmacenCasos(Path(self.tmp.name) / "casos.db")
        patcher = patch.object(main, "almacen", almacen)
        patcher.start()
        self.addCleanup(patcher.stop)
        main.app.state.rag_error = None
        self.client = TestClient(main.app)
        self.datos = ejemplo_laboratorio()
        self.cadena = MagicMock(ainvoke=AsyncMock(return_value="Explicación."))
        p = patch.object(main, "cadena", self.cadena)
        p.start()
        self.addCleanup(p.stop)
        r = patch.object(main.rag_service, "buscar", MagicMock(return_value=[]))
        r.start()
        self.addCleanup(r.stop)

    def generar(self, **extra):
        return self.client.post("/laboratorio/generar", json={"tarea": self.datos, "confirmado": True, **extra})

    def test_flujo_generar_listar_reabrir_comprobar(self):
        resultado = self.generar()
        self.assertEqual(resultado.status_code, 200)
        caso_id = resultado.json()["caso_id"]
        self.assertEqual(self.client.get("/casos").json()[0]["id"], caso_id)
        caso = self.client.get(f"/casos/{caso_id}").json()
        self.assertEqual(caso["tarea"], self.datos)
        self.assertTrue(caso["propuesta"]["comandos_por_equipo"])
        ok = self.client.post(f"/casos/{caso_id}/comprobacion", json={"resultado": "correcta", "salida": "show vlan brief ok"})
        self.assertEqual(ok.json()["propuesta"]["comprobacion_laboratorio"], "correcta")

    def test_preparar_informa_errores_y_generar_rechaza(self):
        self.datos["vlans"][0]["id"] = "5000"
        revision = self.client.post("/laboratorio/preparar", json=self.datos)
        self.assertEqual(revision.status_code, 200)
        self.assertEqual(revision.json()["validacion_tecnica"], "rechazada")
        rechazo = self.generar()
        self.assertEqual(rechazo.status_code, 422)
        self.assertIn("5000", rechazo.json()["detail"])
        self.cadena.ainvoke.assert_not_called()
        self.assertEqual(self.client.get("/casos").json(), [])

    def test_caso_inexistente_o_invalido(self):
        self.assertEqual(self.client.get("/casos/" + "a" * 32).status_code, 404)
        self.assertEqual(self.client.get("/casos/nope").status_code, 404)
        self.assertEqual(self.generar(caso_id="b" * 32).status_code, 404)
        self.assertEqual(self.client.post("/casos/" + "a" * 32 + "/comprobacion", json={"resultado": "correcta", "salida": "x"}).status_code, 404)
        self.assertEqual(self.client.post("/casos/" + "a" * 32 + "/comprobacion", json={"resultado": "quizá", "salida": "x"}).status_code, 422)


class StreamlitCasosTests(unittest.TestCase):
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
class Rag:
    def buscar(self, consulta):
        return [{{"archivo": "cisco_ios_basico.txt", "texto": "x", "distancia": 0.1}}]
mostrar_laboratorio(Cadena(), st.markdown, Rag(), AlmacenCasos("{self.ruta}"))
'''
        return AppTest.from_string(codigo, default_timeout=30).run()

    def button(self, app, label):
        return next(b for b in app.button if b.label == label)

    def test_reglas_bloquean_generar(self):
        app = self.app()
        app.session_state["lab_filas"][0]["id"] = "4095"
        app.session_state["lab_editor_version"] += 1
        app.run()
        self.button(app, "Revisar datos").click().run()
        self.assertFalse(app.exception)
        self.assertIn("4095", app.error[0].value)
        app.checkbox(key="lab_confirmado").check().run()
        self.assertTrue(self.button(app, "Generar propuesta").disabled)

    def test_generar_guarda_y_reabrir_recupera(self):
        app = self.app()
        self.button(app, "Revisar datos").click().run()
        app.checkbox(key="lab_confirmado").check().run()
        self.button(app, "Generar propuesta").click().run()
        self.assertFalse(app.exception)
        caso_id = app.session_state["lab_resultado"]["caso_id"]
        usuario = app.session_state["lab_usuario"]
        self.assertEqual(len(AlmacenCasos(self.ruta).listar_casos(usuario)), 1)
        # Sesión nueva con la misma clave personal: el caso se reabre con datos y propuesta.
        nueva = self.app()
        nueva.session_state["lab_usuario"] = usuario
        nueva.run()
        nueva.session_state["lab_caso_sel"] = caso_id
        nueva.text_input(key="lab_alias").set_value("OTRO").run()
        self.button(nueva, "Reabrir caso").click().run()
        self.assertFalse(nueva.exception)
        self.assertEqual(nueva.text_input(key="lab_alias").value, "SW1")
        self.assertEqual(nueva.session_state["lab_resultado"]["estado"], "reabierto")
        self.assertIn("switchport access vlan 10", nueva.session_state["lab_resultado"]["texto"])


if __name__ == "__main__":
    unittest.main()

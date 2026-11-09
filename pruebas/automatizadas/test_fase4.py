"""Pruebas de la fase 4: analizador de salidas, pasos y evidencias persistentes, API de diagnóstico."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from backend import main
from backend.casos import MIGRACIONES, AlmacenCasos, CasoNoEncontrado
from backend.diagnostico import analizar_bloque, dividir_bloques, esperado_desde_tarea, pasos_base
from backend.laboratorio import ejemplo_laboratorio

VLAN_OK = """SW1#show vlan brief

VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    Gi0/3, Gi0/4
10   ADMINISTRACION                   active    Gi0/1
20   LABORATORIO                      active    Gi0/2
1002 fddi-default                     act/unsup
"""

VLAN_PUERTO_EN_DEFAULT = VLAN_OK.replace("Gi0/3, Gi0/4", "Gi0/2, Gi0/3, Gi0/4").replace("20   LABORATORIO                      active    Gi0/2", "20   LABORATORIO                      active")

SW_OK_1 = """Name: Gi0/1
Switchport: Enabled
Administrative Mode: static access
Operational Mode: static access
Administrative Trunking Encapsulation: dot1q
Access Mode VLAN: 10 (ADMINISTRACION)
Trunking VLANs Enabled: ALL
"""

SW_OK_2 = SW_OK_1.replace("Gi0/1", "Gi0/2").replace("10 (ADMINISTRACION)", "20 (LABORATORIO)")


def esperado():
    return esperado_desde_tarea(ejemplo_laboratorio())


class AnalizadorTests(unittest.TestCase):
    def test_pasos_base_una_vlan_y_un_puerto_por_conexion(self):
        pasos = pasos_base(esperado())
        self.assertEqual([p["comando"] for p in pasos], ["show vlan brief", "show interfaces GigabitEthernet0/1 switchport", "show interfaces GigabitEthernet0/2 switchport"])

    def test_vlan_brief_coherente(self):
        analisis = analizar_bloque(VLAN_OK, esperado())
        self.assertEqual(analisis["resultado"], "ok")
        self.assertEqual(analisis["clave"], "vlan_brief")

    def test_vlan_brief_puerto_en_otra_vlan(self):
        analisis = analizar_bloque(VLAN_PUERTO_EN_DEFAULT, esperado())
        self.assertEqual(analisis["resultado"], "problema")
        problema = next(o for o in analisis["observaciones"] if o["severidad"] == "problema")
        self.assertIn("VLAN 1", problema["texto"])
        self.assertIn(" switchport access vlan 20", problema["correccion"])

    def test_vlan_inexistente_y_nombre_distinto(self):
        sin_20 = VLAN_OK.replace("20   LABORATORIO                      active    Gi0/2\n", "")
        self.assertIn("no aparece", next(o["texto"] for o in analizar_bloque(sin_20, esperado())["observaciones"] if o["severidad"] == "problema"))
        otro = VLAN_OK.replace("LABORATORIO", "LAB")
        self.assertTrue(any("se llama" in o["texto"] for o in analizar_bloque(otro, esperado())["observaciones"]))

    def test_puerto_ausente_en_tabla_es_ambiguo_no_error(self):
        sin_puerto = VLAN_OK.replace("Gi0/2", "    ")
        analisis = analizar_bloque(sin_puerto, esperado())
        self.assertEqual(analisis["resultado"], "ambiguo")
        self.assertTrue(any("Aclara" in o["texto"] for o in analisis["observaciones"]))

    def test_puertos_extra_en_vlan_son_aviso(self):
        extra = VLAN_OK.replace("active    Gi0/1", "active    Gi0/1, Gi0/5")
        analisis = analizar_bloque(extra, esperado())
        self.assertEqual(analisis["resultado"], "ok")
        self.assertTrue(any(o["severidad"] == "aviso" and "Gi0/5" in o["texto"] or "GigabitEthernet0/5" in o["texto"] for o in analisis["observaciones"]))

    def test_continuacion_de_puertos(self):
        multilinea = VLAN_OK.replace("active    Gi0/1", "active    Gi0/5, Gi0/6\n                                                Gi0/1")
        self.assertEqual(analizar_bloque(multilinea, esperado())["resultado"], "ok")

    def test_tabla_vacia_es_ambiguo(self):
        analisis = analizar_bloque("VLAN Name Status Ports\n---- ---- ---- ----\n", esperado())
        self.assertEqual(analisis["resultado"], "ambiguo")

    def test_switchport_ok_y_modos(self):
        self.assertEqual(analizar_bloque(SW_OK_1, esperado())["resultado"], "ok")
        dinamico = SW_OK_1.replace("static access", "dynamic auto", 1)
        analisis = analizar_bloque(dinamico, esperado())
        self.assertEqual(analisis["resultado"], "problema")
        self.assertIn(" switchport mode access", analisis["observaciones"][0]["correccion"])

    def test_switchport_vlan_distinta(self):
        analisis = analizar_bloque(SW_OK_1.replace("10 (ADMINISTRACION)", "1 (default)"), esperado())
        self.assertEqual(analisis["resultado"], "problema")
        self.assertIn("VLAN 1", analisis["observaciones"][0]["texto"])

    def test_switchport_deshabilitado(self):
        analisis = analizar_bloque(SW_OK_1.replace("Enabled", "Disabled"), esperado())
        self.assertEqual(analisis["resultado"], "problema")

    def test_switchport_sin_enlace_es_aviso_no_error(self):
        analisis = analizar_bloque(SW_OK_1.replace("Operational Mode: static access", "Operational Mode: down"), esperado())
        self.assertEqual(analisis["resultado"], "ok")
        self.assertTrue(any(o["severidad"] == "aviso" for o in analisis["observaciones"]))

    def test_switchport_incompleto_o_desconocido(self):
        incompleto = "Name: Gi0/1\nSwitchport: Enabled\n"
        self.assertEqual(analizar_bloque(incompleto, esperado())["resultado"], "ambiguo")
        ajeno = analizar_bloque(SW_OK_1.replace("Gi0/1", "Gi0/9"), esperado())
        self.assertIsNone(ajeno["clave"])
        self.assertEqual(ajeno["resultado"], "ambiguo")

    def test_texto_no_reconocido(self):
        analisis = analizar_bloque("hola, no sé qué pegar", esperado())
        self.assertEqual(analisis["resultado"], "no_reconocida")
        self.assertIsNone(analisis["clave"])

    def test_dividir_bloques_por_prompt_y_por_nombre(self):
        con_prompt = "SW1#show vlan brief\nVLAN Name Status Ports\n\nSW1#show interfaces Gi0/1 switchport\nName: Gi0/1\n"
        self.assertEqual(len(dividir_bloques(con_prompt)), 2)
        self.assertEqual(len(dividir_bloques(SW_OK_1 + SW_OK_2)), 2)
        self.assertEqual(len(dividir_bloques(VLAN_OK)), 1)
        self.assertEqual(len(dividir_bloques(VLAN_OK + SW_OK_1 + SW_OK_2)), 3)
        self.assertEqual(dividir_bloques("  \n"), [])


class DiagnosticoAlmacenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "casos.db"
        self.almacen = AlmacenCasos(self.ruta)
        self.caso = self.almacen.guardar_caso(ejemplo_laboratorio())

    def test_diagnostico_inicial_sin_evidencia(self):
        d = self.almacen.obtener_diagnostico(self.caso)
        self.assertEqual(d["estado"], "sin_evidencia")
        self.assertEqual([p["estado"] for p in d["pasos"]], ["pendiente"] * 3)
        self.assertEqual(len(d["siguientes"]), 3)

    def test_flujo_hallazgo_correccion_y_cierre(self):
        r = self.almacen.registrar_evidencia(self.caso, VLAN_PUERTO_EN_DEFAULT)
        self.assertEqual(r["estado"], "con_hallazgos")
        evidencia = r["registradas"][0]
        self.assertTrue(all(h["evidencia_id"] == evidencia for h in r["hallazgos"]))
        self.assertIn("switchport access vlan 20", "\n".join(r["correccion_propuesta"]))
        self.assertIn(f"E{evidencia}", r["texto"])
        # Tras corregir, la nueva salida del mismo paso reemplaza al hallazgo.
        r = self.almacen.registrar_evidencia(self.caso, VLAN_OK + SW_OK_1 + SW_OK_2)
        self.assertEqual(r["estado"], "coherente")
        self.assertEqual(r["hallazgos"], [])
        self.assertEqual(r["siguientes"], [])
        self.assertEqual(self.almacen.obtener_caso(self.caso)["estado"], "diagnostico_coherente")
        self.assertEqual(len(self.almacen.listar_evidencias(self.caso)), 4)  # el historial se conserva

    def test_no_repite_pasos_completados_ni_salidas_iguales(self):
        self.almacen.registrar_evidencia(self.caso, VLAN_OK)
        repetido = self.almacen.registrar_evidencia(self.caso, VLAN_OK)
        self.assertEqual(repetido["registradas"], [])
        self.assertIn("ya está completado", repetido["omitidos"][0]["motivo"])
        self.assertEqual(len(self.almacen.listar_evidencias(self.caso)), 1)
        otro = self.almacen.guardar_caso(ejemplo_laboratorio())
        self.almacen.registrar_evidencia(otro, VLAN_PUERTO_EN_DEFAULT)  # paso con hallazgos
        igual = self.almacen.registrar_evidencia(otro, VLAN_PUERTO_EN_DEFAULT)
        self.assertIn("ya se registró", igual["omitidos"][0]["motivo"])

    def test_resultado_ambiguo_pide_aclaracion_y_no_cierra(self):
        r = self.almacen.registrar_evidencia(self.caso, VLAN_OK.replace("Gi0/2", "    "))
        self.assertEqual(r["estado"], "requiere_aclaracion")
        self.assertTrue(r["aclaraciones"])
        self.assertEqual(r["pasos"][0]["estado"], "ambiguo")
        self.assertIn("Aclara", r["siguientes"][0]["accion"])

    def test_en_curso_con_pasos_pendientes(self):
        r = self.almacen.registrar_evidencia(self.caso, VLAN_OK)
        self.assertEqual(r["estado"], "en_curso")
        self.assertEqual(len(r["siguientes"]), 2)
        self.assertEqual(self.almacen.obtener_caso(self.caso)["estado"], "en_diagnostico")

    def test_salida_no_reconocida_no_se_guarda(self):
        r = self.almacen.registrar_evidencia(self.caso, "texto sin relación")
        self.assertEqual(r["registradas"], [])
        self.assertEqual(len(r["omitidos"]), 1)
        self.assertEqual(self.almacen.listar_evidencias(self.caso), [])

    def test_rechazos_sin_escritura(self):
        for salida in ("   ", "x" * 8001, "enable secret miclave123\nName: Gi0/1"):
            with self.subTest(salida=salida[:12]), self.assertRaises(ValueError):
                self.almacen.registrar_evidencia(self.caso, salida)
        with self.assertRaises(CasoNoEncontrado):
            self.almacen.registrar_evidencia("0" * 32, VLAN_OK)
        with self.assertRaises(CasoNoEncontrado):
            self.almacen.obtener_diagnostico("../x")
        self.assertEqual(self.almacen.listar_evidencias(self.caso), [])

    def test_cambiar_datos_declarados_invalida_evidencias(self):
        self.almacen.registrar_evidencia(self.caso, VLAN_OK)
        self.almacen.guardar_caso(ejemplo_laboratorio(), self.caso)  # mismos datos: se conserva
        self.assertEqual(self.almacen.obtener_diagnostico(self.caso)["pasos"][0]["estado"], "completado")
        datos = ejemplo_laboratorio()
        datos["vlans"][0]["id"] = "30"
        self.almacen.guardar_caso(datos, self.caso)
        d = self.almacen.obtener_diagnostico(self.caso)
        self.assertEqual(d["estado"], "sin_evidencia")
        evidencias = self.almacen.listar_evidencias(self.caso)
        self.assertEqual([e["vigente"] for e in evidencias], [False])

    def test_persiste_entre_instancias_y_migra_base_de_fase3(self):
        self.almacen.registrar_evidencia(self.caso, VLAN_OK)
        nueva = AlmacenCasos(self.ruta)
        self.assertEqual(nueva.obtener_diagnostico(self.caso)["pasos"][0]["estado"], "completado")
        with closing(sqlite3.connect(self.ruta)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], len(MIGRACIONES))
        # Base creada con el esquema de la fase 3 (versión 1) se actualiza sin perder casos.
        antigua = Path(self.tmp.name) / "antigua.db"
        from backend import casos
        with closing(sqlite3.connect(antigua)) as con, con:
            con.executescript("BEGIN;" + casos.MIGRACIONES[0] + "PRAGMA user_version = 1;COMMIT;")
            con.execute("INSERT INTO casos VALUES ('a'||hex(randomblob(15)), 'previo', 'configuracion', 'borrador', 'x', 'x')")
        migrada = AlmacenCasos(antigua)
        self.assertEqual(len(migrada.listar_casos()), 1)

    def test_borrar_caso_elimina_evidencias_por_cascada(self):
        self.almacen.registrar_evidencia(self.caso, VLAN_OK)
        with closing(self.almacen._conectar()) as con, con:
            con.execute("DELETE FROM casos WHERE id=?", (self.caso,))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM observaciones").fetchone()[0], 0)


class ApiDiagnosticoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        almacen = AlmacenCasos(Path(self.tmp.name) / "casos.db")
        for objetivo, valor in ((main, "almacen"),):
            p = patch.object(objetivo, valor, almacen)
            p.start()
            self.addCleanup(p.stop)
        r = patch.object(main.rag_service, "buscar", MagicMock(return_value=[{"archivo": "cisco_ios_basico.txt"}]))
        r.start()
        self.addCleanup(r.stop)
        main.app.state.rag_error = None
        self.client = TestClient(main.app)
        self.caso = almacen.guardar_caso(ejemplo_laboratorio())

    def test_flujo_api(self):
        inicial = self.client.get(f"/casos/{self.caso}/diagnostico")
        self.assertEqual(inicial.status_code, 200)
        self.assertEqual(inicial.json()["estado"], "sin_evidencia")
        self.assertEqual(inicial.json()["fuentes"], ["cisco_ios_basico.txt"])
        hallazgo = self.client.post(f"/casos/{self.caso}/evidencias", json={"salida": VLAN_PUERTO_EN_DEFAULT})
        self.assertEqual(hallazgo.status_code, 200)
        self.assertEqual(hallazgo.json()["estado"], "con_hallazgos")
        self.assertEqual(len(hallazgo.json()["registradas"]), 1)
        cierre = self.client.post(f"/casos/{self.caso}/evidencias", json={"salida": VLAN_OK + SW_OK_1 + SW_OK_2})
        self.assertEqual(cierre.json()["estado"], "coherente")
        self.assertEqual(len(self.client.get(f"/casos/{self.caso}/evidencias").json()), 4)

    def test_sin_rag_el_diagnostico_sigue_disponible(self):
        main.app.state.rag_error = "caído"
        d = self.client.get(f"/casos/{self.caso}/diagnostico")
        self.assertEqual(d.status_code, 200)
        self.assertNotIn("fuentes", d.json())

    def test_errores_http(self):
        self.assertEqual(self.client.post(f"/casos/{'0' * 32}/evidencias", json={"salida": VLAN_OK}).status_code, 404)
        self.assertEqual(self.client.get("/casos/no-valido/diagnostico").status_code, 404)
        self.assertEqual(self.client.post(f"/casos/{self.caso}/evidencias", json={"salida": ""}).status_code, 422)
        sensible = self.client.post(f"/casos/{self.caso}/evidencias", json={"salida": "password: abc12345\n" + VLAN_OK})
        self.assertEqual(sensible.status_code, 422)


class StreamlitDiagnosticoTests(unittest.TestCase):
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

    def test_diagnostico_en_streamlit(self):
        app = self.app()
        self.assertFalse(any("Analizar salidas" == b.label for b in app.button))
        caso = AlmacenCasos(self.ruta).guardar_caso(ejemplo_laboratorio())
        app.session_state["lab_caso_id"] = caso
        app.run()
        app.text_area(key="lab_evidencia").set_value(VLAN_PUERTO_EN_DEFAULT).run()
        next(b for b in app.button if b.label == "Analizar salidas").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(AlmacenCasos(self.ruta).obtener_diagnostico(caso)["estado"], "con_hallazgos")
        self.assertTrue(any("Hay discrepancias" in m.value for m in app.markdown))
        # Una salida repetida se informa sin duplicar la evidencia.
        app.text_area(key="lab_evidencia").set_value(VLAN_PUERTO_EN_DEFAULT).run()
        next(b for b in app.button if b.label == "Analizar salidas").click().run()
        self.assertTrue(any("ya se registró" in w.value for w in app.warning))
        self.assertEqual(len(AlmacenCasos(self.ruta).listar_evidencias(caso)), 1)


if __name__ == "__main__":
    unittest.main()

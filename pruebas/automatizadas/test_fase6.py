"""Pruebas de la fase 6: el arnés de evaluación y la advertencia de objetivos fuera de alcance."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluacion"))

import escenarios  # noqa: E402
from backend.laboratorio import TareaLaboratorio, ejemplo_laboratorio  # noqa: E402
from backend.validadores import validar_tarea  # noqa: E402


def advertencias(objetivo):
    datos = {**ejemplo_laboratorio(), "objetivo": objetivo}
    return validar_tarea(TareaLaboratorio(**datos))[1]


class ObjetivoFueraDeAlcanceTests(unittest.TestCase):
    def test_tema_no_cubierto_genera_advertencia(self):
        for objetivo in ("Configurar OSPF entre dos routers", "Levantar un túnel VPN IPsec", "Agregar un trunk hacia SW2"):
            with self.subTest(objetivo=objetivo):
                self.assertTrue(any("fuera del alcance" in a for a in advertencias(objetivo)))

    def test_negacion_o_ausencia_no_genera_advertencia(self):
        for objetivo in (ejemplo_laboratorio()["objetivo"], "Separar grupos, sin trunk ni NAT", "", "Separar ventas de soporte"):
            with self.subTest(objetivo=objetivo):
                self.assertFalse(any("fuera del alcance" in a for a in advertencias(objetivo)))

    def test_nombres_de_dispositivos_no_se_confunden_con_siglas(self):
        self.assertFalse(any("fuera del alcance" in a for a in advertencias("Separar la red de la estación y el director")))


class EvaluacionReproducibleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resultados = escenarios.ejecutar()

    def test_todos_los_escenarios_se_superan(self):
        fallidos = [(r["id"], r["detalle"]) for r in self.resultados if not r["ok"]]
        self.assertEqual(fallidos, [])

    def test_cubre_las_areas_previstas(self):
        self.assertEqual(set(escenarios.metricas(self.resultados)["por_area"]),
                         {"Configuración", "Topología", "Continuidad", "Proveedores", "Conocimiento", "Seguridad"})
        self.assertGreaterEqual(len(self.resultados), 28)

    def test_ids_unicos_y_metricas_coherentes(self):
        ids = [r["id"] for r in self.resultados]
        self.assertEqual(len(ids), len(set(ids)))
        m = escenarios.metricas(self.resultados)
        self.assertEqual(m["superados"], m["escenarios"])

    def test_informe_lista_cada_escenario(self):
        texto = escenarios.informe(self.resultados)
        for r in self.resultados:
            self.assertIn(f"| {r['id']} |", texto)


if __name__ == "__main__":
    unittest.main()

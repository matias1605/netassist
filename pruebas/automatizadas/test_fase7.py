"""Regresiones de fase 7: RAG híbrido, filtro de datos sensibles, cadena detallada,
estado del chat, fichas consultadas y topologías con estilo. Sin claves, red ni modelos."""
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import streamlit as st
from streamlit.testing.v1 import AppTest

from backend import cadena, llm, rag, seguridad, tema
import estilos_streamlit
import topologia_ui

RAIZ = Path(__file__).resolve().parents[2]

def mensaje(texto="¿Qué verifico ahora?", role="user"):
    return {"role": role, "content": texto}


# --- RAG híbrido ------------------------------------------------------------------------
class TerminosClaveTests(unittest.TestCase):
    def test_ignora_tildes_mayusculas_y_palabras_vacias(self):
        terminos = rag.terminos_clave("¿Cómo CONFIGURO el Switchport para la VLAN?")
        self.assertIn("switchport", terminos)
        self.assertIn("vlan", terminos)
        self.assertIn("configuro", terminos)
        self.assertNotIn("como", terminos)
        self.assertNotIn("para", terminos)

    def test_solo_usa_la_consulta_actual(self):
        consulta = "historial con ospf\nConsulta actual: show vlan brief\n\nDatos de mi práctica: SW1 trunk"
        terminos = rag.terminos_clave(consulta)
        self.assertEqual(terminos, {"show", "vlan", "brief"})

    def test_coincidencia_lexica(self):
        self.assertEqual(rag.coincidencia_lexica(set(), "lo que sea"), 0.0)
        self.assertEqual(rag.coincidencia_lexica({"vlan", "trunk"}, "Configuración de una VLAN"), 0.5)
        self.assertEqual(rag.coincidencia_lexica({"configuracion"}, "Configuración"), 1.0)


class _Coleccion:
    """Doble de ChromaDB: devuelve los candidatos indicados, ya ordenados por distancia."""

    def __init__(self, candidatos):
        self.candidatos = candidatos
        self.n_results = None

    def count(self):
        return len(self.candidatos)

    def query(self, query_embeddings, n_results, include):
        self.n_results = n_results
        elegidos = self.candidatos[:n_results]
        return {
            "documents": [[d for d, _, _ in elegidos]],
            "metadatas": [[{"archivo": a} for _, a, _ in elegidos]],
            "distances": [[x for _, _, x in elegidos]],
        }


class BusquedaHibridaTests(unittest.TestCase):
    def servicio(self, candidatos):
        servicio = rag.RagService()
        servicio.modelo = MagicMock(encode=MagicMock(return_value=np.zeros((1, 3))))
        servicio.coleccion = _Coleccion(candidatos)
        return servicio

    def test_sin_inicializar_falla_claro(self):
        with self.assertRaises(RuntimeError):
            rag.RagService().buscar("vlan")

    def test_coleccion_vacia(self):
        self.assertEqual(self.servicio([]).buscar("vlan"), [])

    def test_pide_mas_candidatos_y_devuelve_top_k(self):
        candidatos = [(f"ficha {i} vlan", "a.txt", 0.1 + i / 100) for i in range(20)]
        servicio = self.servicio(candidatos)
        resultado = servicio.buscar("vlan")
        self.assertEqual(servicio.coleccion.n_results, rag.RAG_TOP_K * rag.CANDIDATOS_POR_RESULTADO)
        self.assertEqual(len(resultado), rag.RAG_TOP_K)

    def test_premia_terminos_exactos(self):
        servicio = self.servicio([
            ("Acceso remoto al switch", "basico.txt", 0.30),
            ("Asignar puerto: switchport access vlan 10", "vlan.txt", 0.33),
        ])
        resultado = servicio.buscar("switchport access vlan")
        self.assertEqual(resultado[0]["archivo"], "vlan.txt")
        self.assertEqual(resultado[0]["distancia"], 0.33)  # la distancia real no se altera

    def test_umbral_y_rescate(self):
        umbral = rag.RAG_DISTANCE_THRESHOLD
        servicio = self.servicio([
            ("tema lejano sin relación", "x.txt", umbral + 0.05),
            ("show vlan brief explicado", "vlan.txt", umbral + 0.05),
            ("show vlan brief demasiado lejos", "lejos.txt", umbral + rag.MARGEN_RESCATE + 0.05),
        ])
        archivos = [f["archivo"] for f in servicio.buscar("show vlan brief")]
        self.assertEqual(archivos, ["vlan.txt"])  # rescatado por términos; los otros, fuera

    def test_pregunta_fuera_de_tema_no_devuelve_nada(self):
        servicio = self.servicio([("Configurar OSPF", "r.txt", rag.RAG_DISTANCE_THRESHOLD + 0.2)])
        self.assertEqual(servicio.buscar("cómo hago una pizza"), [])

    def test_descarta_duplicados_y_nulos(self):
        servicio = self.servicio([
            ("Ficha VLAN repetida", "a.txt", 0.2),
            ("Ficha  VLAN   repetida", "b.txt", 0.21),
            (None, "c.txt", 0.1),
        ])
        self.assertEqual([f["archivo"] for f in servicio.buscar("vlan")], ["a.txt"])


# --- Filtro de datos sensibles ----------------------------------------------------------
class DatosSensiblesTests(unittest.TestCase):
    def test_wildcards_y_mascaras_no_bloquean(self):
        for texto in (
            "network 192.168.1.0 0.0.0.255 area 0",
            "access-list 1 permit 192.168.20.0 0.0.0.255",
            "network 10.0.0.0 0.0.0.3 area 0",
            "ip address 192.168.1.1 255.255.255.0",
        ):
            with self.subTest(texto=texto):
                self.assertFalse(seguridad.contiene_datos_sensibles(texto))

    def test_ips_publicas_y_claves_siguen_bloqueadas(self):
        for texto in ("ping 8.8.8.8", "ip route 0.0.0.0 0.0.0.0 200.48.1.1", "enable secret cisco123",
                      "password: [oculto]x", "token=abc"):
            with self.subTest(texto=texto):
                self.assertTrue(seguridad.contiene_datos_sensibles(texto))

    def test_ocultar_deja_texto_sin_datos_sensibles(self):
        texto = ("enable secret ClaveLab123\nusername admin password Clave1\n"
                 "token=abc ping 8.8.8.8\nip address 192.168.1.1 255.255.255.0")
        oculto = seguridad.ocultar_datos_sensibles(texto)
        self.assertFalse(seguridad.contiene_datos_sensibles(oculto))
        for valor in ("ClaveLab123", "Clave1", "abc", "8.8.8.8"):
            self.assertNotIn(valor, oculto)
        self.assertIn("enable secret [oculto]", oculto)
        self.assertIn("192.168.1.1 255.255.255.0", oculto)  # datos de laboratorio intactos
        self.assertEqual(seguridad.ocultar_datos_sensibles("show vlan brief"), "show vlan brief")


class FichasNoBloqueanTests(unittest.IsolatedAsyncioTestCase):
    async def test_claves_de_ejemplo_en_fichas_no_bloquean(self):
        prompt = "Contexto: enable secret ClaveLab123\nnetwork 192.168.1.0 0.0.0.255 area 0"
        with patch.object(llm, "_llamar_gemini", AsyncMock(return_value="Respuesta")) as proveedor:
            self.assertEqual(await llm.generar_con_respaldo([mensaje("¿Cómo configuro SSH?")], prompt), "Respuesta")
            proveedor.assert_awaited_once()

    async def test_clave_del_usuario_si_bloquea(self):
        with patch.object(llm, "_llamar_gemini", AsyncMock()) as proveedor:
            resultado = await llm.generar_con_respaldo([mensaje("mi clave: password Secreta99")], "Cisco")
            self.assertEqual(resultado, seguridad.MENSAJE_DATOS_SENSIBLES)
            proveedor.assert_not_called()


# --- Cadena detallada -------------------------------------------------------------------
class _Rag:
    def __init__(self, fragmentos):
        self.fragmentos = fragmentos

    def buscar(self, consulta):
        return self.fragmentos

    def buscar_con_imagen(self, consulta):
        return self.fragmentos


FRAGMENTOS = [
    {"texto": "a", "archivo": "cisco_ios_vlan_switching.txt", "distancia": 0.2},
    {"texto": "b", "archivo": "cisco_ios_vlan_switching.txt", "distancia": 0.3},
    {"texto": "c", "archivo": "cisco_ios_basico.txt", "distancia": 0.4},
]


class CadenaDetalladaTests(unittest.IsolatedAsyncioTestCase):
    async def invocar(self, fragmentos, respuesta="Respuesta", texto="¿Qué reviso en la VLAN?"):
        with patch.object(cadena, "generar_con_respaldo", AsyncMock(return_value=respuesta)):
            return await cadena.crear_cadena_detallada(_Rag(fragmentos)).ainvoke({"mensajes": [mensaje(texto)]})

    async def test_devuelve_fuentes_sin_repetir(self):
        detalle = await self.invocar(FRAGMENTOS)
        self.assertEqual(detalle["respuesta"], "Respuesta")
        self.assertEqual(detalle["fuentes"], ["cisco_ios_vlan_switching.txt", "cisco_ios_basico.txt"])
        self.assertEqual(detalle["fragmentos"], 3)
        self.assertFalse(detalle["bloqueado"])

    async def test_sin_fichas(self):
        detalle = await self.invocar([])
        self.assertEqual((detalle["fuentes"], detalle["fragmentos"]), ([], 0))

    async def test_bloqueo_de_entrada_no_llama_al_modelo(self):
        with patch.object(cadena, "generar_con_respaldo", AsyncMock()) as proveedor:
            detalle = await cadena.crear_cadena_detallada(_Rag(FRAGMENTOS)).ainvoke({"mensajes": [mensaje("ping 8.8.8.8")]})
        proveedor.assert_not_called()
        self.assertTrue(detalle["bloqueado"])
        self.assertEqual(detalle["fuentes"], [])

    async def test_bloqueo_y_fallo_del_modelo_no_muestran_fichas(self):
        bloqueo = await self.invocar(FRAGMENTOS, seguridad.MENSAJE_DATOS_SENSIBLES)
        self.assertTrue(bloqueo["bloqueado"])
        self.assertEqual(bloqueo["fuentes"], [])
        fallo = await self.invocar(FRAGMENTOS, llm.MENSAJE_FALLBACK)
        self.assertFalse(fallo["bloqueado"])
        self.assertEqual((fallo["fuentes"], fallo["fragmentos"]), ([], 0))

    async def test_cadena_original_sigue_devolviendo_texto(self):
        with patch.object(cadena, "generar_con_respaldo", AsyncMock(return_value="Texto")):
            self.assertEqual(await cadena.crear_cadena(_Rag(FRAGMENTOS)).ainvoke({"mensajes": [mensaje()]}), "Texto")


# --- Alcance: solo temas de redes -------------------------------------------------------
class AlcanceTests(unittest.TestCase):
    FUERA = [
        "¿Quién es el presidente del Perú?", "quien es la presidenta del peru", "¿Cómo hago una pizza?",
        "¿Quién ganó el mundial 2022?", "Resuelve esta ecuación: 2x+3=7", "Escríbeme un poema de amor",
        "¿Cuál es la capital de Francia?",
    ]
    DENTRO = [
        "¿Cómo configuro SSH en el switch?", "la PC1 no hace ping a la PC2", "Gi0/1 aparece down",
        "¿qué es una máscara de subred?", "show vlan brief no muestra nada", "192.168.1.1 no responde",
        "R2 no aprende rutas", "hola", "gracias!", "Genera la topología de mi práctica.",
        "¿Qué hace enable secret?", "Dame los comandos para comprobar mi práctica",
    ]
    HISTORIAL = [mensaje("¿Cómo creo la VLAN 10?"), mensaje("Usa vlan 10.", "assistant")]

    def fuera(self, texto, historial=(), fichas=(), imagen=None):
        entrada = {"mensajes": [*historial, mensaje(texto)], "imagen": imagen}
        return tema.es_fuera_de_tema(entrada, lambda _: list(fichas))

    def test_temas_ajenos_se_detectan_incluso_en_mitad_de_la_conversacion(self):
        for texto in self.FUERA:
            with self.subTest(texto=texto):
                self.assertTrue(self.fuera(texto))
                self.assertTrue(self.fuera(texto, self.HISTORIAL))

    def test_preguntas_de_redes_saludos_y_seguimientos_pasan(self):
        for texto in self.DENTRO:
            with self.subTest(texto=texto):
                self.assertFalse(self.fuera(texto))
        for texto in ("explícalo mejor", "¿y eso por qué pasa?", "no me sale"):
            with self.subTest(texto=texto):
                self.assertFalse(self.fuera(texto, self.HISTORIAL))

    def test_casos_que_deciden_otros(self):
        self.assertFalse(self.fuera("¿Qué ves aquí?", imagen={"mime": "image/png"}))  # captura: siempre se analiza
        self.assertFalse(self.fuera("¿Quién inventó esto?", fichas=[{"archivo": "x"}]))  # las fichas lo cubren
        # Los datos de la práctica que añade la app no convierten la pregunta en "de redes".
        con_practica = "¿Quién es el presidente del Perú?\n\nDatos de mi práctica (ficticios):\n{\"vlans\": []}"
        self.assertTrue(self.fuera(con_practica))
        # Si la búsqueda falla, decide el modelo (no se bloquea por un error interno).
        entrada = {"mensajes": [mensaje("¿Quién es el presidente?")]}
        self.assertFalse(tema.es_fuera_de_tema(entrada, MagicMock(side_effect=RuntimeError("índice"))))


class AlcanceCadenaTests(unittest.IsolatedAsyncioTestCase):
    async def test_fuera_de_tema_no_llama_al_modelo(self):
        with patch.object(cadena, "generar_con_respaldo", AsyncMock()) as proveedor:
            texto = await cadena.crear_cadena(_Rag([])).ainvoke({"mensajes": [mensaje("¿Quién es el presidente del Perú?")]})
            detalle = await cadena.crear_cadena_detallada(_Rag([])).ainvoke({"mensajes": [mensaje("¿Cómo hago una pizza?")]})
        proveedor.assert_not_called()
        self.assertEqual(texto, tema.MENSAJE_FUERA_DE_TEMA)
        self.assertEqual(detalle["respuesta"], tema.MENSAJE_FUERA_DE_TEMA)
        self.assertTrue(detalle["fuera_de_tema"])
        self.assertEqual((detalle["fuentes"], detalle["fragmentos"]), ([], 0))

    async def test_datos_sensibles_tienen_prioridad(self):
        detalle = await cadena.crear_cadena_detallada(_Rag([])).ainvoke({"mensajes": [mensaje("token=abc")]})
        self.assertTrue(detalle["bloqueado"])

    def test_el_prompt_limita_el_alcance(self):
        from backend.prompts import construir_prompt

        prompt = construir_prompt("", "soporte")
        self.assertIn("Solo respondes sobre redes", prompt)
        self.assertFalse(seguridad.contiene_datos_sensibles(prompt))


# --- Estilos del chat -------------------------------------------------------------------
class EstilosChatTests(unittest.TestCase):
    def test_marca_estado(self):
        for estado in ("listo", "pensando", "ok", "duda"):
            self.assertIn(f'data-estado="{estado}"', estilos_streamlit.marca_estado(estado))
        self.assertIn('data-estado="listo"', estilos_streamlit.marca_estado("<script>"))

    def test_fichas_consultadas(self):
        html = estilos_streamlit.fichas_consultadas(["cisco_ios_vlan_switching.txt", "docs\\otra_<b>.txt"])
        self.assertIn("VLAN y switching", html)
        self.assertIn("&lt;b&gt;", html)  # nombres escapados
        self.assertNotIn("<b>", html)
        self.assertIn("Sin fichas relacionadas", estilos_streamlit.fichas_consultadas([]))

    def test_css_sobrevive_al_sanitizado_de_st_html(self):
        # st.html elimina el <style> entero si dentro aparece algo con forma de etiqueta.
        css = estilos_streamlit.estilos()
        cuerpo = css.split("<style>", 1)[1].rsplit("</style>", 1)[0]
        self.assertNotRegex(cuerpo, r"<[a-zA-Z/!]")
        for estado in ("pensando", "ok", "duda"):
            self.assertIn(f'data-estado="{estado}"', css)

    def test_logo_es_imagen_y_no_svg(self):
        panel = estilos_streamlit.panel_izquierdo("soporte")
        self.assertIn('src="data:image/png;base64,', panel)
        self.assertNotIn("<svg", panel)
        self.assertNotIn("Presentación", panel)
        self.assertNotIn("Mis prácticas", panel)


# --- Topologías -------------------------------------------------------------------------
class TopologiaTests(unittest.TestCase):
    PRACTICA = (
        'graph LR\nSW1["SW1 2960"]\n'
        'SW1 -- "Gi0/1" --> PC_ADMIN["PC_ADMIN"]\nSW1 -- "Gi0/2" --> PC_LAB["PC_LAB"]'
    )

    def test_vertical_iconos_y_clases(self):
        codigo, altura, presentes = topologia_ui.preparar_topologia(self.PRACTICA)
        self.assertTrue(codigo.startswith("graph TD"))
        self.assertIn('SW1["fa:fa-network-wired SW1 2960"]', codigo)
        self.assertIn("class SW1 switch", codigo)
        self.assertIn("class PC_ADMIN,PC_LAB pc", codigo)
        self.assertEqual(presentes, ["switch", "pc"])
        self.assertEqual(altura, topologia_ui.ALTURA_BASE + topologia_ui.ALTURA_NIVEL * 2)

    def test_enlace_con_falla_en_rojo_y_nodos_sin_definir(self):
        fuente = 'graph LR\nR1["R1"] -- "G0/1 down" --- R2["R2"]\nR2 --- SW1\nSW1 --- SRV1'
        codigo, _, presentes = topologia_ui.preparar_topologia(fuente)
        self.assertIn("linkStyle 0 stroke:#e5484d", codigo)
        self.assertNotIn("linkStyle 1 ", codigo)
        self.assertIn('SW1["fa:fa-network-wired SW1"]', codigo)
        self.assertIn('SRV1["fa:fa-server SRV1"]', codigo)
        self.assertEqual(presentes, ["router", "switch", "servidor"])

    def test_no_duplica_iconos_ni_toca_otros_diagramas(self):
        ya = 'graph TD\nA["fa:fa-desktop PC1"] --- B["fa:fa-desktop PC2"]'
        self.assertEqual(topologia_ui.preparar_topologia(ya)[0].count("fa:fa-desktop"), 2)
        secuencia = "sequenceDiagram\nA->>B: hola"
        self.assertEqual(topologia_ui.preparar_topologia(secuencia), (secuencia, 320, []))

    def test_altura_con_ciclos_y_tope(self):
        ciclo = "graph TD\nA --- B\nB --- C\nC --- A"
        self.assertLessEqual(topologia_ui.preparar_topologia(ciclo)[1], 900)
        cadena_larga = "graph TD\n" + "\n".join(f"N{i} --> N{i + 1}" for i in range(30))
        self.assertEqual(topologia_ui.preparar_topologia(cadena_larga)[1], 900)

    def test_leyenda(self):
        html = topologia_ui.leyenda(["router", "pc"])
        self.assertIn("fa-shuffle", html)
        self.assertIn("Router", html)
        self.assertIn("PC", html)
        self.assertEqual(topologia_ui.leyenda([]), "")


# --- Chat de Streamlit de punta a punta (RAG y proveedores simulados) --------------------
class ChatStreamlitTests(unittest.TestCase):
    def setUp(self):
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        for parche in (
            patch.object(rag.RagService, "initialize", return_value={"archivos": 1, "fragmentos": 1}),
            patch.object(rag.RagService, "buscar", side_effect=self.buscar),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    @staticmethod
    def buscar(consulta):
        # Como el índice real: lo que no es de redes no encuentra fichas si se busca solo.
        if "pizza" in consulta or consulta.startswith("¿Quién es"):
            return []
        return [{"texto": "switchport access vlan 10", "archivo": "cisco_ios_vlan_switching.txt", "distancia": 0.2}]

    def enviar(self, texto, respuesta="Usa switchport access vlan 10."):
        app = AppTest.from_file(str(RAIZ / "streamlit_app.py"), default_timeout=60)
        app.session_state["chat_abierto"] = True
        app.run()
        self.assertFalse(app.exception)
        with patch.object(cadena, "generar_con_respaldo", AsyncMock(return_value=respuesta)):
            app.chat_input[0].set_value(texto).run()
        self.assertFalse(app.exception)
        return app

    def estado(self, app):
        return app.session_state["estado_chat"]

    def test_respuesta_con_fichas_pone_verde_y_las_muestra(self):
        app = self.enviar("¿Cómo asigno un puerto a la VLAN 10?")
        self.assertEqual(self.estado(app), "ok")
        ultimo = app.session_state["mensajes"][-1]
        self.assertEqual(ultimo["fuentes"], ["cisco_ios_vlan_switching.txt"])
        self.assertTrue(any("VLAN y switching" in h.proto.body for h in app.get("html")))

    def test_pregunta_fuera_de_tema_pone_rojo_sin_llamar_al_modelo(self):
        app = AppTest.from_file(str(RAIZ / "streamlit_app.py"), default_timeout=60)
        app.session_state["chat_abierto"] = True
        app.run()
        with patch.object(cadena, "generar_con_respaldo", AsyncMock(return_value="Hornea a 220 °C")) as proveedor:
            app.chat_input[0].set_value("¿Cómo hago una pizza?").run()
        self.assertFalse(app.exception)
        proveedor.assert_not_called()
        self.assertEqual(self.estado(app), "duda")
        ultimo = app.session_state["mensajes"][-1]
        self.assertEqual(ultimo["content"], tema.MENSAJE_FUERA_DE_TEMA)
        self.assertNotIn("fuentes", ultimo)  # sin chips de fichas

    def test_presidente_en_mitad_de_una_conversacion_de_redes(self):
        app = self.enviar("¿Cómo asigno un puerto a la VLAN 10?")
        with patch.object(cadena, "generar_con_respaldo", AsyncMock(return_value="Es ...")) as proveedor:
            app.chat_input[0].set_value("¿Quién es el presidente del Perú?").run()
        proveedor.assert_not_called()
        self.assertEqual(app.session_state["mensajes"][-1]["content"], tema.MENSAJE_FUERA_DE_TEMA)
        self.assertEqual(self.estado(app), "duda")

    def test_dato_sensible_pone_rojo_sin_fichas(self):
        app = self.enviar("No llego a 8.8.8.8")
        self.assertEqual(self.estado(app), "duda")
        ultimo = app.session_state["mensajes"][-1]
        self.assertTrue(ultimo["bloqueado"])
        self.assertNotIn("fuentes", ultimo)

    def test_clave_de_ejemplo_del_asistente_no_bloquea_la_siguiente_pregunta(self):
        # Regresión: tras una respuesta con "enable secret ClaveLab123", todo quedaba bloqueado.
        app = self.enviar("¿Cómo configuro SSH?", "Usa: enable secret ClaveLab123 y ssh -l admin 192.168.1.2")
        proveedor = AsyncMock(return_value="Revisa la VLAN de administración.")
        with patch.object(cadena, "generar_con_respaldo", proveedor):
            app.chat_input[0].set_value("¿Y cómo lo compruebo desde la PC?").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state["mensajes"][-1]["bloqueado"])
        proveedor.assert_awaited_once()
        enviado = proveedor.await_args.args[0]
        self.assertIn("enable secret [oculto]", enviado[-2]["content"])
        self.assertNotIn("ClaveLab123", str(enviado))
        # La conversación visible conserva la respuesta original.
        self.assertIn("ClaveLab123", app.session_state["mensajes"][1]["content"])

    def test_borrar_chat_reinicia_conversacion_y_estado(self):
        app = self.enviar("¿Cómo asigno un puerto a la VLAN 10?")
        next(b for b in app.button if b.label == "Borrar chat").click().run()
        self.assertEqual(app.session_state["mensajes"], [])
        self.assertEqual(self.estado(app), "listo")

    def test_topologia_en_respuesta_no_rompe(self):
        respuesta = "Aquí está:\n```mermaid\n" + TopologiaTests.PRACTICA + "\n```"
        app = self.enviar("Genera la topología de mi práctica.", respuesta)
        self.assertEqual(self.estado(app), "ok")


if __name__ == "__main__":
    unittest.main()

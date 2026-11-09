"""Regresiones locales de fase 1; sin claves, red ni descarga de modelos."""
import asyncio
import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import chromadb
from chromadb.config import Settings
import numpy as np
from filelock import FileLock, Timeout
from PIL import Image
from fastapi.testclient import TestClient

from backend import cadena, llm, main, rag, seguridad


def mensaje(texto="¿Qué verifico ahora?", role="user"):
    return {"role": role, "content": texto}


def imagen():
    salida = io.BytesIO()
    Image.new("RGB", (8, 8)).save(salida, format="PNG")
    return {"mime": "image/png", "data": base64.b64encode(salida.getvalue()).decode(), "laboratorio_confirmado": True}


class SeguridadTests(unittest.TestCase):
    def test_politica_laboratorio(self):
        for texto in ("192.168.1.1 255.255.255.0", "10.0.0.1", "172.16.0.1", "2001:db8::1", "192.0.2.1", "999.999.999.999", "¿Qué hace enable secret?", "¿Qué es una contraseña?"):
            with self.subTest(texto=texto):
                self.assertFalse(seguridad.contiene_datos_sensibles(texto))
        for texto in ("8.8.8.8", "2606:4700:4700::1111", "token=EJEMPLO_FICTICIO", "enable secret cisco123", "password 7 12345", "contraseña es cisco123", "api_key: ejemplo"):
            with self.subTest(texto=texto):
                self.assertTrue(seguridad.contiene_datos_sensibles(texto))

    def test_limites(self):
        for mensajes in ([], [mensaje()] * 41, [mensaje("x"*12001)], [mensaje("x"*12000)]*5, [mensaje(role="system")], [mensaje(role="assistant")]):
            with self.subTest(cantidad=len(mensajes)), self.assertRaises(ValueError):
                seguridad.validar_historial(mensajes)
        seguridad.validar_historial([mensaje("x"*12000)]*4)

    def test_imagen_decodificada_y_confirmada(self):
        img = imagen()
        seguridad.validar_entrada({"mensajes": [mensaje()], "imagen": img})
        for reemplazo in ({"laboratorio_confirmado": False}, {"data": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()}, {"mime": "image/jpeg"}, {"data": "*"}, {"data": "A"*5_600_001}):
            with self.subTest(reemplazo=list(reemplazo)), self.assertRaises(ValueError):
                seguridad.validar_entrada({"mensajes": [mensaje()], "imagen": {**img, **reemplazo}})
        with patch.object(seguridad, "MAX_IMAGEN_PIXELES", 10), self.assertRaises(ValueError):
            seguridad.validar_imagen(img["mime"], img["data"])


class CadenaTests(unittest.IsolatedAsyncioTestCase):
    async def test_historial_bloqueado_en_ambos_roles(self):
        for rol in ("user", "assistant"):
            proveedor = AsyncMock(return_value="ok")
            with patch.object(cadena, "generar_con_respaldo", proveedor):
                resultado = await cadena.crear_cadena(object()).ainvoke({"mensajes": [mensaje("token=privado", rol), mensaje()]})
            self.assertEqual(resultado, seguridad.MENSAJE_DATOS_SENSIBLES)
            proveedor.assert_not_called()

    async def test_recuperacion_contextual_y_acciones(self):
        class Corpus:
            def buscar(self, consulta):
                self.consulta = consulta
                return []
        corpus = Corpus()
        with patch.object(cadena, "generar_con_respaldo", AsyncMock(return_value="ok")):
            self.assertEqual(await cadena.crear_cadena(corpus).ainvoke({"mensajes": [mensaje("SW1 VLAN 20 Fa0/2 no conecta"), mensaje("show vlan brief: puerto ausente", "assistant"), mensaje()]}), "ok")
        self.assertIn("VLAN 20", corpus.consulta)
        self.assertIn("puerto ausente", corpus.consulta)
        self.assertIn("Qué verifico", corpus.consulta)
        from backend.acciones import obtener_acciones
        acciones = obtener_acciones()
        self.assertEqual(len(acciones), 2)
        for accion in acciones:
            self.assertFalse(seguridad.contiene_datos_sensibles(accion["prompt"]))

    async def test_proveedores(self):
        for primario, secundario, esperado in (("gemini", "groq", "gemini"), (RuntimeError("fallo"), "groq", "groq"), (RuntimeError("fallo"), RuntimeError("fallo"), llm.MENSAJE_FALLBACK), ("", "groq", "groq")):
            with self.subTest(esperado=esperado):
                p = AsyncMock(side_effect=primario) if isinstance(primario, Exception) else AsyncMock(return_value=primario)
                q = AsyncMock(side_effect=secundario) if isinstance(secundario, Exception) else AsyncMock(return_value=secundario)
                with patch.object(llm, "_llamar_gemini", p), patch.object(llm, "_llamar_groq", q):
                    self.assertEqual(await llm.generar_con_respaldo([mensaje()], "Cisco IOS"), esperado)
                self.assertEqual(q.call_count, 0 if esperado == "gemini" else 1)

    async def test_imagen_respaldo_aviso_garantizado(self):
        with patch.object(llm, "_llamar_gemini", AsyncMock(side_effect=RuntimeError())), patch.object(llm, "_llamar_groq", AsyncMock(return_value="Comprueba el cable.")):
            resultado = await llm.generar_con_respaldo([mensaje()], "Cisco", imagen())
            self.assertIn("No pude analizar la imagen", resultado)

    async def test_prompt_real_y_corpus_no_bloquean_laboratorio(self):
        from backend.prompts import construir_prompt
        corpus = Path("docs/cisco_ios_basico.txt").read_text(encoding="utf-8")
        prompt = construir_prompt(corpus, "Docente de laboratorio")
        self.assertFalse(seguridad.contiene_datos_sensibles(prompt))
        with patch.object(llm, "_llamar_gemini", AsyncMock(return_value="Propuesta pendiente de verificación.")) as proveedor:
            self.assertIn("Propuesta", await llm.generar_con_respaldo([mensaje("192.168.1.1 VLAN 20")], prompt))
            proveedor.assert_awaited_once()

    async def test_ruta_alternativa_bloquea_historial(self):
        with patch.object(llm, "_llamar_gemini", AsyncMock()) as proveedor:
            self.assertEqual(await llm.llamar_llm([mensaje("8.8.8.8"), mensaje()], ""), seguridad.MENSAJE_DATOS_SENSIBLES)
            proveedor.assert_not_called()


class TransporteTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_clave_en_cabecera_y_groq_sin_imagen(self):
        peticiones = []
        def responder(request):
            import json
            peticiones.append((request, json.loads(request.content)))
            if "googleapis" in request.url.host:
                return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Correcto"}]}}]})
            return httpx.Response(200, json={"choices": [{"message": {"content": "Solo texto"}}]})
        cliente_real = httpx.AsyncClient
        def cliente(**kwargs):
            return cliente_real(transport=httpx.MockTransport(responder), **kwargs)
        with patch.object(llm.httpx, "AsyncClient", cliente), patch.multiple(llm, GEMINI_API_KEY="clave-ficticia", GEMINI_MODEL="modelo", GROQ_API_KEY="clave-ficticia", GROQ_MODEL="modelo"):
            self.assertEqual(await llm._llamar_gemini([mensaje()], "Cisco", imagen()), "Correcto")
            self.assertEqual(await llm._llamar_groq([mensaje()], "Cisco", imagen()), "Solo texto")
        request, cuerpo = peticiones[0]
        self.assertNotIn("key", request.url.params)
        self.assertEqual(request.headers["x-goog-api-key"], "clave-ficticia")
        self.assertIn("inlineData", cuerpo["contents"][-1]["parts"][0])
        request, cuerpo = peticiones[1]
        self.assertNotIn(imagen()["data"], str(cuerpo))
        self.assertIn(llm.AVISO_SIN_IMAGEN, cuerpo["messages"][-1]["content"])

    async def test_log_no_expone_excepcion(self):
        with patch.object(llm, "_llamar_gemini", AsyncMock(side_effect=RuntimeError("token=NO_PUBLICAR"))), patch.object(llm, "_llamar_groq", AsyncMock(return_value="ok")), self.assertLogs("backend.llm", level="INFO") as registros:
            await llm.generar_con_respaldo([mensaje()], "Cisco")
        self.assertNotIn("NO_PUBLICAR", " ".join(registros.output))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main.app.state.rag_error = None
        main.app.state.rag_summary = {"archivos": 1, "fragmentos": 1}

    def test_rechaza_limites_y_adjuntos(self):
        for cuerpo in ({"messages": [mensaje()]*41}, {"messages": [mensaje("x"*12000)]*5}, {"messages": [mensaje()], "imagen": {**imagen(), "laboratorio_confirmado": False}}):
            self.assertEqual(self.client.post("/chat", json=cuerpo).status_code, 422)

    def test_bloquea_historial(self):
        with patch.object(main, "cadena", MagicMock(ainvoke=AsyncMock())) as servicio:
            respuesta = self.client.post("/chat", json={"messages": [mensaje("token=ejemplo", "assistant"), mensaje()]})
            self.assertEqual(respuesta.json()["reply"], seguridad.MENSAJE_DATOS_SENSIBLES)
            servicio.ainvoke.assert_not_called()

    def test_reindex_administracion_y_fallo_no_deshabilita_chat(self):
        with patch.dict("os.environ", {"REINDEX_ADMIN_TOKEN": "solo-prueba"}), patch.object(main.rag_service, "initialize", side_effect=RuntimeError("fallo")), patch.object(main.rag_service, "coleccion", object()):
            self.assertEqual(self.client.post("/reindexar").status_code, 403)
            self.assertEqual(self.client.post("/reindexar", headers={"X-Admin-Token": "solo-prueba"}).status_code, 503)
            self.assertTrue(self.client.get("/health").json()["rag_ready"])


class Modelo:
    def encode(self, textos, **kwargs):
        return np.array([[1., 0., 0.] for _ in textos])


class IndiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.docs = raiz / "docs"
        self.docs.mkdir()
        self.archivo = self.docs / "manual.txt"
        self.archivo.write_text("VLAN 10 SW1 puertos de acceso", encoding="utf-8")
        self.db = raiz / "db"
        for nombre, valor in (("DOCS_DIR", self.docs), ("CHROMA_DIR", self.db), ("SentenceTransformer", lambda _: Modelo())):
            parche = patch.object(rag, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)
        self.servicio = rag.RagService()
        # Chroma real en memoria; publicación persistente se verifica en archivo temporal.
        self.servicio.cliente = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        self.servicio.initialize(reconstruir=True)

    def test_fallos_conservan_indice_y_reinicio(self):
        anterior = self.servicio.coleccion.name
        referencia = (self.db / "indice_activo.json").read_text()
        for destino in ("lectura", "embeddings", "escritura", "publicacion", "consulta"):
            if destino == "lectura":
                parche = patch.object(rag, "_leer_archivo", side_effect=ValueError("PDF ilegible"))
            elif destino == "embeddings":
                parche = patch.object(self.servicio.modelo, "encode", side_effect=RuntimeError("embeddings"))
            elif destino == "escritura":
                parche = patch("chromadb.api.models.Collection.Collection.add", side_effect=RuntimeError("disco"))
            elif destino == "consulta":
                parche = patch("chromadb.api.models.Collection.Collection.query", side_effect=RuntimeError("consulta"))
            else:
                parche = patch.object(rag.os, "replace", side_effect=OSError("disco"))
            with self.subTest(fallo=destino), parche, self.assertRaises((ValueError, RuntimeError, OSError)):
                self.servicio.initialize(reconstruir=True)
            self.assertEqual(self.servicio.coleccion.name, anterior)
            self.assertEqual((self.db / "indice_activo.json").read_text(), referencia)
            self.assertTrue(self.servicio.buscar("VLAN"))
        nuevo = rag.RagService()
        nuevo.cliente = self.servicio.cliente
        nuevo.initialize()
        self.assertEqual(nuevo.coleccion.name, anterior)

    def test_vacio_y_bloqueo_concurrente(self):
        self.archivo.write_text("")
        with self.assertRaises(ValueError):
            self.servicio.initialize(reconstruir=True)
        with FileLock(str(self.db / "reindex.lock")):
            with self.assertRaises(Timeout):
                self.servicio.initialize(reconstruir=True)
        self.assertTrue(self.servicio.buscar("VLAN"))

    def test_candidata_incompleta_y_sin_relevancia_visual(self):
        anterior = self.servicio.coleccion.name
        with patch("chromadb.api.models.Collection.Collection.add", return_value=None), self.assertRaises(RuntimeError):
            self.servicio.initialize(reconstruir=True)
        self.assertEqual(self.servicio.coleccion.name, anterior)
        with patch.object(self.servicio, "buscar", return_value=[]):
            self.assertEqual(self.servicio.buscar_con_imagen("consulta sin tema"), [])

    def test_publicacion_y_reuso_sin_embeddings(self):
        anterior = self.servicio.coleccion.name
        self.archivo.write_text("VLAN 20 actualizada")
        self.servicio.initialize(reconstruir=True)
        self.assertNotEqual(self.servicio.coleccion.name, anterior)
        self.assertIn("actualizada", self.servicio.buscar_con_imagen("VLAN")[0]["texto"])
        with patch.object(self.servicio.modelo, "encode", side_effect=AssertionError("no reconstruir")):
            self.servicio.initialize()
        self.assertEqual(self.servicio.cliente.get_collection(anterior).count(), 1)


if __name__ == "__main__":
    unittest.main()

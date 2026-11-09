"""API FastAPI de NetAssist."""

import logging
import hmac
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool

from .casos import AlmacenCasos, CasoNoEncontrado
from .config import CASOS_DB_PATH, FRONTEND_ORIGIN, SUPPORT_CONTACT
from .acciones import obtener_acciones
from .cadena import crear_cadena
from .laboratorio import TareaLaboratorio, _fuentes, ejemplo_laboratorio, preparar_tarea, generar_tarea
from .llm import MENSAJE_FALLBACK
from .rag import RagService
from .seguridad import MENSAJE_DATOS_SENSIBLES, contiene_datos_sensibles, validar_imagen, validar_historial

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
rag_service = RagService()
cadena = crear_cadena(rag_service)
almacen = AlmacenCasos(CASOS_DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el índice al arrancar; deja la API disponible si RAG falla."""
    app.state.rag_error = None
    try:
        app.state.rag_summary = await run_in_threadpool(rag_service.initialize)
    except Exception as error:
        app.state.rag_error = str(error)
        app.state.rag_summary = {"archivos": 0, "fragmentos": 0}
        logger.error("No se pudo iniciar RAG. tipo=%s", type(error).__name__)
    yield


app = FastAPI(title="NetAssist API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class Mensaje(BaseModel):
    """Mensaje permitido en el historial enviado por el navegador."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ImagenAdjunta(BaseModel):
    """Imagen en base64 que acompaña al último mensaje del usuario."""

    mime: Literal["image/png", "image/jpeg", "image/webp"]
    data: str = Field(min_length=1, max_length=5_600_000)
    laboratorio_confirmado: bool = False


class SolicitudChat(BaseModel):
    """Historial completo de la conversación del cliente."""

    messages: list[Mensaje] = Field(min_length=1, max_length=40)
    imagen: ImagenAdjunta | None = None

    @model_validator(mode="after")
    def validar_presupuesto(self):
        validar_historial([m.model_dump() for m in self.messages])
        return self


class RespuestaChat(BaseModel):
    """Respuesta uniforme para el frontend."""

    reply: str
    contact: str


@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Indica si la API y el índice local están disponibles."""
    return {
        "status": "ok",
        "rag_ready": request.app.state.rag_error is None,
        "index": request.app.state.rag_summary,
    }


@app.get("/contacto")
async def contacto() -> dict[str, str]:
    """Entrega al frontend la vía de contacto configurada en el backend."""
    return {"contact": SUPPORT_CONTACT}


@app.get("/acciones")
async def acciones() -> list[dict[str, str]]:
    """Borradores editables de acciones rápidas con datos ficticios de laboratorio."""
    return obtener_acciones()


@app.post("/reindexar")
async def reindexar(request: Request) -> dict[str, int]:
    """Vuelve a leer e indexar los documentos de /docs."""
    token = os.getenv("REINDEX_ADMIN_TOKEN", "")
    if token:
        autorizado = hmac.compare_digest(request.headers.get("X-Admin-Token", ""), token)
    else:
        autorizado = request.client is not None and request.client.host in {"127.0.0.1", "::1"}
    if not autorizado:
        raise HTTPException(status_code=403, detail="Reindexación reservada a administración local o token de administración.")
    try:
        resumen = await run_in_threadpool(rag_service.initialize, reconstruir=True)
        request.app.state.rag_error = None
        request.app.state.rag_summary = resumen
        return resumen
    except Exception as error:
        if rag_service.coleccion is None:
            request.app.state.rag_error = "Índice no disponible."
        logger.error("Falló la reindexación; se conserva el índice anterior. tipo=%s", type(error).__name__)
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo reindexar la documentación. Contacta al docente o técnico: {SUPPORT_CONTACT}",
        ) from error


@app.post("/chat", response_model=RespuestaChat)
async def chat(solicitud: SolicitudChat, request: Request) -> RespuestaChat:
    """Recupera manuales y genera una respuesta con el historial recibido."""
    if solicitud.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="El último mensaje debe ser del usuario.")

    if any(contiene_datos_sensibles(m.content) for m in solicitud.messages):
        return RespuestaChat(reply=MENSAJE_DATOS_SENSIBLES, contact=SUPPORT_CONTACT)

    imagen = None
    if solicitud.imagen is not None:
        try:
            if not solicitud.imagen.laboratorio_confirmado:
                raise ValueError("Confirma que revisaste la captura y eliminaste credenciales y datos reales.")
            validar_imagen(solicitud.imagen.mime, solicitud.imagen.data)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        imagen = solicitud.imagen.model_dump()

    mensajes = [mensaje.model_dump() for mensaje in solicitud.messages]
    try:
        if request.app.state.rag_error is not None:
            raise RuntimeError("El índice RAG no está disponible.")
        respuesta = await cadena.ainvoke({"mensajes": mensajes, "imagen": imagen})
        return RespuestaChat(reply=respuesta, contact=SUPPORT_CONTACT)
    except Exception as error:
        logger.error("No se pudo completar el chat. tipo=%s", type(error).__name__)
        return RespuestaChat(reply=MENSAJE_FALLBACK, contact=SUPPORT_CONTACT)


class GeneracionLaboratorio(BaseModel):
    tarea: TareaLaboratorio
    confirmado: bool = False
    caso_id: str | None = Field(default=None, max_length=32)


class EvidenciaDiagnostico(BaseModel):
    salida: str = Field(min_length=1, max_length=8000)


class ComprobacionLaboratorio(BaseModel):
    resultado: Literal["correcta", "fallida"]
    salida: str = Field(min_length=1, max_length=8000)


@app.get("/laboratorio/ejemplo")
async def laboratorio_ejemplo() -> dict:
    return ejemplo_laboratorio()


@app.post("/laboratorio/preparar")
async def laboratorio_preparar(tarea: TareaLaboratorio) -> dict:
    try:
        return preparar_tarea(tarea)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/laboratorio/generar")
async def laboratorio_generar(solicitud: GeneracionLaboratorio, request: Request) -> dict:
    try:
        # Primero revisar incluso si el índice está caído, para informar datos faltantes.
        revision = preparar_tarea(solicitud.tarea)
        if revision["errores"]:
            raise ValueError("Corrige estos datos: " + " ".join(revision["errores"]))
        if not solicitud.confirmado or revision["faltantes"]:
            raise ValueError("Revisa los datos, completa los campos faltantes y confirma antes de generar.")
        if request.app.state.rag_error is not None:
            raise HTTPException(status_code=503, detail="La base de conocimiento no está disponible. Intenta más tarde.")
        return await generar_tarea(solicitud.tarea, solicitud.confirmado, cadena, rag_service, almacen, solicitud.caso_id)
    except CasoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Falló la tarea de laboratorio. tipo=%s", type(error).__name__)
        raise HTTPException(status_code=503, detail="No se pudo generar la propuesta. Intenta nuevamente.") from error


@app.get("/casos")
async def casos_listar() -> list[dict]:
    return await run_in_threadpool(almacen.listar_casos)


@app.get("/casos/{caso_id}")
async def casos_obtener(caso_id: str) -> dict:
    try:
        return await run_in_threadpool(almacen.obtener_caso, caso_id)
    except CasoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/casos/{caso_id}/comprobacion")
async def casos_comprobacion(caso_id: str, datos: ComprobacionLaboratorio) -> dict:
    """Registra el resultado de una prueba manual en simulador o laboratorio."""
    try:
        await run_in_threadpool(almacen.registrar_comprobacion, caso_id, datos.resultado, datos.salida)
        return await run_in_threadpool(almacen.obtener_caso, caso_id)
    except CasoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


CONSULTA_DIAGNOSTICO = "verificar VLAN y puertos de acceso show vlan brief show interfaces switchport"


@app.get("/casos/{caso_id}/diagnostico")
async def casos_diagnostico(caso_id: str) -> dict:
    """Pasos, evidencias y hallazgos del caso. Compara salidas pegadas con lo declarado; no consulta dispositivos."""
    try:
        fuentes = await _fuentes(None if getattr(app.state, "rag_error", None) else rag_service, CONSULTA_DIAGNOSTICO)
        return await run_in_threadpool(almacen.obtener_diagnostico, caso_id, fuentes)
    except CasoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/casos/{caso_id}/evidencias")
async def casos_evidencias(caso_id: str, datos: EvidenciaDiagnostico) -> dict:
    """Analiza salidas de show pegadas por la persona y las guarda como evidencia del caso."""
    try:
        diagnostico = await run_in_threadpool(almacen.registrar_evidencia, caso_id, datos.salida)
        fuentes = await _fuentes(None if getattr(app.state, "rag_error", None) else rag_service, CONSULTA_DIAGNOSTICO)
        if fuentes:
            diagnostico = {**diagnostico, **await run_in_threadpool(almacen.obtener_diagnostico, caso_id, fuentes)}
        return diagnostico
    except CasoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/casos/{caso_id}/evidencias")
async def casos_evidencias_listar(caso_id: str) -> list[dict]:
    try:
        return await run_in_threadpool(almacen.listar_evidencias, caso_id)
    except CasoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

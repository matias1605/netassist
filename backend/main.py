"""API FastAPI de NetAssist."""

import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import FRONTEND_ORIGIN, SUPPORT_CONTACT
from .llm import MENSAJE_FALLBACK, llamar_llm
from .rag import RagService, formatear_contexto
from .seguridad import MENSAJE_DATOS_SENSIBLES, contiene_datos_sensibles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
rag_service = RagService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el índice al arrancar; deja la API disponible si RAG falla."""
    app.state.rag_error = None
    try:
        app.state.rag_summary = rag_service.initialize()
    except Exception as error:
        app.state.rag_error = str(error)
        app.state.rag_summary = {"archivos": 0, "fragmentos": 0}
        logger.exception("No se pudo iniciar RAG; el chat responderá con derivación.")
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


class SolicitudChat(BaseModel):
    """Historial completo de la conversación del cliente."""

    messages: list[Mensaje] = Field(min_length=1)


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


@app.post("/reindexar")
async def reindexar(request: Request) -> dict[str, int]:
    """Vuelve a leer e indexar los documentos de /docs."""
    try:
        resumen = rag_service.initialize()
        request.app.state.rag_error = None
        request.app.state.rag_summary = resumen
        return resumen
    except Exception as error:
        request.app.state.rag_error = str(error)
        logger.exception("Falló la reindexación de documentos.")
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo reindexar la documentación. Contacta al docente o técnico: {SUPPORT_CONTACT}",
        ) from error


@app.post("/chat", response_model=RespuestaChat)
async def chat(solicitud: SolicitudChat, request: Request) -> RespuestaChat:
    """Recupera manuales y genera una respuesta con el historial recibido."""
    if solicitud.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="El último mensaje debe ser del usuario.")

    if contiene_datos_sensibles(solicitud.messages[-1].content):
        return RespuestaChat(reply=MENSAJE_DATOS_SENSIBLES, contact=SUPPORT_CONTACT)

    mensajes = [mensaje.model_dump() for mensaje in solicitud.messages]
    try:
        if request.app.state.rag_error is not None:
            raise RuntimeError("El índice RAG no está disponible.")
        consulta = next(
            mensaje.content for mensaje in reversed(solicitud.messages) if mensaje.role == "user"
        )
        fragmentos = rag_service.buscar(consulta)
        contexto = formatear_contexto(fragmentos)
        respuesta = await llamar_llm(mensajes, contexto)
        return RespuestaChat(reply=respuesta, contact=SUPPORT_CONTACT)
    except Exception as error:
        logger.exception("No se pudo completar la solicitud de chat.")
        return RespuestaChat(reply=MENSAJE_FALLBACK, contact=SUPPORT_CONTACT)

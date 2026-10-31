"""Clientes HTTP asíncronos para Gemini y Groq con failover automático."""

import logging
from urllib.parse import quote

import httpx

from .config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_TIMEOUT_SECONDS,
    SUPPORT_CONTACT,
)
from .prompts import construir_prompt

logger = logging.getLogger(__name__)
MENSAJE_FALLBACK = (
    "Lo siento, no pude obtener una respuesta del asistente en este momento. "
    "Por favor, inténtalo de nuevo más tarde o contacta al docente o técnico: "
    f"{SUPPORT_CONTACT}"
)


def _validar_configuracion() -> None:
    """Comprueba que cada proveedor configurado tenga también su modelo."""
    if GEMINI_API_KEY and not GEMINI_MODEL:
        raise RuntimeError("GEMINI_MODEL debe configurarse si se define GEMINI_API_KEY.")
    if GROQ_API_KEY and not GROQ_MODEL:
        raise RuntimeError("GROQ_MODEL debe configurarse si se define GROQ_API_KEY.")


async def _llamar_gemini(mensajes: list[dict[str, str]], system_prompt: str) -> str:
    """Convierte los roles a contents/model y envía systemInstruction separado."""
    if not GEMINI_API_KEY:
        raise RuntimeError("No está configurada GEMINI_API_KEY.")
    if not GEMINI_MODEL:
        raise RuntimeError("No está configurado GEMINI_MODEL.")

    contenido = [
        {
            "role": "model" if mensaje["role"] == "assistant" else "user",
            "parts": [{"text": mensaje["content"]}],
        }
        for mensaje in mensajes
    ]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(GEMINI_MODEL, safe='')}:generateContent"
    )
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as cliente:
        respuesta = await cliente.post(
            url,
            params={"key": GEMINI_API_KEY},
            headers={"content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": contenido,
                "generationConfig": {"maxOutputTokens": 1200},
            },
        )
    respuesta.raise_for_status()
    datos = respuesta.json()
    candidatos = datos.get("candidates", [])
    partes = (
        candidatos[0].get("content", {}).get("parts", [])
        if candidatos and isinstance(candidatos[0], dict)
        else []
    )
    texto = "\n".join(
        parte["text"]
        for parte in partes
        if isinstance(parte.get("text"), str)
    ).strip()
    if not texto:
        raise ValueError("Gemini devolvió una respuesta sin texto.")
    return texto


async def _llamar_groq(mensajes: list[dict[str, str]], system_prompt: str) -> str:
    """Envía el historial a Groq mediante su endpoint compatible con OpenAI."""
    if not GROQ_API_KEY:
        raise RuntimeError("No está configurada GROQ_API_KEY.")
    if not GROQ_MODEL:
        raise RuntimeError("No está configurado GROQ_MODEL.")

    cuerpo = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, *mensajes],
        "max_tokens": 1200,
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as cliente:
        respuesta = await cliente.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "content-type": "application/json",
            },
            json=cuerpo,
        )
    respuesta.raise_for_status()
    datos = respuesta.json()
    elecciones = datos.get("choices", [])
    mensaje = (
        elecciones[0].get("message", {})
        if elecciones and isinstance(elecciones[0], dict)
        else {}
    )
    texto = mensaje.get("content", "")
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("Groq devolvió una respuesta sin texto.")
    return texto.strip()


async def llamar_llm(mensajes: list[dict[str, str]], contexto_rag: str) -> str:
    """Prueba Gemini primero, pasa a Groq ante un error y siempre devuelve texto."""
    _validar_configuracion()
    system_prompt = construir_prompt(contexto_rag, SUPPORT_CONTACT)

    try:
        return await _llamar_gemini(mensajes, system_prompt)
    except (httpx.HTTPError, ValueError, RuntimeError) as error:
        logger.warning(
            "Gemini no pudo responder; se intentará Groq. Tipo de error: %s",
            type(error).__name__,
        )

    try:
        return await _llamar_groq(mensajes, system_prompt)
    except (httpx.HTTPError, ValueError, RuntimeError) as error:
        logger.error(
            "Gemini y Groq no pudieron responder. Tipo de error: %s",
            type(error).__name__,
        )
        return MENSAJE_FALLBACK

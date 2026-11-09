"""Orquestación de NetAssist con LangChain: datos sensibles -> recuperación -> generación.

La cadena la usan tanto la API FastAPI como la app de Streamlit, así ambas responden igual.
Entrada: {"mensajes": [{"role", "content"}, ...], "imagen": {"mime", "data"} | None}.
Salida: el texto de la respuesta.
"""

from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda, RunnablePassthrough

from .config import SUPPORT_CONTACT
from .llm import MENSAJE_FALLBACK, _llamar_gemini, _llamar_groq, _validar_configuracion
from .prompts import construir_prompt
from .rag import RagService, formatear_contexto
from .seguridad import MENSAJE_DATOS_SENSIBLES, contiene_datos_sensibles


class FichasRetriever(BaseRetriever):
    """Expone la búsqueda en ChromaDB de RagService como un retriever de LangChain."""

    rag: Any
    con_imagen: bool = False

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        servicio: RagService = self.rag
        fragmentos = (
            servicio.buscar_con_imagen(query) if self.con_imagen else servicio.buscar(query)
        )
        return [
            Document(
                page_content=str(fragmento["texto"]),
                metadata={"archivo": fragmento["archivo"], "distancia": fragmento["distancia"]},
            )
            for fragmento in fragmentos
        ]


def _ultima_consulta(entrada: dict[str, Any]) -> str:
    """Texto del último mensaje del usuario, que es lo que se busca en las fichas."""
    return next(m["content"] for m in reversed(entrada["mensajes"]) if m["role"] == "user")


def _tiene_datos_sensibles(entrada: dict[str, Any]) -> bool:
    return contiene_datos_sensibles(_ultima_consulta(entrada))


def crear_cadena(rag: RagService) -> Runnable:
    """Arma la cadena: bloqueo de datos sensibles, recuperación RAG y LLM con respaldo."""
    recuperador_texto = FichasRetriever(rag=rag)
    recuperador_imagen = FichasRetriever(rag=rag, con_imagen=True)

    def recuperar(entrada: dict[str, Any]) -> list[Document]:
        recuperador = recuperador_imagen if entrada.get("imagen") else recuperador_texto
        return recuperador.invoke(_ultima_consulta(entrada))

    def armar_prompt(entrada: dict[str, Any]) -> str:
        fragmentos = [
            {"texto": doc.page_content, "archivo": doc.metadata["archivo"]}
            for doc in entrada["documentos"]
        ]
        return construir_prompt(formatear_contexto(fragmentos), SUPPORT_CONTACT)

    async def generar_gemini(entrada: dict[str, Any]) -> str:
        _validar_configuracion()
        return await _llamar_gemini(entrada["mensajes"], entrada["system_prompt"], entrada.get("imagen"))

    async def generar_groq(entrada: dict[str, Any]) -> str:
        return await _llamar_groq(entrada["mensajes"], entrada["system_prompt"], entrada.get("imagen"))

    async def mensaje_fallback(_: dict[str, Any]) -> str:
        return MENSAJE_FALLBACK

    # Gemini es el modelo principal; si falla, LangChain pasa a Groq y luego al aviso fijo.
    generador = RunnableLambda(generar_gemini).with_fallbacks(
        [RunnableLambda(generar_groq), RunnableLambda(mensaje_fallback)]
    )

    cadena_rag = (
        RunnablePassthrough.assign(documentos=RunnableLambda(recuperar))
        | RunnablePassthrough.assign(system_prompt=RunnableLambda(armar_prompt))
        | generador
    )

    # Los datos sensibles se bloquean antes de buscar o llamar a cualquier modelo.
    return RunnableBranch(
        (RunnableLambda(_tiene_datos_sensibles), RunnableLambda(lambda _: MENSAJE_DATOS_SENSIBLES)),
        cadena_rag,
    )

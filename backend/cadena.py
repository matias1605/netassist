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
from .llm import generar_con_respaldo
from .prompts import construir_prompt
from .rag import RagService, formatear_contexto
from .seguridad import MENSAJE_DATOS_SENSIBLES, contiene_datos_sensibles, validar_entrada


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


def _consulta_contextual(entrada: dict[str, Any]) -> str:
    """Ventana acotada de requisitos y resultados; sin llamada adicional al modelo."""
    mensajes = entrada["mensajes"]
    previos = "\n".join(m["content"][-800:] for m in mensajes[:-1][-6:])
    return f"{previos}\nConsulta actual: {_ultima_consulta(entrada)[-2000:]}"


def _tiene_datos_sensibles(entrada: dict[str, Any]) -> bool:
    return any(contiene_datos_sensibles(m["content"]) for m in entrada["mensajes"])


def crear_cadena(rag: RagService) -> Runnable:
    """Arma la cadena: bloqueo de datos sensibles, recuperación RAG y LLM con respaldo."""
    recuperador_texto = FichasRetriever(rag=rag)
    recuperador_imagen = FichasRetriever(rag=rag, con_imagen=True)

    def recuperar(entrada: dict[str, Any]) -> list[Document]:
        recuperador = recuperador_imagen if entrada.get("imagen") else recuperador_texto
        return recuperador.invoke(_consulta_contextual(entrada))

    def armar_prompt(entrada: dict[str, Any]) -> str:
        fragmentos = [
            {"texto": doc.page_content, "archivo": doc.metadata["archivo"]}
            for doc in entrada["documentos"]
        ]
        return construir_prompt(formatear_contexto(fragmentos), SUPPORT_CONTACT)

    async def generar(entrada: dict[str, Any]) -> str:
        return await generar_con_respaldo(entrada["mensajes"], entrada["system_prompt"], entrada.get("imagen"))

    generador = RunnableLambda(generar)

    cadena_rag = (
        RunnablePassthrough.assign(documentos=RunnableLambda(recuperar))
        | RunnablePassthrough.assign(system_prompt=RunnableLambda(armar_prompt))
        | generador
    )

    # Los datos sensibles se bloquean antes de buscar o llamar a cualquier modelo.
    return RunnableLambda(validar_entrada) | RunnableBranch(
        (RunnableLambda(_tiene_datos_sensibles), RunnableLambda(lambda _: MENSAJE_DATOS_SENSIBLES)),
        cadena_rag,
    )

"""Carga de manuales, fragmentación, indexado y búsqueda semántica local."""

import logging
from pathlib import Path
from typing import Any

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from .config import (
    CHROMA_DIR,
    DOCS_DIR,
    EMBEDDING_MODEL,
    RAG_DISTANCE_THRESHOLD,
    RAG_TOP_K,
)

logger = logging.getLogger(__name__)
COLLECTION_NAME = "manuales_netassist"
CHUNK_WORDS = 500
CHUNK_OVERLAP = 50
FICHA_SEPARATOR = "\n---\n"


def fragmentar_texto(texto: str, tamano: int = CHUNK_WORDS, solapamiento: int = CHUNK_OVERLAP) -> list[str]:
    """Divide el texto por palabras y conserva un solapamiento entre fragmentos."""
    palabras = texto.split()
    if tamano <= 0 or solapamiento < 0 or solapamiento >= tamano:
        raise ValueError("El tamaño debe ser positivo y el solapamiento menor al tamaño.")
    paso = tamano - solapamiento
    return [
        " ".join(palabras[inicio : inicio + tamano])
        for inicio in range(0, len(palabras), paso)
        if palabras[inicio : inicio + tamano]
    ]


def fragmentar_fichas(texto: str) -> list[str]:
    """Trata cada ficha (separada por '---') como un fragmento; divide las muy largas."""
    fichas: list[str] = []
    for bloque in texto.split(FICHA_SEPARATOR):
        bloque = bloque.strip()
        if not bloque:
            continue
        if len(bloque.split()) > CHUNK_WORDS:
            fichas.extend(fragmentar_texto(bloque))
        else:
            fichas.append(bloque)
    return fichas


def _leer_archivo(ruta: Path) -> str:
    """Extrae texto de archivos PDF o TXT admitidos."""
    if ruta.suffix.lower() == ".txt":
        return ruta.read_text(encoding="utf-8", errors="replace")
    lector = PdfReader(str(ruta))
    paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    return "\n".join(paginas)


class RagService:
    """Mantiene el modelo de embeddings y la colección local de ChromaDB."""

    def __init__(self) -> None:
        self.modelo: SentenceTransformer | None = None
        self.cliente: Any | None = None
        self.coleccion: Any | None = None

    def initialize(self) -> dict[str, int]:
        """Carga el modelo local y reconstruye el índice a partir de /docs."""
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.modelo = SentenceTransformer(EMBEDDING_MODEL)
        self.cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))

        self.cliente.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.cliente.delete_collection(COLLECTION_NAME)
        self.coleccion = self.cliente.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        archivos = sorted(
            ruta
            for ruta in DOCS_DIR.rglob("*")
            if ruta.is_file() and ruta.suffix.lower() in {".txt", ".pdf"}
        )
        documentos: list[str] = []
        metadatos: list[dict[str, str | int]] = []
        ids: list[str] = []

        for archivo in archivos:
            texto = _leer_archivo(archivo)
            if archivo.suffix.lower() == ".txt" and FICHA_SEPARATOR in texto:
                fragmentos = fragmentar_fichas(texto)
            else:
                fragmentos = fragmentar_texto(texto)
            for numero, fragmento in enumerate(fragmentos):
                documentos.append(fragmento)
                metadatos.append(
                    {"archivo": str(archivo.relative_to(DOCS_DIR)), "fragmento": numero + 1}
                )
                ids.append(f"{archivo.relative_to(DOCS_DIR).as_posix()}-{numero}")

        if documentos:
            embeddings = self.modelo.encode(documentos, normalize_embeddings=True).tolist()
            self.coleccion.add(
                ids=ids,
                documents=documentos,
                metadatas=metadatos,
                embeddings=embeddings,
            )

        logger.info(
            "Índice RAG actualizado: %s archivo(s), %s fragmento(s).",
            len(archivos),
            len(documentos),
        )
        return {"archivos": len(archivos), "fragmentos": len(documentos)}

    def buscar(self, consulta: str) -> list[dict[str, str | float]]:
        """Devuelve hasta cuatro fragmentos que superen el umbral de relevancia."""
        if self.modelo is None or self.coleccion is None:
            raise RuntimeError("El servicio RAG no está inicializado.")
        if self.coleccion.count() == 0:
            return []

        embedding = self.modelo.encode([consulta], normalize_embeddings=True).tolist()
        resultados = self.coleccion.query(
            query_embeddings=embedding,
            n_results=min(RAG_TOP_K, self.coleccion.count()),
            include=["documents", "metadatas", "distances"],
        )
        documentos = resultados.get("documents", [[]])[0]
        metadatos = resultados.get("metadatas", [[]])[0]
        distancias = resultados.get("distances", [[]])[0]
        relevantes: list[dict[str, str | float]] = []

        for documento, metadata, distancia in zip(documentos, metadatos, distancias):
            if documento is None or distancia is None or distancia > RAG_DISTANCE_THRESHOLD:
                continue
            archivo = str((metadata or {}).get("archivo", "manual sin nombre"))
            relevantes.append(
                {"texto": str(documento), "archivo": archivo, "distancia": float(distancia)}
            )
        return relevantes


def formatear_contexto(fragmentos: list[dict[str, str | float]]) -> str:
    """Prepara fragmentos y referencias para incluirlos en el prompt."""
    if not fragmentos:
        return "No se encontraron fragmentos relevantes en los manuales disponibles."
    bloques = []
    for indice, fragmento in enumerate(fragmentos, start=1):
        bloques.append(
            f"[Fragmento {indice} | Fuente: {fragmento['archivo']}]\n{fragmento['texto']}"
        )
    return "\n\n".join(bloques)

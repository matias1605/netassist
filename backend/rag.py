"""Carga de manuales, fragmentación, indexado y búsqueda semántica local."""

import logging
import json
import os
from uuid import uuid4
from filelock import FileLock
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

    def initialize(self, reconstruir: bool = False) -> dict[str, int]:
        """Reutiliza el índice persistente; publica generaciones mediante referencia atómica.

        El bloqueo de archivo coordina API y Streamlit en el mismo almacenamiento.
        Las generaciones anteriores se conservan para lectores que aún las usan.
        """
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        with FileLock(str(CHROMA_DIR / "reindex.lock"), timeout=1):
            if self.modelo is None:
                self.modelo = SentenceTransformer(EMBEDDING_MODEL)
            if self.cliente is None:
                self.cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
            referencia = CHROMA_DIR / "indice_activo.json"
            if not reconstruir:
                if referencia.exists():
                    datos = json.loads(referencia.read_text(encoding="utf-8"))
                    coleccion = self.cliente.get_collection(datos["coleccion"])
                    if coleccion.count() < 1:
                        raise RuntimeError("El índice activo está vacío.")
                    self.coleccion = coleccion
                    return datos["resumen"]
                # Compatibilidad con el índice anterior sin reconstruirlo al arrancar.
                try:
                    anterior = self.cliente.get_collection(COLLECTION_NAME)
                except Exception:
                    anterior = None
                if anterior is not None and anterior.count() > 0:
                    self.coleccion = anterior
                    return {"archivos": len(set((m or {}).get("archivo", "") for m in anterior.get(include=["metadatas"])["metadatas"])), "fragmentos": anterior.count()}
            return self._reconstruir(referencia)

    def _reconstruir(self, referencia: Path) -> dict[str, int]:
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

        if not documentos:
            raise ValueError("No hay fragmentos legibles; se conserva el índice anterior.")
        embeddings = self.modelo.encode(documentos, normalize_embeddings=True).tolist()
        nombre = f"{COLLECTION_NAME}_{uuid4().hex}"
        candidata = self.cliente.create_collection(name=nombre, metadata={"hnsw:space": "cosine"})
        temporal = referencia.with_name(f"{nombre}.tmp")
        try:
            candidata.add(ids=ids, documents=documentos, metadatas=metadatos, embeddings=embeddings)
            if candidata.count() != len(documentos):
                raise RuntimeError("La colección nueva está incompleta.")
            # Verifica también que se puede consultar antes de publicarla.
            candidata.query(query_embeddings=embeddings[:1], n_results=1, include=["documents"])
            resumen = {"archivos": len(archivos), "fragmentos": len(documentos)}
            temporal.write_text(json.dumps({"coleccion": nombre, "resumen": resumen}), encoding="utf-8")
            os.replace(temporal, referencia)
        except Exception:
            temporal.unlink(missing_ok=True)
            try:
                self.cliente.delete_collection(nombre)
            except Exception:
                logger.warning("No se pudo limpiar una colección candidata.")
            raise
        self.coleccion = candidata

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

    def buscar_con_imagen(self, consulta: str, maximo: int = 8) -> list[dict[str, str | float]]:
        """Recupera solo fichas relevantes al texto y contexto confirmado."""
        # La captura no proporciona una puntuación semántica local. No inventar distancia 0.
        return self.buscar(consulta)[:maximo]



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

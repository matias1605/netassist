"""Persistencia mínima de casos en SQLite (una instancia local; sin usuarios hasta la fase 5).

Separada de ChromaDB, que guarda solo conocimiento. El esquema se versiona con
`PRAGMA user_version` y se migra al abrir la base.
"""
import json
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .generador import formatear_propuesta
from .seguridad import MENSAJE_DATOS_SENSIBLES, contiene_datos_sensibles

_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_SALIDA = 8000

MIGRACIONES = [
    """
    CREATE TABLE casos (
        id TEXT PRIMARY KEY, nombre TEXT NOT NULL, tipo TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'borrador', creado TEXT NOT NULL, actualizado TEXT NOT NULL);
    CREATE TABLE equipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id TEXT NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
        alias TEXT NOT NULL, modelo TEXT NOT NULL, ios TEXT NOT NULL);
    CREATE TABLE conexiones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id TEXT NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
        posicion INTEGER NOT NULL, vlan_id TEXT NOT NULL, vlan_nombre TEXT NOT NULL,
        puerto TEXT NOT NULL, host TEXT NOT NULL);
    CREATE TABLE requisitos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id TEXT NOT NULL REFERENCES casos(id) ON DELETE CASCADE, texto TEXT NOT NULL);
    CREATE TABLE propuestas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id TEXT NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
        contenido TEXT NOT NULL, explicacion TEXT NOT NULL DEFAULT '',
        validacion TEXT NOT NULL, comprobacion TEXT NOT NULL DEFAULT 'no_realizada',
        salida_laboratorio TEXT NOT NULL DEFAULT '', creada TEXT NOT NULL);
    CREATE INDEX idx_propuestas_caso ON propuestas(caso_id);
    """,
]


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CasoNoEncontrado(LookupError):
    pass


class AlmacenCasos:
    def __init__(self, ruta: Path | str) -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conectar()) as con, con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            for numero in range(version, len(MIGRACIONES)):
                con.executescript("BEGIN;" + MIGRACIONES[numero] + f"PRAGMA user_version = {numero + 1};COMMIT;")
            con.execute("PRAGMA journal_mode=WAL")

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @staticmethod
    def _validar_id(caso_id: str) -> str:
        if not isinstance(caso_id, str) or not _ID.match(caso_id):
            raise CasoNoEncontrado("Caso no encontrado.")
        return caso_id

    def guardar_caso(self, datos: dict, caso_id: str | None = None) -> str:
        """Crea o reemplaza los datos de un caso. `datos` es TareaLaboratorio.model_dump()."""
        if contiene_datos_sensibles(json.dumps(datos, ensure_ascii=False)):
            raise ValueError(MENSAJE_DATOS_SENSIBLES)
        ahora = _ahora()
        with closing(self._conectar()) as con, con:
            if caso_id is None:
                caso_id = uuid.uuid4().hex
                con.execute("INSERT INTO casos(id, nombre, tipo, creado, actualizado) VALUES (?,?,?,?,?)",
                            (caso_id, datos["nombre"], datos["tipo"], ahora, ahora))
            else:
                self._validar_id(caso_id)
                if not con.execute("SELECT 1 FROM casos WHERE id=?", (caso_id,)).fetchone():
                    raise CasoNoEncontrado("Caso no encontrado.")
                con.execute("UPDATE casos SET nombre=?, tipo=?, estado='borrador', actualizado=? WHERE id=?",
                            (datos["nombre"], datos["tipo"], ahora, caso_id))
                for tabla in ("equipos", "conexiones", "requisitos"):
                    con.execute(f"DELETE FROM {tabla} WHERE caso_id=?", (caso_id,))
            equipo = datos["equipo"]
            con.execute("INSERT INTO equipos(caso_id, alias, modelo, ios) VALUES (?,?,?,?)",
                        (caso_id, equipo["alias"], equipo["modelo"], equipo["ios"]))
            con.executemany("INSERT INTO conexiones(caso_id, posicion, vlan_id, vlan_nombre, puerto, host) VALUES (?,?,?,?,?,?)",
                            [(caso_id, i, v["id"], v["nombre"], v["puerto"], v["host"]) for i, v in enumerate(datos["vlans"])])
            con.execute("INSERT INTO requisitos(caso_id, texto) VALUES (?,?)", (caso_id, datos["objetivo"]))
        return caso_id

    def guardar_propuesta(self, caso_id: str, propuesta: dict, explicacion: str = "") -> int:
        self._validar_id(caso_id)
        with closing(self._conectar()) as con, con:
            if not con.execute("SELECT 1 FROM casos WHERE id=?", (caso_id,)).fetchone():
                raise CasoNoEncontrado("Caso no encontrado.")
            cursor = con.execute(
                "INSERT INTO propuestas(caso_id, contenido, explicacion, validacion, creada) VALUES (?,?,?,?,?)",
                (caso_id, json.dumps(propuesta, ensure_ascii=False), explicacion, propuesta["estado_validacion"], _ahora()))
            con.execute("UPDATE casos SET estado='propuesta', actualizado=? WHERE id=?", (_ahora(), caso_id))
            return cursor.lastrowid

    def registrar_comprobacion(self, caso_id: str, resultado: str, salida: str) -> None:
        """Anota el resultado manual en simulador/laboratorio sobre la última propuesta."""
        if resultado not in {"correcta", "fallida"}:
            raise ValueError("El resultado debe ser «correcta» o «fallida».")
        if not salida.strip() or len(salida) > MAX_SALIDA:
            raise ValueError(f"Adjunta las salidas de verificación (hasta {MAX_SALIDA} caracteres).")
        if contiene_datos_sensibles(salida):
            raise ValueError(MENSAJE_DATOS_SENSIBLES)
        self._validar_id(caso_id)
        with closing(self._conectar()) as con, con:
            if not con.execute("SELECT 1 FROM casos WHERE id=?", (caso_id,)).fetchone():
                raise CasoNoEncontrado("Caso no encontrado.")
            fila = con.execute("SELECT id FROM propuestas WHERE caso_id=? ORDER BY id DESC LIMIT 1", (caso_id,)).fetchone()
            if not fila:
                raise ValueError("El caso no tiene una propuesta para comprobar.")
            con.execute("UPDATE propuestas SET comprobacion=?, salida_laboratorio=? WHERE id=?", (resultado, salida, fila["id"]))
            con.execute("UPDATE casos SET estado=?, actualizado=? WHERE id=?",
                        ("comprobado" if resultado == "correcta" else "comprobacion_fallida", _ahora(), caso_id))

    def listar_casos(self) -> list[dict]:
        with closing(self._conectar()) as con:
            filas = con.execute("SELECT id, nombre, tipo, estado, actualizado FROM casos ORDER BY actualizado DESC, rowid DESC LIMIT 100").fetchall()
        return [dict(f) for f in filas]

    def obtener_caso(self, caso_id: str) -> dict:
        self._validar_id(caso_id)
        with closing(self._conectar()) as con:
            caso = con.execute("SELECT * FROM casos WHERE id=?", (caso_id,)).fetchone()
            if not caso:
                raise CasoNoEncontrado("Caso no encontrado.")
            equipo = con.execute("SELECT alias, modelo, ios FROM equipos WHERE caso_id=?", (caso_id,)).fetchone()
            vlans = con.execute("SELECT vlan_id AS id, vlan_nombre AS nombre, puerto, host FROM conexiones WHERE caso_id=? ORDER BY posicion", (caso_id,)).fetchall()
            texto = con.execute("SELECT texto FROM requisitos WHERE caso_id=?", (caso_id,)).fetchone()
            propuesta = con.execute("SELECT * FROM propuestas WHERE caso_id=? ORDER BY id DESC LIMIT 1", (caso_id,)).fetchone()
        resultado = {
            "caso_id": caso["id"], "estado": caso["estado"], "creado": caso["creado"], "actualizado": caso["actualizado"],
            "tarea": {"tipo": caso["tipo"], "nombre": caso["nombre"], "equipo": dict(equipo),
                      "vlans": [dict(v) for v in vlans], "objetivo": texto["texto"] if texto else ""},
            "propuesta": None,
        }
        if propuesta:
            resultado["propuesta"] = {
                **json.loads(propuesta["contenido"]), "explicacion": propuesta["explicacion"],
                "comprobacion_laboratorio": propuesta["comprobacion"], "salida_laboratorio": propuesta["salida_laboratorio"],
                "creada": propuesta["creada"],
            }
            resultado["propuesta"]["texto"] = formatear_propuesta(resultado["propuesta"], propuesta["explicacion"])
        return resultado

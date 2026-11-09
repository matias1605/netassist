"""Persistencia mínima de casos en SQLite (una instancia local; sin usuarios hasta la fase 5).

Separada de ChromaDB, que guarda solo conocimiento. El esquema se versiona con
`PRAGMA user_version` y se migra al abrir la base.
"""
import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .diagnostico import analizar_bloque, dividir_bloques, esperado_desde_tarea, estado_paso, formatear_diagnostico, pasos_base, resumir
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
    # Fase 4: pasos de diagnóstico, evidencias pegadas y observaciones que las referencian.
    """
    CREATE TABLE pasos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id TEXT NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
        clave TEXT NOT NULL, orden INTEGER NOT NULL, titulo TEXT NOT NULL, comando TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente', evidencia_id INTEGER,
        UNIQUE(caso_id, clave));
    CREATE TABLE evidencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id TEXT NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
        clave_paso TEXT NOT NULL, tipo TEXT NOT NULL, salida TEXT NOT NULL, resultado TEXT NOT NULL,
        vigente INTEGER NOT NULL DEFAULT 1, creada TEXT NOT NULL);
    CREATE INDEX idx_evidencias_caso ON evidencias(caso_id);
    CREATE TABLE observaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evidencia_id INTEGER NOT NULL REFERENCES evidencias(id) ON DELETE CASCADE,
        severidad TEXT NOT NULL, texto TEXT NOT NULL, correccion TEXT NOT NULL DEFAULT '[]');
    """,
    # Fase 5: propietario (huella de la clave de usuario; NULL en casos anteriores) y archivado.
    """
    ALTER TABLE casos ADD COLUMN propietario TEXT;
    ALTER TABLE casos ADD COLUMN archivado INTEGER NOT NULL DEFAULT 0;
    CREATE INDEX idx_casos_propietario ON casos(propietario);
    """,
]


_USUARIO = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def validar_usuario(usuario: str | None) -> str | None:
    """La clave de usuario es un secreto opaco generado por el cliente; no es una autenticación."""
    if usuario is not None and not _USUARIO.match(usuario):
        raise ValueError("Clave de usuario no válida: usa entre 16 y 64 letras, números, guion o guion bajo.")
    return usuario


def _hash_usuario(usuario: str | None) -> str | None:
    return None if validar_usuario(usuario) is None else hashlib.sha256(usuario.encode("utf-8")).hexdigest()


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

    def _acceso(self, con: sqlite3.Connection, caso_id: str, usuario: str | None) -> None:
        """Un caso ajeno es indistinguible de uno inexistente. Los casos anteriores a la fase 5 no tienen propietario."""
        fila = con.execute("SELECT propietario FROM casos WHERE id=?", (caso_id,)).fetchone()
        if fila is None or (fila["propietario"] is not None and fila["propietario"] != _hash_usuario(usuario)):
            raise CasoNoEncontrado("Caso no encontrado.")

    def archivar_caso(self, caso_id: str, archivado: bool, usuario: str | None = None) -> None:
        self._validar_id(caso_id)
        with closing(self._conectar()) as con, con:
            self._acceso(con, caso_id, usuario)
            con.execute("UPDATE casos SET archivado=?, actualizado=? WHERE id=?", (int(archivado), _ahora(), caso_id))

    @staticmethod
    def _validar_id(caso_id: str) -> str:
        if not isinstance(caso_id, str) or not _ID.match(caso_id):
            raise CasoNoEncontrado("Caso no encontrado.")
        return caso_id

    def guardar_caso(self, datos: dict, caso_id: str | None = None, usuario: str | None = None) -> str:
        """Crea o reemplaza los datos de un caso. `datos` es TareaLaboratorio.model_dump()."""
        if contiene_datos_sensibles(json.dumps(datos, ensure_ascii=False)):
            raise ValueError(MENSAJE_DATOS_SENSIBLES)
        ahora = _ahora()
        with closing(self._conectar()) as con, con:
            antes = None
            if caso_id is None:
                caso_id = uuid.uuid4().hex
                con.execute("INSERT INTO casos(id, nombre, tipo, creado, actualizado, propietario) VALUES (?,?,?,?,?,?)",
                            (caso_id, datos["nombre"], datos["tipo"], ahora, ahora, _hash_usuario(usuario)))
            else:
                self._validar_id(caso_id)
                self._acceso(con, caso_id, usuario)
                antes = self._firma_diagnostico(con, caso_id)
                # Un caso anterior sin propietario pasa a ser de quien lo regenera.
                con.execute("UPDATE casos SET nombre=?, tipo=?, estado='borrador', actualizado=?, propietario=COALESCE(propietario, ?) WHERE id=?",
                            (datos["nombre"], datos["tipo"], ahora, _hash_usuario(usuario), caso_id))
                for tabla in ("equipos", "conexiones", "requisitos"):
                    con.execute(f"DELETE FROM {tabla} WHERE caso_id=?", (caso_id,))
            equipo = datos["equipo"]
            con.execute("INSERT INTO equipos(caso_id, alias, modelo, ios) VALUES (?,?,?,?)",
                        (caso_id, equipo["alias"], equipo["modelo"], equipo["ios"]))
            con.executemany("INSERT INTO conexiones(caso_id, posicion, vlan_id, vlan_nombre, puerto, host) VALUES (?,?,?,?,?,?)",
                            [(caso_id, i, v["id"], v["nombre"], v["puerto"], v["host"]) for i, v in enumerate(datos["vlans"])])
            con.execute("INSERT INTO requisitos(caso_id, texto) VALUES (?,?)", (caso_id, datos["objetivo"]))
            if antes is not None and antes != self._firma_diagnostico(con, caso_id):
                # Los datos declarados cambiaron: las evidencias previas dejan de ser vigentes y los pasos se rehacen.
                con.execute("UPDATE evidencias SET vigente=0 WHERE caso_id=?", (caso_id,))
                con.execute("DELETE FROM pasos WHERE caso_id=?", (caso_id,))
        return caso_id

    @staticmethod
    def _firma_diagnostico(con: sqlite3.Connection, caso_id: str) -> list | None:
        equipo = con.execute("SELECT alias FROM equipos WHERE caso_id=?", (caso_id,)).fetchone()
        filas = con.execute("SELECT vlan_id, vlan_nombre, puerto, host FROM conexiones WHERE caso_id=? ORDER BY posicion", (caso_id,)).fetchall()
        return None if equipo is None else [equipo["alias"], [tuple(f) for f in filas]]

    def guardar_propuesta(self, caso_id: str, propuesta: dict, explicacion: str = "", usuario: str | None = None) -> int:
        self._validar_id(caso_id)
        with closing(self._conectar()) as con, con:
            self._acceso(con, caso_id, usuario)
            cursor = con.execute(
                "INSERT INTO propuestas(caso_id, contenido, explicacion, validacion, creada) VALUES (?,?,?,?,?)",
                (caso_id, json.dumps(propuesta, ensure_ascii=False), explicacion, propuesta["estado_validacion"], _ahora()))
            con.execute("UPDATE casos SET estado='propuesta', actualizado=? WHERE id=?", (_ahora(), caso_id))
            return cursor.lastrowid

    def registrar_comprobacion(self, caso_id: str, resultado: str, salida: str, usuario: str | None = None) -> None:
        """Anota el resultado manual en simulador/laboratorio sobre la última propuesta."""
        if resultado not in {"correcta", "fallida"}:
            raise ValueError("El resultado debe ser «correcta» o «fallida».")
        if not salida.strip() or len(salida) > MAX_SALIDA:
            raise ValueError(f"Adjunta las salidas de verificación (hasta {MAX_SALIDA} caracteres).")
        if contiene_datos_sensibles(salida):
            raise ValueError(MENSAJE_DATOS_SENSIBLES)
        self._validar_id(caso_id)
        with closing(self._conectar()) as con, con:
            self._acceso(con, caso_id, usuario)
            fila = con.execute("SELECT id FROM propuestas WHERE caso_id=? ORDER BY id DESC LIMIT 1", (caso_id,)).fetchone()
            if not fila:
                raise ValueError("El caso no tiene una propuesta para comprobar.")
            con.execute("UPDATE propuestas SET comprobacion=?, salida_laboratorio=? WHERE id=?", (resultado, salida, fila["id"]))
            con.execute("UPDATE casos SET estado=?, actualizado=? WHERE id=?",
                        ("comprobado" if resultado == "correcta" else "comprobacion_fallida", _ahora(), caso_id))

    # ----- Fase 4: diagnóstico con evidencia -----

    def _esperado(self, con: sqlite3.Connection, caso_id: str) -> list[dict]:
        filas = con.execute("SELECT vlan_id AS id, vlan_nombre AS nombre, puerto, host FROM conexiones WHERE caso_id=? ORDER BY posicion", (caso_id,)).fetchall()
        return esperado_desde_tarea({"vlans": [dict(f) for f in filas]})

    def _asegurar_pasos(self, con: sqlite3.Connection, caso_id: str) -> None:
        if con.execute("SELECT 1 FROM pasos WHERE caso_id=?", (caso_id,)).fetchone():
            return
        for orden, paso in enumerate(pasos_base(self._esperado(con, caso_id))):
            con.execute("INSERT INTO pasos(caso_id, clave, orden, titulo, comando) VALUES (?,?,?,?,?)",
                        (caso_id, paso["clave"], orden, paso["titulo"], paso["comando"]))

    def registrar_evidencia(self, caso_id: str, salida: str, usuario: str | None = None) -> dict:
        """Analiza las salidas pegadas, guarda las que corresponden a un paso y devuelve el diagnóstico.

        Un paso ya completado no se repite y la misma salida no se registra dos veces para un paso.
        Lo omitido se informa en `omitidos` con el motivo."""
        if not salida.strip() or len(salida) > MAX_SALIDA:
            raise ValueError(f"Pega la salida de los comandos de verificación (hasta {MAX_SALIDA} caracteres).")
        if contiene_datos_sensibles(salida):
            raise ValueError(MENSAJE_DATOS_SENSIBLES)
        self._validar_id(caso_id)
        registradas, omitidos = [], []
        with closing(self._conectar()) as con, con:
            self._acceso(con, caso_id, usuario)
            self._asegurar_pasos(con, caso_id)
            esperado = self._esperado(con, caso_id)
            for bloque in dividir_bloques(salida):
                analisis = analizar_bloque(bloque, esperado)
                if analisis["clave"] is None:
                    omitidos.append({"motivo": analisis["observaciones"][0]["texto"], "fragmento": bloque[:80]})
                    continue
                paso = con.execute("SELECT * FROM pasos WHERE caso_id=? AND clave=?", (caso_id, analisis["clave"])).fetchone()
                if paso["estado"] == "completado":
                    omitidos.append({"motivo": f"El paso «{paso['comando']}» ya está completado con la evidencia E{paso['evidencia_id']}; no se repite.", "fragmento": bloque[:80]})
                    continue
                previa = con.execute("SELECT id FROM evidencias WHERE caso_id=? AND clave_paso=? AND vigente=1 AND salida=?", (caso_id, analisis["clave"], bloque)).fetchone()
                if previa:
                    omitidos.append({"motivo": f"Esa salida ya se registró como E{previa['id']}. Aplica la corrección o aclara y pega una salida nueva.", "fragmento": bloque[:80]})
                    continue
                evidencia = con.execute("INSERT INTO evidencias(caso_id, clave_paso, tipo, salida, resultado, creada) VALUES (?,?,?,?,?,?)",
                                        (caso_id, analisis["clave"], analisis["tipo"], bloque, analisis["resultado"], _ahora())).lastrowid
                con.executemany("INSERT INTO observaciones(evidencia_id, severidad, texto, correccion) VALUES (?,?,?,?)",
                                [(evidencia, o["severidad"], o["texto"], json.dumps(o["correccion"], ensure_ascii=False)) for o in analisis["observaciones"]])
                con.execute("UPDATE pasos SET estado=?, evidencia_id=? WHERE id=?", (estado_paso(analisis["resultado"]), evidencia, paso["id"]))
                registradas.append(evidencia)
            diagnostico = self._leer_diagnostico(con, caso_id)
            if registradas:
                nuevo = "diagnostico_coherente" if diagnostico["estado"] == "coherente" else "en_diagnostico"
                con.execute("UPDATE casos SET estado=?, actualizado=? WHERE id=? AND estado<>'comprobado'", (nuevo, _ahora(), caso_id))
        return {**diagnostico, "registradas": registradas, "omitidos": omitidos}

    def _leer_diagnostico(self, con: sqlite3.Connection, caso_id: str) -> dict:
        self._asegurar_pasos(con, caso_id)
        pasos = []
        for fila in con.execute("SELECT * FROM pasos WHERE caso_id=? ORDER BY orden", (caso_id,)).fetchall():
            paso = {"clave": fila["clave"], "titulo": fila["titulo"], "comando": fila["comando"], "estado": fila["estado"], "evidencia": None}
            if fila["evidencia_id"]:
                ev = con.execute("SELECT id, creada, resultado FROM evidencias WHERE id=?", (fila["evidencia_id"],)).fetchone()
                observaciones = [{"severidad": o["severidad"], "texto": o["texto"], "correccion": json.loads(o["correccion"])}
                                 for o in con.execute("SELECT * FROM observaciones WHERE evidencia_id=? ORDER BY id", (ev["id"],)).fetchall()]
                paso["evidencia"] = {"id": ev["id"], "creada": ev["creada"], "resultado": ev["resultado"], "observaciones": observaciones}
            pasos.append(paso)
        diagnostico = {"caso_id": caso_id, "pasos": pasos, **resumir(pasos)}
        diagnostico["texto"] = formatear_diagnostico(diagnostico)
        return diagnostico

    def obtener_diagnostico(self, caso_id: str, fuentes: list[str] | None = None, usuario: str | None = None) -> dict:
        self._validar_id(caso_id)
        with closing(self._conectar()) as con, con:
            self._acceso(con, caso_id, usuario)
            diagnostico = self._leer_diagnostico(con, caso_id)
        if fuentes:
            diagnostico["fuentes"] = fuentes
            diagnostico["texto"] = formatear_diagnostico(diagnostico)
        return diagnostico

    def listar_evidencias(self, caso_id: str, usuario: str | None = None) -> list[dict]:
        """Todas las evidencias del caso, vigentes o no, con sus observaciones, para trazabilidad."""
        self._validar_id(caso_id)
        with closing(self._conectar()) as con:
            self._acceso(con, caso_id, usuario)
            resultado = []
            for ev in con.execute("SELECT * FROM evidencias WHERE caso_id=? ORDER BY id", (caso_id,)).fetchall():
                observaciones = [{"severidad": o["severidad"], "texto": o["texto"]}
                                 for o in con.execute("SELECT severidad, texto FROM observaciones WHERE evidencia_id=? ORDER BY id", (ev["id"],)).fetchall()]
                resultado.append({"id": ev["id"], "paso": ev["clave_paso"], "tipo": ev["tipo"], "salida": ev["salida"], "resultado": ev["resultado"],
                                  "vigente": bool(ev["vigente"]), "creada": ev["creada"], "observaciones": observaciones})
        return resultado

    def listar_casos(self, usuario: str | None = None, estado: str | None = None, archivados: bool = False) -> list[dict]:
        """Casos propios (y los anteriores sin propietario), más recientes primero. Los archivados se piden aparte."""
        huella = _hash_usuario(usuario)
        condiciones, parametros = ["(propietario IS NULL OR propietario = ?)"], [huella]
        if estado:
            condiciones.append("estado = ?")
            parametros.append(estado)
        if not archivados:
            condiciones.append("archivado = 0")
        with closing(self._conectar()) as con:
            filas = con.execute(
                "SELECT id, nombre, tipo, estado, archivado, creado, actualizado, "
                "(SELECT COUNT(*) FROM evidencias e WHERE e.caso_id = casos.id AND e.vigente = 1) AS evidencias, "
                "(SELECT comprobacion FROM propuestas p WHERE p.caso_id = casos.id ORDER BY p.id DESC LIMIT 1) AS comprobacion "
                "FROM casos WHERE " + " AND ".join(condiciones) + " ORDER BY actualizado DESC, rowid DESC LIMIT 100", parametros).fetchall()
        return [{**dict(f), "archivado": bool(f["archivado"])} for f in filas]

    def obtener_caso(self, caso_id: str, usuario: str | None = None) -> dict:
        self._validar_id(caso_id)
        with closing(self._conectar()) as con:
            self._acceso(con, caso_id, usuario)
            caso = con.execute("SELECT * FROM casos WHERE id=?", (caso_id,)).fetchone()
            equipo = con.execute("SELECT alias, modelo, ios FROM equipos WHERE caso_id=?", (caso_id,)).fetchone()
            vlans = con.execute("SELECT vlan_id AS id, vlan_nombre AS nombre, puerto, host FROM conexiones WHERE caso_id=? ORDER BY posicion", (caso_id,)).fetchall()
            texto = con.execute("SELECT texto FROM requisitos WHERE caso_id=?", (caso_id,)).fetchone()
            propuesta = con.execute("SELECT * FROM propuestas WHERE caso_id=? ORDER BY id DESC LIMIT 1", (caso_id,)).fetchone()
        resultado = {
            "caso_id": caso["id"], "estado": caso["estado"], "archivado": bool(caso["archivado"]), "creado": caso["creado"], "actualizado": caso["actualizado"],
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

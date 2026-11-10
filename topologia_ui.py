"""Presentación de las topologías Mermaid que escribe el modelo.

El modelo decide QUÉ se dibuja (equipos, enlaces, etiquetas). Aquí solo se decide CÓMO se ve:
cada equipo recibe un color e icono según su tipo, los enlaces con falla se marcan en rojo y
se calcula la altura del diagrama para que no sobre espacio. Si algo no se reconoce, se deja
tal cual: el diagrama original siempre se sigue dibujando.
"""

import re

# Tipo de equipo -> (icono Font Awesome, nombre en la leyenda, estilo Mermaid).
TIPOS = {
    "router": ("fa:fa-shuffle", "Router", "fill:#0f1a2b,stroke:#14304a,color:#ffffff"),
    "switch": ("fa:fa-network-wired", "Switch", "fill:#14958a,stroke:#0f7a71,color:#ffffff"),
    "servidor": ("fa:fa-server", "Servidor", "fill:#eaf2ff,stroke:#2a7fd6,color:#123a66"),
    "pc": ("fa:fa-desktop", "PC", "fill:#ffffff,stroke:#9fb3c8,color:#1d2b3b"),
    "nube": ("fa:fa-cloud", "Red externa", "fill:#f4f8fa,stroke:#9fb3c8,color:#4b5d70"),
}
_PATRONES_TIPO = [
    ("router", re.compile(r"^r\d|router|rtr|gateway|\bisr", re.I)),
    ("switch", re.compile(r"^s\d|^sw|switch|catalyst|2960|3560|3650|9200", re.I)),
    ("servidor", re.compile(r"srv|server|servidor|dns|dhcp|web", re.I)),
    ("nube", re.compile(r"internet|isp|nube|cloud|wan", re.I)),
]
ALTURA_BASE = 70
ALTURA_NIVEL = 105
_FALLA = re.compile(r"down|falla|caid|error|shutdown|err-disabled|sin conexi", re.I)
_NODO = re.compile(r'\b([A-Za-z_][\w-]*)\s*\[\s*"?([^"\]]*)"?\s*\]')
_ENLACE = re.compile(r"(--|==|-\.)")


def _tipo(identificador: str, etiqueta: str) -> str:
    # Primero por el identificador (SW1, R1, PC2) y luego por la etiqueta (modelo, nombre).
    for texto in (identificador, etiqueta):
        for tipo, patron in _PATRONES_TIPO:
            if patron.search(texto):
                return tipo
    return "pc"


def _limpiar_enlace(linea: str) -> list[str]:
    """Identificadores de los extremos de una línea de enlace (sin etiquetas ni formas)."""
    sin_texto = re.sub(r'"[^"]*"|\|[^|]*\||\[[^\]]*\]|\([^)]*\)|\{[^}]*\}', " ", linea)
    sin_texto = re.sub(r"[-=.>ox<]{2,}", " ", sin_texto)
    return re.findall(r"\b[A-Za-z_][\w-]*\b", sin_texto)


def preparar_topologia(fuente: str) -> tuple[str, int, list[str]]:
    """Devuelve (código Mermaid con estilo, altura en px, tipos presentes para la leyenda)."""
    # La ventana del chat es angosta: los diagramas horizontales se dibujan en vertical.
    fuente = re.sub(r"^\s*(graph|flowchart)\s+(LR|RL)\b", r"\1 TD", fuente.strip(), flags=re.I)
    lineas = fuente.splitlines()
    if not lineas or not re.match(r"\s*(graph|flowchart)\b", lineas[0], re.I):
        return fuente, 320, []  # no es un diagrama de flujo: se dibuja sin tocar

    etiquetas: dict[str, str] = {}
    for linea in lineas[1:]:
        for identificador, etiqueta in _NODO.findall(linea):
            etiquetas.setdefault(identificador, etiqueta.strip())

    enlaces: list[tuple[str, str]] = []
    enlaces_con_falla: list[int] = []
    nodos: list[str] = list(etiquetas)
    for linea in lineas[1:]:
        if not _ENLACE.search(linea) or linea.strip().startswith(("classDef", "class ", "style", "linkStyle", "%%")):
            continue
        extremos = _limpiar_enlace(linea)
        if len(extremos) >= 2:
            enlaces.append((extremos[0], extremos[-1]))
            if _FALLA.search(linea):
                enlaces_con_falla.append(len(enlaces) - 1)
            for nodo in (extremos[0], extremos[-1]):
                if nodo not in nodos:
                    nodos.append(nodo)

    tipos = {nodo: _tipo(nodo, etiquetas.get(nodo, "")) for nodo in nodos}

    def con_icono(coincidencia: re.Match) -> str:
        identificador, etiqueta = coincidencia.group(1), coincidencia.group(2).strip()
        if identificador not in tipos or etiqueta.startswith("fa:"):
            return coincidencia.group(0)
        return f'{identificador}["{TIPOS[tipos[identificador]][0]} {etiqueta}"]'

    cuerpo = [_NODO.sub(con_icono, linea) for linea in lineas[1:]]
    # Equipos que solo aparecen en enlaces: se les da etiqueta con icono.
    sin_definir = [n for n in nodos if n not in etiquetas]
    extra = [f'{n}["{TIPOS[tipos[n]][0]} {n}"]' for n in sin_definir]
    estilos = [f"classDef {tipo} {estilo}" for tipo, (_, _, estilo) in TIPOS.items()]
    for tipo in TIPOS:
        miembros = [n for n in nodos if tipos[n] == tipo]
        if miembros:
            estilos.append(f"class {','.join(miembros)} {tipo}")
    if enlaces:
        estilos.append("linkStyle default stroke:#14958a,stroke-width:2px")
    for indice in enlaces_con_falla:
        estilos.append(f"linkStyle {indice} stroke:#e5484d,stroke-width:2.5px,stroke-dasharray:6 4")

    codigo = "\n".join([lineas[0], *extra, *cuerpo, *estilos])
    presentes = [tipo for tipo in TIPOS if tipo in tipos.values()]
    return codigo, _altura(nodos, enlaces), presentes


def _altura(nodos: list[str], enlaces: list[tuple[str, str]]) -> int:
    """Altura según el número de niveles del diagrama vertical (no según el número de enlaces)."""
    hijos: dict[str, list[str]] = {n: [] for n in nodos}
    entrantes = {n: 0 for n in nodos}
    for origen, destino in enlaces:
        hijos.setdefault(origen, []).append(destino)
        entrantes[destino] = entrantes.get(destino, 0) + 1
    nivel = {n: 0 for n in nodos if entrantes.get(n, 0) == 0} or {nodos[0]: 0} if nodos else {}
    pendientes = list(nivel)
    pasos = 0
    while pendientes and pasos < 500:  # tope ante ciclos
        pasos += 1
        actual = pendientes.pop(0)
        for hijo in hijos.get(actual, []):
            if nivel.get(hijo, -1) < nivel[actual] + 1 and nivel[actual] + 1 < len(nodos):
                nivel[hijo] = nivel[actual] + 1
                pendientes.append(hijo)
    niveles = (max(nivel.values()) + 1) if nivel else 1
    # Cada nivel: caja (~45 px) + separación entre niveles (60 px); base: marco y leyenda.
    return min(ALTURA_BASE + ALTURA_NIVEL * niveles, 900)


def leyenda(presentes: list[str]) -> str:
    """HTML de la leyenda con los tipos de equipo que aparecen en el diagrama."""
    chips = "".join(
        f'<span class="ley ley-{tipo}"><i class="fa {TIPOS[tipo][0][3:]}"></i>{TIPOS[tipo][1]}</span>'
        for tipo in presentes
    )
    return chips

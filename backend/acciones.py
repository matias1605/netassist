"""Borradores compartidos por ambas interfaces; no ejecutan cambios en equipos."""

import json

from .config import ROOT_DIR


def obtener_acciones() -> list[dict[str, str]]:
    """Carga el escenario de laboratorio y prepara solicitudes editables para la IA."""
    datos = json.loads((ROOT_DIR / "docs" / "datos_prueba_vlan.json").read_text(encoding="utf-8"))
    contexto = json.dumps(datos, ensure_ascii=False, indent=2)
    return [
        {
            "id": "configuracion",
            "titulo": "Generar configuración",
            "descripcion": "VLAN y puertos de acceso con datos de prueba.",
            "prompt": (
                "Genera una propuesta de configuración Cisco IOS según estos datos de prueba. "
                "Responde de forma concisa y precisa: un bloque de comandos por equipo, "
                "verificaciones y una advertencia breve. Usa las fichas disponibles; "
                "si falta un dato obligatorio, pregunta antes de generar cambios. "
                "No afirmes que la propuesta fue ejecutada o validada en laboratorio.\n\n" + contexto
            ),
        },
        {
            "id": "topologia",
            "titulo": "Generar topología",
            "descripcion": "Diagrama de SW1 y sus dos PC de laboratorio.",
            "prompt": (
                "Genera únicamente una topología Mermaid (graph LR) y una explicación de "
                "máximo dos frases según estos datos de prueba. Muestra SW1, ambas PC y "
                "los enlaces etiquetados con puerto y VLAN. No inventes equipos, IP, "
                "conectividad entre VLAN ni fallas. No incluyas comandos de configuración. "
                "Aclara que es un diseño propuesto, pendiente de verificación.\n\n" + contexto
            ),
        },
    ]

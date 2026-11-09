# Verificación de la fase 3

Fecha: 9 de noviembre de 2026. Estado: implementada y probada localmente; **comprobación en simulador pendiente**.

## Resultados

- **57 pruebas automatizadas: OK** (`pruebas/resultado_fase3.txt`): 31 previas, 26 nuevas en `test_fase3.py`.
- Chrome con API real: VLAN 4095 rechazada con generación bloqueada; ejemplo generado y guardado; caso reabierto con datos, propuesta y diagrama. Sin proveedores de IA disponibles se conservó la propuesta determinista.
- Compilación Python, sintaxis de `laboratorio.js` y `git diff --check`: sin errores.

## Cobertura

| Área | Evidencia |
|---|---|
| Validadores | VLAN fuera de rango/reservadas/no numéricas, puertos inválidos y duplicados, nombres, hosts, VLAN con dos nombres, advertencia de modelo. |
| Generador | Comandos por plantilla, VLAN sin repetir, abreviaturas normalizadas, topología desde los datos, identificadores Mermaid seguros, sin IP inventadas. |
| Persistencia | Guardar, reabrir con instancia nueva, actualizar el mismo caso, rechazos sin escritura, identificadores inválidos, datos sensibles, migración y claves foráneas. |
| API y UI | Flujo generar → listar → reabrir → comprobar; 404/422; Streamlit: bloqueo por reglas y reapertura en sesión nueva. |
| Degradación | Fallo de RAG (sin fuentes) y proveedores caídos (propuesta sin explicación) no impiden la propuesta. |

## Reproducción

```powershell
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
```

## Comprobación manual pendiente (caso de referencia)

1. Generar el ejemplo (SW1, VLAN 10 y 20) y copiar los comandos.
2. Aplicarlos en Packet Tracer sobre un 2960 y ejecutar las verificaciones propuestas.
3. Registrar las salidas: `POST /casos/{id}/comprobacion` con `{"resultado": "correcta" | "fallida", "salida": "..."}`.
4. Reabrir el caso y confirmar que propuesta y estado se conservan.

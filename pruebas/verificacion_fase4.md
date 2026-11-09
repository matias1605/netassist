# Verificación de la fase 4

Fecha: 9 de noviembre de 2026. Estado: implementada y probada localmente; **contraste con salidas reales de simulador pendiente**.

## Resultados

- **86 pruebas automatizadas: OK** (`pruebas/resultado_fase4.txt`): 57 previas y 29 nuevas en `test_fase4.py`.
- Chrome con API real y base temporal: caso generado, salida de `show vlan brief` con Gi0/2 en la VLAN 1 → hallazgo `[E1]`, corrección propuesta no ejecutada, dos pasos pendientes y fuente `cisco_ios_basico.txt`. Sin errores de consola.
- Compilación Python y sintaxis de `laboratorio.js`: sin errores.

## Cobertura

| Área | Evidencia |
|---|---|
| Analizador | Tabla coherente, puerto en otra VLAN, VLAN ausente o renombrada, continuación de puertos, tabla vacía, switchport correcto/dinámico/VLAN distinta/deshabilitado/enlace caído, salida incompleta, puerto no declarado, texto no reconocido, división de varias salidas. |
| Evidencia | Todo hallazgo referencia su `evidencia_id`; el texto muestra `E<n>`. |
| Continuidad | Paso completado no se repite; salida idéntica no se duplica; corrección → nueva salida cierra el hallazgo y conserva el historial; persistencia entre instancias; datos del caso modificados invalidan evidencias. |
| Ambigüedad | Pide aclaración y no cierra el paso. |
| Seguridad | Datos sensibles, vacío y exceso de tamaño rechazados sin escribir; identificador inválido → 404. |
| Datos | Migración desde esquema de fase 3 sin perder casos; borrado en cascada. |
| API y UI | Flujo completo vía API; RAG caído sigue diagnosticando; Streamlit con AppTest (hallazgo y repetición). |

## Reproducción

```powershell
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
```

## Comprobación manual pendiente

1. En Packet Tracer, aplicar la propuesta del ejemplo y ejecutar `show vlan brief` y `show interfaces <puerto> switchport` para ambos puertos.
2. Pegar las salidas reales en «4. Diagnóstico» y confirmar estado `coherente` (o ajustar el analizador si el formato difiere).
3. Provocar un fallo (p. ej. mover un puerto a la VLAN 1) y confirmar hallazgo, corrección y cierre tras repetir la salida.

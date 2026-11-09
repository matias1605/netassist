# Verificación de la fase 6 — demostración y evaluación

Fecha: 9 de noviembre de 2026. Estado: implementada y probada localmente. **No hay mediciones con proveedores reales ni simulador en esta fase.**

## Qué se evalúa y qué no

La evaluación ejecuta la API real (validadores, generador, analizador, SQLite, informe y política de respaldo) con **dobles** de Gemini, Groq y del índice. Mide el comportamiento determinista del producto; no mide la calidad del texto de un modelo ni la latencia de la red. Las cifras de latencia de abajo son locales y no deben compararse con las del chat histórico.

## Reproducción

```powershell
$env:PYTHONIOENCODING = "utf-8"
.venv/Scripts/python.exe pruebas/evaluacion/escenarios.py      # escribe pruebas/resultado_fase6.md y .json
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
```

## Resultados

- **28 de 28 escenarios superados** (`pruebas/resultado_fase6.md`, detalle y milisegundos por escenario; `pruebas/resultado_fase6.json`, métricas).
- Suite completa: ver `pruebas/resultado_fase6.txt` (102 previas + 7 nuevas en `test_fase6.py`).

| Área prevista en el plan | Escenarios | Cubre |
|---|---|---|
| Configuración | CF1–CF7 | Datos completos, modelo ausente, VLAN inválida, puerto repetido, objetivo fuera de alcance, objetivo que excluye temas, modelo no 2960 |
| Topología | TP1–TP4 | Dos PC y un switch, datos incompletos, ausencia de IP, enlace no declarado |
| Continuidad | CT1–CT5 | Reabrir caso, no duplicar salidas, hallazgo → corrección → resolución, ambigüedad, informe |
| Proveedores | PV1–PV5 | Primario caído, respuesta vacía, ambos caídos, solo respaldo con captura, chat sin proveedores |
| Conocimiento | CN1–CN4 | Fuente válida, búsqueda caída, índice caído (503), diagnóstico sin índice |
| Seguridad | SG1–SG3 | Datos sensibles en chat y formulario, aislamiento entre usuarios |
| Interfaz | — | No automatizada aquí: ver los smoke de Chrome de las fases 2–5 y el guion de demostración |

## Hallazgo corregido durante la evaluación

El caso «objetivo fuera del corpus» (CF5) reveló un hueco: con el objetivo *«Configurar OSPF entre dos routers»* la propuesta se generaba como VLAN sin ninguna advertencia, y parecía atender lo pedido. Ahora `validar_tarea` añade la advertencia *«El objetivo menciona OSPF, fuera del alcance…»* para OSPF, EIGRP, BGP, RIP, VPN/IPsec, NAT, ACL, DHCP, STP, HSRP, EtherChannel, trunk e inter-VLAN, salvo que el objetivo los niegue (*«sin trunk»*). Sigue siendo una lista heurística: es una advertencia, no un bloqueo.

## Comparación con el chat inicial

| Aspecto | Chat inicial (rondas 1–2) | Espacio de laboratorio |
|---|---|---|
| Entrada | Texto libre | Formulario con revisión y confirmación |
| VLAN 4095, puerto repetido, modelo ausente | Dependía del modelo de lenguaje | Rechazo o petición determinista, sin llamar a la IA (CF2–CF4) |
| Comandos | Generados por el modelo; sin validador posterior | Plantilla determinista; el modelo solo explica (CF1, PV3) |
| Fallo de proveedores | Aviso fijo, sin contenido útil | Propuesta y caso conservados sin explicación (PV3) |
| Continuidad | Historial de la conversación | Casos persistentes, evidencias y estado de diagnóstico (CT1–CT4) |
| Resumen exportable | No | Informe Markdown (CT5) |
| Datos entre personas | No aplicaba | Aislamiento por clave opaca (SG3) |
| Corrección en preguntas abiertas | 20/20 en ronda 2, 0 alucinaciones, 3,9 s de media (proveedores reales) | No comparable: el espacio de laboratorio solo cubre VLAN y puertos de acceso |

La comparación es **de capacidades**, no de precisión de la IA: no se ejecutó el mismo conjunto de preguntas contra ambos con un proveedor real. El chat se conserva y sigue siendo la vía para consultas abiertas.

## Limitaciones

- Dobles en lugar de proveedores: no se prueban cuotas, latencia real, ni la calidad de la explicación.
- El analizador y el generador siguen sin contrastarse con salidas reales de Packet Tracer o un 2960 (pendiente de las fases 3 y 4).
- «Utilidad del resumen» y «resolución confirmada» se miden solo como presencia de contenido y cambio de estado, no con usuarios.
- Sin pruebas de carga ni de concurrencia; una instancia local.

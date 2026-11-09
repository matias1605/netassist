# NetAssist: fases de implementación

## Objetivo y alcance

Transformar el asistente educativo Cisco IOS en un espacio de trabajo para generar propuestas, diagnosticar con evidencias y guardar casos. Primer escenario: VLAN y puertos de acceso en laboratorio. Las dos interfaces deben compartir servicios, datos de prueba y reglas.

## Requisito transversal: respuestas de IA

- Concisas y precisas, sin saludos repetidos, relleno ni duplicación de advertencias.
- Como orientación, hasta 180 palabras explicativas en consultas simples; comandos y diagramas no cuentan. Los casos complejos pueden requerir más detalle.
- Configuración: comandos por equipo, verificaciones y advertencia breve.
- Topología: diagrama y hasta dos frases de alcance; sin comandos innecesarios.
- Diagnóstico: causa, comprobaciones, comando y aviso; pasos concretos y ordenados.
- Pedir juntos los datos obligatorios faltantes; no completarlos con valores inventados.
- Distinguir diseño propuesto, validación automática y comprobación en laboratorio.
- Las reglas del prompt orientan la generación; todavía no hay un validador posterior que garantice su cumplimiento.

## Preparación implementada

- Instrucciones compartidas de precisión y brevedad en `backend/prompts.py`.
- Acciones «Generar configuración» y «Generar topología» en web y Streamlit.
- Escenario común en `docs/datos_prueba_vlan.json`: SW1, dos PC, VLAN 10 y 20, puertos de acceso; sin IP ni enrutamiento entre VLAN.
- Los botones preparan borradores editables. La generación solo empieza al enviarlos; no ejecutan comandos ni prueban dispositivos.
- Catálogo compartido `backend/acciones.py` y endpoint `GET /acciones` para la web.

Este avance prepara la interacción. No equivale a un generador validado, un diagnóstico estructurado ni un gestor de casos terminado.

## Fases y criterios de cierre

| Fase | Estado | Entregables | Criterio de cierre |
|---|---|---|---|
| 1. Fortalecer la base | Completada (pruebas locales, 09/11/2026) | Política de datos coherente, revisión de historial completo, límites globales, recuperación contextual, reindexación segura y pruebas del respaldo | Un fallo de reconstrucción conserva el índice previo; fallos inducidos permiten usar el respaldo; información bloqueada no llega al proveedor desde turnos anteriores. |
| 2. Espacio de laboratorio | En curso | Acciones rápidas ya añadidas; pendientes formulario de equipos, requisitos y panel de resultados | Se inicia una tarea desde un formulario, se revisan los datos y se diferencia claramente propuesta de resultado comprobado. |
| 3. Generador VLAN | Por hacer | Solicitud estructurada, validadores, comandos por equipo, verificaciones y persistencia mínima del caso | Faltan datos → se solicitan; VLAN/puertos inválidos → se rechazan; un caso de referencia se comprueba en simulador y puede reabrirse. |
| 4. Diagnóstico con evidencia | Por hacer | Analizador de salidas del escenario, pasos y resultados persistentes, fuentes | Cada observación referencia evidencia; no se repiten pasos completados y los resultados ambiguos piden aclaración. |
| 5. Casos e informes | Por hacer | Lista de casos, estados, resumen exportable, acceso por usuario cuando corresponda | Se recuperan requisitos, propuestas, fuentes y evidencias; un usuario no accede a casos ajenos. |
| 6. Demostración y evaluación | Por hacer | Escenarios reproducibles, fallos de proveedor, casos incompletos y métricas | Se presenta evidencia de funcionamiento, limitaciones y comparación contra el chat inicial. |

## Diseño técnico previsto

- Mantener ChromaDB exclusivamente para conocimiento; añadir una base de aplicación independiente.
- Para un laboratorio local de una instancia, comenzar con SQLite y migraciones; revisar el almacenamiento al definir el despliegue concurrente.
- Persistencia mínima de fase 3: casos, equipos, requisitos y propuestas. Extender después con pasos, evidencias, fuentes y evaluaciones.
- Servicio compartido de casos/diagnóstico consumido por Streamlit y FastAPI; evitar reglas duplicadas en cada pantalla.
- Contrato previsto del generador: identificador del caso, equipos, datos faltantes, comandos por equipo, verificaciones, advertencias, fuentes y estado de validación.
- Contrato previsto de topología: nodos, enlaces, datos confirmados, supuestos y Mermaid renderizable. Un diagrama no certifica conectividad.
- Validaciones previstas: VLAN admitidas por el escenario, interfaces declaradas, puertos no asignados a dos VLAN de acceso y coherencia de direcciones cuando se incorpore direccionamiento.

## Primer incremento funcional

1. Elegir «Generar configuración» y revisar el ejemplo común.
2. Completar modelo, versión, VLAN y puertos desde un formulario.
3. Validar los datos y generar una propuesta sustentada en fichas.
4. Guardar el caso y producir su topología a partir de los mismos datos.
5. Probar manualmente en simulador y adjuntar las salidas de verificación.

Las acciones actuales cubren el primer paso como borrador de chat. Los siguientes requieren implementar los servicios y validadores descritos.

## Evaluación prevista

| Área | Casos mínimos |
|---|---|
| Configuración | Datos completos, modelo ausente, VLAN inválida, puerto repetido y objetivo fuera del corpus |
| Topología | Dos PC y un switch, datos incompletos, ausencia de IP y enlace no declarado |
| Continuidad | Reabrir el caso, continuar tras una verificación y evitar repetición |
| Proveedores | Primario caído, respaldo caído y captura enviada cuando solo queda respaldo textual |
| Conocimiento | Fuente válida, ausencia de ficha aplicable y reconstrucción fallida |
| Interfaz | Editar, descartar y enviar borrador; acciones con consulta previa; pantalla estrecha |

Medir corrección, fuentes válidas, resolución confirmada, latencia y utilidad del resumen. Los resultados históricos del chat no certifican estas funciones futuras.

## Resultado de la fase 1 — 9 de noviembre de 2026

Estado: **completada en el alcance local de una instancia**, con 18 pruebas automatizadas satisfactorias y fallos inducidos. Evidencias y reproducción en `pruebas/verificacion_fase1.md`; salida de ejecución en `pruebas/resultado_fase1.txt`. No se inició la fase 2 ni se certificó funcionamiento en equipos o proveedores reales.

| Entregable | Implementación y resultado |
|---|---|
| Política de laboratorio coherente | Un único filtro compartido por ambas interfaces y la ruta alternativa de LLM. Admite direcciones privadas/locales/de documentación y máscaras; bloquea IP fuera del alcance y patrones de credenciales con valor. Permite preguntas conceptuales sobre `enable secret`. Sustitución local manual de datos reales; no altera evidencias automáticamente. |
| Historial completo | Revisa usuario y asistente antes de recuperación y proveedores. También revisa el prompt saliente; un turno bloqueado impide todo el envío. Pruebas de bloqueo en cadena, API y ruta alternativa. |
| Límites globales | Hasta 40 mensajes, 12000 caracteres por turno y 48000 por conversación, en el servicio compartido. Se rechaza el exceso sin truncar evidencias. Capturas decodificadas y estáticas: máximo 4 MB y 16 millones de píxeles. |
| Capturas | Confirmación explícita de revisión en web y Streamlit, exigida también por el servicio. No se realiza OCR ni anonimización visual; una casilla no certifica ausencia de secretos. Retiradas las instrucciones de elusión mediante imágenes. |
| Recuperación contextual | Última consulta (hasta 2000 caracteres para búsqueda) y ventana de seis mensajes previos (hasta 800 caracteres por mensaje). El proveedor conserva el historial admitido completo. No equivale al resumen estructurado de casos de fases posteriores. Las capturas ya no agregan fichas con distancia ficticia. |
| Reindexación segura | Reutilización al iniciar; reconstrucción explícita en una colección candidata validada por conteo y consulta, con publicación por referencia atómica. Bloqueo de archivo entre procesos locales. Fallos de lectura, embeddings, escritura, validación y publicación conservan el índice consultable anterior. Corpus vacío rechazado. FastAPI ejecuta la operación fuera del bucle de atención. |
| Administración | Reindexación por loopback cuando no hay token; con `REINDEX_ADMIN_TOKEN`, exige `X-Admin-Token`. Se debe configurar el token al publicar o usar un proxy. El fallo de reconstrucción no inhabilita el chat si había índice disponible. |
| Respaldo y registros | Una sola política Gemini → Groq → aviso fijo. Pruebas de error, respuesta vacía y caída doble. Con imagen, Groq recibe solo texto y el servicio antepone aviso de pérdida de capacidad visual. Gemini usa la clave en cabecera; registros con proveedor, latencia y tipo de error sin texto de excepción. |
| Conservación de interacción | Se mantienen las dos acciones rápidas y sus borradores editables, así como las reglas de respuestas concisas y precisas. Se eliminó la instrucción contradictoria de inventar números para direcciones con X. |

Verificación adicional: compilación de Python, revisión de sintaxis de `frontend/app.js` y `git diff --check`, sin errores. Dependencias directas Pillow y filelock declaradas en ambas modalidades y alineadas con las versiones del archivo de entorno local.

Límites del cierre: filtro heurístico, revisión manual de adjuntos, sin prueba visual de navegador ni llamadas a proveedores reales, sin prueba en simulador. El índice se probó con Chroma real en memoria y embeddings deterministas; publicación y bloqueo en directorio temporal. No se modificó el índice local del proyecto. Tras actualizar el corpus, ejecutar una reindexación administrativa para incorporar el ejemplo DNS de documentación. Las generaciones anteriores se conservan para lectores abiertos y no se limpian automáticamente; otras instancias abiertas actualizan su generación al reiniciar. No se garantiza coordinación sobre almacenamiento de red ni alta disponibilidad.

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
| 2. Espacio de laboratorio | Completada (pruebas locales, 09/11/2026) | Acciones rápidas conservadas; formulario de equipo, VLAN/conexiones y requisitos; revisión explícita y panel de resultados en ambas interfaces | Se inicia una tarea desde un formulario, se revisan los datos y se diferencia claramente propuesta de resultado comprobado. |
| 3. Generador VLAN | Implementada (pruebas locales, 09/11/2026); comprobación en simulador pendiente | Solicitud estructurada, validadores, comandos por equipo, verificaciones y persistencia mínima del caso | Faltan datos → se solicitan; VLAN/puertos inválidos → se rechazan; un caso de referencia se comprueba en simulador y puede reabrirse. |
| 4. Diagnóstico con evidencia | Implementada (pruebas locales, 09/11/2026); comprobación con salidas reales de simulador pendiente | Analizador de salidas del escenario, pasos y resultados persistentes, fuentes | Cada observación referencia evidencia; no se repiten pasos completados y los resultados ambiguos piden aclaración. |
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

Las acciones rápidas cubren el primer paso como borrador de chat. La fase 2 añade el formulario del segundo paso, revisión de campos y generación mediante la cadena existente. La validación técnica, persistencia y comprobación en simulador de los pasos siguientes corresponden a la fase 3.

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

## Resultado de la fase 2 — 9 de noviembre de 2026

Estado: **completada para el espacio de laboratorio local**. Se puede iniciar una tarea desde un formulario, revisar la solicitud y generar una respuesta separada de una comprobación real. Se conservan el chat, las dos acciones rápidas con borradores editables y las instrucciones compartidas de precisión y brevedad.

| Entregable | Implementación y resultado |
|---|---|
| Formulario de laboratorio | Web y Streamlit: tipo de tarea (configuración/topología), nombre, alias del switch, modelo/IOS, conexiones con VLAN/nombre/puerto/host y objetivo/requisitos. Un switch y de 1 a 16 conexiones; datos ficticios, sin IP, trunk ni enrutamiento. Ejemplo común de `docs/datos_prueba_vlan.json`. |
| Preparación compartida | `backend/laboratorio.py` concentra modelos, ejemplo, campos faltantes, prompt y generación. API web: `GET /laboratorio/ejemplo`, `POST /laboratorio/preparar` y `POST /laboratorio/generar`; Streamlit utiliza el mismo servicio directamente. |
| Revisión antes de generar | Revisar datos no llama a la IA. Los faltantes se muestran juntos; modelo e IOS se requieren para configuración. Se presenta la solicitud y se exige confirmación. Editar cualquier dato invalida revisión, confirmación y resultado anterior. Descartar permite seguir editando sin generar. |
| Panel de resultados | Estados sin propuesta, respuesta generada y fallo recuperable. Validación técnica siempre pendiente y comprobación en laboratorio no realizada. La caída total de proveedores se muestra como aviso sin propuesta. La generación no ejecuta comandos. |
| Reglas y límites | Campos y filas acotados, filtro de datos y presupuesto global de fase 1. No se mezclan los datos del formulario con el historial del chat. La generación reutiliza la cadena compartida y su respaldo. |
| Interfaz y regresiones | 31 pruebas automatizadas satisfactorias (18 de fase 1 y 13 nuevas), incluidas dos pruebas interactivas de Streamlit. Smoke en Chrome con API simulada: revisión, confirmación, edición, faltantes, descarte, ejemplo, conexiones, topología, error recuperable y acciones rápidas. Capturas de escritorio y móvil de 390 px, sin desbordamiento horizontal ni errores JavaScript. |

Evidencias: `pruebas/verificacion_fase2.md`, `pruebas/resultado_fase2.txt`, `pruebas/resultado_web_fase2.txt` y `pruebas/evidencias/fase2-web-*.png`. Compilación de Python, sintaxis de ambos scripts JavaScript y `git diff --check`: correctos.

Límites: revisión de campos presentes y tamaños, no validador técnico de rangos VLAN, sintaxis de puertos, asignaciones duplicadas ni soporte del modelo. Los valores del formulario son datos declarados, no observados en dispositivos. No hay casos persistentes; el resultado del formulario se conserva solo mientras la página/sesión permanece abierta. No se probaron proveedores reales ni simulador. El smoke del navegador simula la API y bloquea el CDN; no valida Mermaid ni conecta todo el flujo con un proveedor real. Streamlit se verifica con AppTest, sin captura de navegador. La fase 3 permanece por hacer.

## Resultado de la fase 3 — 9 de noviembre de 2026

Estado: **implementada y verificada con pruebas automatizadas y smoke de navegador; falta la comprobación manual del caso de referencia en simulador**, que es parte del criterio de cierre. No se ha certificado funcionamiento en equipos.

| Entregable | Implementación y resultado |
|---|---|
| Validadores | `backend/validadores.py`: VLAN 2–4094 (1 y 1002–1005 rechazadas), nombre de VLAN, sintaxis de puerto (Fa/Gi y formas largas, normalizadas), puerto no asignado dos veces, VLAN con dos nombres, host repetido, alias válido. Modelo distinto de 2960: advertencia, no error. Los vacíos los sigue informando `faltantes`. |
| Estados de validación | `reglas_aprobadas`, `incompleta` o `rechazada`; sustituyen a «pendiente». Con errores no hay propuesta ni llamada a la IA (422 en API). La comprobación en laboratorio sigue `no_realizada` hasta registrarla. |
| Generador | `backend/generador.py`: comandos IOS y diagrama Mermaid por plantilla determinista, no del modelo. Contrato: equipos, datos faltantes, comandos por equipo, verificaciones, advertencias, fuentes (de la búsqueda RAG) y estado de validación; topología con nodos, enlaces, confirmados y supuestos. La IA solo añade una explicación breve; si los proveedores caen, la propuesta determinista se conserva (`propuesta_sin_explicacion`). |
| Persistencia | `backend/casos.py`: SQLite independiente de Chroma (`backend/data/netassist.db`, o `NETASSIST_DB`), migraciones con `PRAGMA user_version`, tablas casos, equipos, conexiones, requisitos y propuestas, WAL y claves foráneas. Generar guarda el caso; regenerar con el mismo `caso_id` actualiza datos y añade propuesta. Se aplica el filtro de datos sensibles. |
| API | `GET /casos`, `GET /casos/{id}`, `POST /casos/{id}/comprobacion` (resultado correcta/fallida y salidas pegadas) y `caso_id` opcional en `/laboratorio/generar`. |
| Interfaces | Web y Streamlit: errores de reglas, propuesta previa sin IA, bloqueo de generación con errores, caso guardado, lista de casos y reabrir con su propuesta. Formato común en `formatear_propuesta`. |

Pruebas: 57 automatizadas satisfactorias (31 previas, con dos ajustes por los nuevos estados, y 26 nuevas), incluidas dos de Streamlit. Las pruebas de fase 2 ahora aíslan la base de casos. Smoke en Chrome con API real: VLAN 4095 rechazada y generación bloqueada; ejemplo revisado, generado (sin proveedor disponible, propuesta determinista) y guardado; caso reabierto con datos, propuesta y diagrama.

Límites: sin usuarios ni acceso por usuario (fase 5); una instancia local, sin coordinación en red; el registro de la comprobación manual existe en la API pero sin pantalla; el generador cubre solo VLAN y puertos de acceso en un switch; el filtro de datos sensibles es heurístico. **Pendiente para cerrar la fase:** aplicar los comandos del ejemplo en Packet Tracer, registrar las salidas con `POST /casos/{id}/comprobacion` y confirmar que el caso puede reabrirse.

## Resultado de la fase 4 — 9 de noviembre de 2026

Estado: **implementada y verificada con pruebas automatizadas y smoke de navegador**. Las salidas usadas en las pruebas son de formato IOS reproducido a mano; falta contrastar el analizador con salidas reales de Packet Tracer o de un 2960 (mismo pendiente que la fase 3).

| Entregable | Implementación y resultado |
|---|---|
| Analizador de salidas | `backend/diagnostico.py`: interpreta `show vlan brief` (incluye puertos en líneas de continuación y abreviaturas Gi/Fa) y `show interfaces <puerto> switchport`, y lo compara con las conexiones declaradas del caso. Acepta varias salidas pegadas juntas (por prompt, por «Name:» o por cabecera de tabla). Determinista; no usa IA ni consulta dispositivos. |
| Observaciones con evidencia | Severidades `ok`, `problema`, `aviso` y `ambiguo`. Detecta VLAN ausente o con otro nombre, puerto en otra VLAN, modo distinto de acceso, switchport deshabilitado, puertos no declarados en la VLAN (aviso) y enlace caído (aviso). Cada hallazgo cita su evidencia (`E<n>`) y trae la corrección de la misma plantilla del generador, marcada como no ejecutada. |
| Pasos persistentes | Un paso por tabla de VLAN y uno por puerto declarado (`pasos`, `evidencias`, `observaciones`, migración 2 con `PRAGMA user_version`). Estados: pendiente, completado, con hallazgos, ambiguo. Un paso completado no se repite y la misma salida no se guarda dos veces; el motivo se informa en `omitidos`. Tras corregir, una salida nueva sustituye al hallazgo y el historial se conserva. |
| Resultados ambiguos | Tabla cortada, puerto ausente de la tabla (puede ser troncal), salida incompleta o interfaz no declarada: no cierran el paso, piden aclaración y no se afirman como error. Texto no reconocido no se guarda. |
| Estado del diagnóstico | `sin_evidencia`, `en_curso`, `con_hallazgos`, `requiere_aclaracion`, `coherente`. «Coherente» significa que las salidas coinciden con lo declarado; no prueba conectividad. El caso pasa a `en_diagnostico` o `diagnostico_coherente` sin pisar `comprobado`. |
| Vigencia | Si cambian equipo o conexiones del caso, las evidencias previas quedan como no vigentes (se conservan) y los pasos se rehacen; guardar los mismos datos no los toca. |
| Fuentes | El diagnóstico cita las fichas devueltas por el RAG; si el índice cae, el diagnóstico sigue disponible sin fuentes. |
| API e interfaces | `GET /casos/{id}/diagnostico`, `POST /casos/{id}/evidencias`, `GET /casos/{id}/evidencias`. Sección «4. Diagnóstico con evidencia» en web y Streamlit, con formato común `formatear_diagnostico`. Se aplican el filtro de datos sensibles y el límite de 8000 caracteres. |

Pruebas: 86 automatizadas satisfactorias (57 previas y 29 nuevas en `test_fase4.py`: analizador, almacén, API y Streamlit). Se actualizó una aserción de fase 3 para que la versión de esquema siga a las migraciones. Smoke en Chrome con API real y base temporal: caso generado, salida con un puerto en la VLAN 1 → hallazgo `E1`, corrección propuesta, pasos pendientes y fuente citada. Evidencias: `pruebas/verificacion_fase4.md`, `pruebas/resultado_fase4.txt`.

Límites: cubre solo VLAN y puertos de acceso en un switch; no interpreta `show running-config`, `show interfaces status` ni trunk; el analizador se probó con salidas redactadas a mano; sin usuarios ni acceso por usuario (fase 5); la resolución confirmada depende de que la persona pegue la salida posterior a corregir; sin pruebas con simulador ni proveedores reales; la vista móvil del panel no se midió.

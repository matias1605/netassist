# NetAssist: análisis del proyecto y propuesta de valor agregado

Fecha: 9 de noviembre de 2026.

## 1. Conclusión

NetAssist tiene una base funcional de asistente educativo para Cisco IOS: dos interfaces, recuperación de manuales locales, respuestas con IA, imágenes, diagramas y proveedor de respaldo. Su principal oportunidad es **convertir las conversaciones en casos de diagnóstico guiado, con evidencias, seguimiento y resultado verificable**.

Actualmente el sistema entrega orientación, pero no mantiene un registro de qué problema se resolvió, qué verificaciones se ejecutaron o qué necesita revisar el docente. Esa continuidad ofrece más valor al laboratorio que agregar otro proveedor de IA o una tercera interfaz.

Esta propuesta mantiene Python, FastAPI, Streamlit y ChromaDB. Añade una base de datos de la aplicación y un servicio de diagnóstico compartido. No requiere conectarse a equipos reales para demostrar su utilidad.

## 2. Alcance y evidencia

Se revisaron los módulos Python del backend y Streamlit, HTML/JS/CSS, configuraciones de ejemplo, dependencias declaradas y locales, scripts de inicio, documentación, las seis fichas Cisco y los archivos de ambas rondas de evaluación.

Se inspeccionó `backend/chroma_db/chroma.sqlite3` en modo de solo lectura. Se ejecutaron comprobaciones locales de detección de datos, validación de imagen, fragmentación, sintaxis Python y comportamiento de la cadena con recuperación y proveedor simulados. Las simulaciones no enviaron mensajes a Gemini ni a Groq.

No se ejecutó una nueva ronda con proveedores reales, una prueba visual de navegador, una prueba de carga ni una validación contra equipos Cisco. Los resultados históricos son evidencia guardada en el repositorio, no una certificación independiente de la versión actual. No se consultó ni expuso el contenido de `.env`.

## 3. Estructura implementada

| Componente | Responsabilidad actual | Observación |
|---|---|---|
| `backend/main.py` | API FastAPI, modelos de entrada, inicio de RAG y cuatro endpoints | El chat recibe el historial del cliente; no gestiona casos ni identidades. |
| `backend/cadena.py` | Flujo LangChain: filtro → recuperación → prompt → Gemini → Groq → aviso fijo | Compartido por ambas interfaces. Es la ruta principal de generación. |
| `backend/rag.py` | Lectura TXT/PDF, fragmentación, embeddings, almacenamiento y búsqueda | El índice se reconstruye en cada inicialización. |
| `backend/llm.py` | Clientes HTTP de Gemini y Groq, validación de configuración y respuestas de contingencia | También contiene `llamar_llm`, una segunda ruta de orquestación que no usan actualmente las interfaces. |
| `backend/prompts.py` | Formato, alcance Cisco, advertencias, memoria conversacional y topologías | Muchas reglas se expresan como instrucciones al modelo, sin validación posterior. |
| `backend/seguridad.py` | Expresión regular para datos sensibles y validación básica de imágenes | No anonimiza información ni analiza el contenido visual. |
| `backend/config.py` | Variables de entorno, rutas, modelo y umbral RAG | Centraliza la configuración y valida algunos parámetros. |
| `frontend/` | Chat HTML/CSS/JS, adjuntos, pegado de imágenes, copiado de comandos y Mermaid | Historial de texto en `localStorage`; API fijada a `http://localhost:8000`. |
| `streamlit_app.py` | Portal de laboratorio y chat flotante | Usa la cadena directamente, sin pasar por FastAPI. Historial en `st.session_state`. |
| `docs/` | Conocimiento de referencia | Un TXT con seis fichas; soporte de PDF implementado, pero sin PDF de ejemplo. |
| `pruebas/` | Veinte casos, dos rondas documentadas, imágenes y guion de demo | No hay suite automatizada de regresión en los archivos versionados. |
| `.streamlit/` | Tema y ejemplo de secretos | Los secretos reales están excluidos de Git. |
| `iniciar.ps1` y `Iniciar NetAssist.cmd` | Inicio local con entorno y cachés del proyecto | Permiten elegir Streamlit o web y comprueban puertos ocupados. |
| Archivos `requirements*` | Instalación por modalidad y versiones del entorno local | Hay varias listas que necesitan mantenerse coordinadas. |

### Flujo de datos

```text
Web HTML → FastAPI ─────────────┐
                              ├→ cadena compartida → filtro del último mensaje
Streamlit ─────────────────────┘                         ↓
                                         búsqueda de fichas en ChromaDB
                                                       ↓
                                         prompt + historial + imagen actual
                                                       ↓
                                         Gemini → Groq → mensaje fijo
                                                       ↓
                                         texto y topología en la interfaz
```

Las imágenes viajan a Gemini. Groq recibe texto y una indicación de que no puede ver la imagen. Las imágenes anteriores no se reenvían al modelo: en la web quedan notas de adjunto y en Streamlit se conservan los bytes para mostrarlos en la sesión, pero la cadena solo recibe la imagen del turno actual.

### API existente

| Método y ruta | Función | Limitación relevante |
|---|---|---|
| `POST /chat` | Responde con `reply` y `contact` | No devuelve fuentes estructuradas, proveedor, estado del caso ni resultados de verificaciones. |
| `POST /reindexar` | Reconstruye la colección desde `docs/` | Sin autenticación; reconstrucción síncrona y destructiva del índice anterior. |
| `GET /health` | Estado de API e inicialización RAG | `rag_ready` depende de que la inicialización no falle; no prueba proveedores ni garantiza que existan fichas. |
| `GET /contacto` | Contacto humano configurado | Mostrar contacto no crea un ticket ni entrega contexto al docente. |

## 4. Base de datos: qué existe realmente

### ChromaDB

La base actual es un índice vectorial persistente, no una base de datos funcional de usuarios o incidencias.

- Ubicación: `backend/chroma_db/`.
- Colección observada: `manuales_netassist`.
- Dimensión de embeddings observada: 384.
- Corpus fuente: un TXT de 761 palabras, dividido en seis fichas.
- Identificadores generados: ruta del documento y número de fragmento.
- Metadatos de aplicación: `archivo` y `fragmento`.
- Contenido: texto de la ficha y su representación vectorial.
- Búsqueda: similitud coseno; por defecto hasta cuatro resultados y distancia máxima de 0,65, configurables por entorno.

Las seis fichas cubren conectividad, interfaces administrativamente caídas, rutas estáticas, DNS, SVI y VLAN.

La lectura del SQLite interno encontró seis registros de embeddings asociados al segmento de metadatos vigente y otros seis sin correspondencia con los segmentos actuales. Esto **no demuestra que la búsqueda devuelva resultados duplicados**. Sí justifica revisar el ciclo de reconstrucción y mantenimiento antes de ampliar el corpus. No se modificaron esas tablas; son internas de ChromaDB.

### Persistencia que falta

No hay entidades de usuarios, roles, casos, equipos, mensajes persistidos en servidor, verificaciones, evaluaciones, derivaciones o resultados. Tampoco existen migraciones para una base de datos de aplicación.

| Información | Dónde se conserva hoy |
|---|---|
| Manuales y embeddings | Disco local y ChromaDB |
| Conversación web | Texto en el navegador, hasta limpiar el historial |
| Conversación Streamlit | Estado de la sesión; no es un archivo de casos recuperable |
| Imágenes web | Memoria de la página durante el uso; no en el historial persistido |
| Imágenes Streamlit | Memoria de la sesión |
| Calificación de pruebas | Archivos Markdown editados manualmente |
| Resultado de una incidencia | Sin registro estructurado |

## 5. Funciones existentes y nivel de garantía

| Capacidad | Implementación | Qué falta para confiar en ella de forma consistente |
|---|---|---|
| Consultas Cisco con manuales | RAG y prompt compartidos | Más cobertura y medición de recuperación por tema. |
| Memoria | Reenvío del historial | Estado estructurado de pasos y recuperación que use el contexto del caso. |
| Respuesta en cuatro secciones | Instrucción de sistema | Validación de salida y criterios de aceptación. |
| Pedir modelo y versión antes de configurar | Instrucción de sistema | Regla del servicio que impida habilitar cambios si faltan esos datos. |
| Topología | Mermaid producido por el modelo | Separar datos confirmados de inferencias y comprobar la sintaxis. |
| Análisis de capturas | Gemini multimodal | Manejo explícito de incertidumbre y pérdida de capacidad visual en el respaldo. |
| Datos sensibles | Bloqueo por patrón de texto | Revisar todo el historial y aplicar una política coherente para imágenes y datos del laboratorio. |
| Respaldo del proveedor | `with_fallbacks` | Registrar cuál respondió y si se perdió capacidad visual. |
| Derivación humana | Contacto mostrado en la respuesta o diálogo web | Caso, resumen y estado de entrega. |

## 6. Hallazgos que conviene resolver primero

### Prioridad alta

1. **El servidor solo filtra el último mensaje.** `main.py` y `cadena.py` no revisan todo el historial recibido. Se reprodujo con la cadena real y un proveedor simulado: un mensaje anterior con una IPv4 llegó al proveedor cuando el último mensaje era inocuo. La interfaz web evita guardar ciertos mensajes bloqueados, pero eso no protege solicitudes directas a la API ni todo el contenido generado por el asistente. Aplicar la política a todo el material saliente.

2. **La política de datos impide diagnósticos normales y tiene huecos.** El filtro bloquea `255.255.255.0`, `999.999.999.999` y una pregunta conceptual sobre `enable secret`; no detectó `2001:db8::1` ni `token=EJEMPLO_FICTICIO`. Bloquea secuencias que parecen IPv4 y algunas palabras, no identifica de forma completa secretos o información real. La guía de demo incluso propone pasar direcciones en imágenes para evitar el bloqueo. Definir un modo de laboratorio explícito y anonimización local coherente entre texto, historial y adjuntos.

3. **Modelo/versión y avisos dependen del modelo.** Las respuestas guardadas de ronda 2 incluyen comandos de configuración sin una confirmación previa del modelo y la versión. Marcar una respuesta como correcta por contener el comando esperado no verifica esta regla. Incorporar controles del servicio y criterios separados para corrección técnica, datos requeridos y advertencias.

4. **Reindexar elimina primero la colección anterior.** Un PDF ilegible o un fallo de embeddings posterior puede dejar el índice sin la versión que funcionaba. Preparar una colección nueva, validarla y cambiar la referencia después. Restringir la operación a administración si se ofrece fuera del uso local.

### Prioridad media

5. **Recuperación sin contexto conversacional.** La búsqueda usa solo la última consulta. Se confirmó que un seguimiento como «¿qué verifico ahora?» es la consulta enviada al recuperador, aunque el historial contenga el síntoma. Construir la consulta con el resumen estructurado del caso y el último resultado.

6. **Con imágenes se agregan fichas sin relevancia medida.** `buscar_con_imagen` completa hasta ocho fichas y les asigna distancia `0.0`. Con seis fichas puede terminar enviando todo el corpus. Esa distancia no debe interpretarse como confianza. Registrar el motivo de inclusión y recuperar usando una descripción de la imagen cuando el corpus crezca.

7. **Fuentes poco trazables.** El prompt recibe referencias numeradas, pero la cadena devuelve solo texto. El recuperador pierde el identificador de ficha y los PDFs se unen sin conservar página. Devolver fuente, versión, ficha/página y fragmento como datos; validar que las citas correspondan a fuentes recuperadas.

8. **Validación de imagen superficial.** Una cadena base64 con solo la cabecera PNG de ocho bytes fue aceptada. Verificar que se pueda decodificar como imagen y limitar dimensiones además del peso. No equivale a revisar datos sensibles en la captura.

9. **Sin límites globales de conversación.** Cada mensaje de API tiene límite de 12 000 caracteres, pero la lista de mensajes no tiene máximo ni presupuesto global de contexto. Puede crecer el tiempo, costo y tamaño de solicitud. Añadir límites y resumen sin perder evidencias del caso.

10. **Operaciones pesadas dentro de rutas asíncronas.** Reindexar realiza lectura y embeddings de forma síncrona. Puede bloquear la atención de otras solicitudes en ese proceso. Llevarlo a una tarea controlada y evitar reconstrucciones concurrentes desde FastAPI y Streamlit sobre la misma colección.

11. **Renderizado Streamlit a endurecer.** Se interpola `json.dumps(fuente)` del diagrama en una etiqueta `script`. JSON no neutraliza por sí solo un cierre HTML como `</script>`. No se realizó explotación de navegador. Evitar insertar contenido del modelo directamente en código de script o escapar los caracteres relevantes al contexto HTML.

12. **Observabilidad y errores.** La respuesta no distingue un diagnóstico normal de la contingencia, ni registra métricas estructuradas. En la ruta Gemini la clave se envía en la URL; las excepciones HTTP registradas con trazas podrían incluirla. Redactar URLs y secretos en registros, registrar proveedor/latencia/resultado y verificarlo sin claves reales.

### Mantenimiento

- Hay dos rutas de orquestación en `cadena.py` y `llm.py`; consolidar para evitar divergencias.
- La interfaz web fija el servidor a localhost; permitir configuración al desplegar.
- El guion contiene rutas de otra máquina. README y guía necesitan reflejar consistentemente adjuntos, respuestas y límites actuales.
- Mantener coordinadas las listas de dependencias y verificar reinstalación limpia. No se auditó disponibilidad actual de modelos o vulnerabilidades de paquetes.

## 7. Qué dicen realmente las pruebas existentes

Las dos rondas documentan 20/20 respuestas correctas y cero alucinaciones según la evaluación guardada. Se recalcularon los tiempos de los encabezados:

| Métrica histórica | Ronda 1 | Ronda 2 |
|---|---:|---:|
| Casos registrados | 20 | 20 |
| Promedio incluyendo bloqueos | 3,415 s | 3,890 s |
| Promedio excluyendo bloqueos | 3,794 s | 4,322 s |

Los promedios coinciden con los redondeos publicados. Sin embargo, las propias observaciones mencionan topologías ausentes en casos donde se esperaban. También hay respuestas con configuración sin confirmar modelo/IOS. El 100 % debe presentarse como resultado de esa rúbrica manual, no como cobertura completa del producto.

Faltan evaluaciones de continuidad entre turnos, historial sensible, fallos de proveedores inducidos, capturas ilegibles, citas verificables, reindexación fallida y concurrencia. Las comprobaciones nuevas de este análisis no sustituyen esas pruebas.

## 8. Valor agregado recomendado: diagnóstico guiado con expediente del caso

**Propuesta:** cada consulta técnica puede convertirse en un caso que mantiene el síntoma, los equipos, las verificaciones realizadas, las evidencias y el resultado. La IA explica y propone; el servicio controla los estados y registra lo confirmado.

### Experiencia propuesta

1. El estudiante abre «Nuevo diagnóstico» y selecciona interfaces, conectividad, rutas, DNS, SVI o VLAN.
2. Registra equipo, modelo/IOS si los conoce y síntoma. Puede empezar con verificaciones de lectura aunque falten datos.
3. NetAssist ofrece una comprobación concreta, explica su propósito y muestra la ficha utilizada.
4. El estudiante pega la salida anonimizada o adjunta una captura. El sistema conserva el paso como realizado y su resultado.
5. El diagnóstico avanza usando esas evidencias. Los cambios requieren los datos definidos como obligatorios; una salida dudosa pide aclaración.
6. Se verifica la recuperación del servicio: por ejemplo, estado up/up o conectividad restaurada. La confirmación del estudiante queda distinguida de una evidencia analizada.
7. El caso queda resuelto, pendiente o derivado. Una derivación prepara un resumen para el docente y el usuario decide cómo compartirlo.

**Ejemplo de demostración:** un estudiante reporta una interfaz caída; registra el resultado, aplica la corrección en Packet Tracer y aporta la verificación posterior. El docente puede revisar el razonamiento y las evidencias, incluso si el caso no se resolvió.

### Comparación de oportunidades

| Mejora | Valor para este proyecto | Esfuerzo relativo | Orden sugerido |
|---|---|---|---|
| Pasos y estado del diagnóstico | Hace consistente la continuidad y evita repetir trabajo | Medio | Primero |
| Casos persistentes y resumen | Permite retomar y derivar con contexto | Medio | Primero |
| Fuentes verificables | Hace revisable la explicación técnica | Bajo–medio | Primero |
| Analizador local de salidas `show` | Aporta hechos estructurados sin depender solo del LLM | Medio | Después del primer flujo |
| Panel docente | Muestra problemas frecuentes y casos pendientes | Medio | Tras registrar casos reales |
| Prácticas con pistas progresivas | Refuerza aprendizaje y evaluación | Medio | Segunda etapa |
| Soporte MikroTik | Amplía alcance, exige corpus y pruebas propios | Alto | Más adelante |
| Conexión y ejecución sobre equipos | Añade credenciales, permisos y operación real | Alto | Fuera del primer alcance |

El analizador local puede comenzar exclusivamente con `show ip interface brief`, identificando estado administrativo y de protocolo. Cada familia adicional de salida necesita ejemplos y pruebas propios. No debe marcar una causa como confirmada solo por la semejanza textual de una ficha.

## 9. Base de datos propuesta

Mantener ChromaDB para recuperación. Para el primer despliegue local de un solo servidor, añadir una base SQLite independiente para los datos de aplicación. Si el objetivo es uso institucional concurrente o varias instancias, evaluar PostgreSQL desde el diseño de despliegue. Las tablas internas de Chroma no deben reutilizarse como tablas del producto.

| Entidad | Datos principales | Relación |
|---|---|---|
| `usuarios` | ID, identidad externa o identificador, rol | Un usuario tiene varios casos; necesaria al habilitar cuentas y panel docente. |
| `casos` | ID, propietario/sesión, categoría, síntoma, estado, fechas, resumen | Unidad principal de seguimiento. |
| `equipos_caso` | ID, caso, alias, fabricante, modelo, versión | Un caso puede involucrar varios equipos. |
| `mensajes` | ID, caso, rol, contenido anonimizado, fecha, estado de generación | Historial persistente con límites y retención. |
| `pasos_diagnostico` | ID, caso, equipo, orden, comprobación, resultado esperado, resultado observado, estado | Distingue pendiente, realizado y descartado. |
| `evidencias` | ID, caso/paso, tipo, texto saneado o referencia de archivo, fecha | Conserva lo que sustenta el diagnóstico. |
| `fuentes` | ID estable, documento, versión/hash, ficha o página | Referencias rastreables entre reconstrucciones del índice. |
| `mensaje_fuente` | Mensaje, fuente, fragmento recuperado, distancia/motivo | Relación entre explicación y conocimiento utilizado. |
| `derivaciones` | ID, caso, motivo, resumen, estado | Registra una preparación o entrega real sin confundirlas. |
| `evaluaciones` | ID, caso, resolución declarada, utilidad, comentario | Permite medir resultado y satisfacción. |
| `ejecuciones_ia` | ID, mensaje, proveedor, modelo, latencia, contingencia | Métricas operativas sin guardar claves. |

Usar claves foráneas, índices por propietario/estado/fecha y migraciones. Definir borrado y retención desde el primer caso persistido. Un caso anónimo puede servir para la demo, con acceso mediante sesión segura; el panel multiusuario exige autenticación y autorización en servidor. No exponer historiales por conocer un ID.

## 10. Implementación por entregables

| Entregable | Cambios principales | Criterio de aceptación |
|---|---|---|
| A. Base confiable | Política coherente de datos, revisión de historial, límites de entrada y errores saneados | Un dato bloqueado en un turno anterior no llega al proveedor; datos de laboratorio siguen la política definida. |
| B. Primer diagnóstico guiado | Servicio de casos y pasos, persistencia, flujo de interfaces | Se abre un caso, se registra una verificación y se retoma sin repetirla tras recargar. |
| C. Evidencia y fuentes | Identificadores estables, resultado estructurado, citas en interfaz | Cada fuente visible existe y pertenece a la recuperación; la evidencia queda ligada al paso. |
| D. Cierre y derivación | Verificación posterior, estados y resumen exportable | «Resuelto» requiere confirmación registrada; derivar conserva síntoma, pruebas y pendientes. |
| E. Revisión docente | Cuentas/roles, listado y métricas | Cada rol ve únicamente los casos autorizados y puede localizar pendientes. |
| F. Ampliación | Otros cinco flujos y analizadores de salida | Cada flujo incluye casos correctos, ambiguos y sin solución documentada. |

Implementar el servicio compartido detrás de ambas interfaces. Agregar la funcionalidad solo a FastAPI dejaría a Streamlit sin los mismos controles, porque actualmente llama a la cadena de forma directa. Para la demo se puede priorizar la pantalla Streamlit y conectar después la web al mismo servicio.

Como contrato nuevo, el diagnóstico debería devolver campos como `caso_id`, `estado`, `respuesta`, `fuentes`, `siguiente_paso`, `proveedor` y `contingencia`. El estado de negocio debe decidirlo el servicio a partir de eventos y confirmaciones; no copiarlo libremente de una respuesta generada.

## 11. Cómo demostrar el valor

- **Resolución:** casos confirmados como resueltos / casos cerrados, informando también abiertos y derivados.
- **Continuidad:** proporción de seguimientos donde no se repiten comprobaciones ya completadas.
- **Trazabilidad:** respuestas técnicas con fuentes válidas / respuestas técnicas que las requieren.
- **Aprendizaje:** capacidad del estudiante para explicar la causa y justificar la corrección antes y después de la práctica.
- **Tiempo:** mediana y percentil 95 por turno y por caso; separar texto, imágenes y contingencias.
- **Derivación útil:** porcentaje de resúmenes que incluyen síntoma, equipos, evidencias y pasos pendientes.

La comparación debe usar los mismos escenarios con el chat actual y el diagnóstico guiado. Los objetivos numéricos de mejora deben fijarse tras obtener una línea base; no hay evidencia actual para prometer un porcentaje de reducción del tiempo.

## 12. Alcance inicial recomendado

Construir primero una demostración completa para **interfaces administrativamente caídas**: caso persistente, un equipo, verificación inicial, propuesta sustentada, resultado posterior y resumen de cierre o derivación. Añadir continuidad y fuentes a ese recorrido antes de extenderlo a todos los temas.

Ese alcance aprovecha el conocimiento existente y permite mostrar una mejora concreta: NetAssist acompaña y documenta la resolución de un problema del laboratorio, además de responder preguntas.

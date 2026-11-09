# Resultado de la evaluación de la fase 6

Ejecución reproducible con dobles de proveedor e índice (sin red).

**Escenarios superados: 28/28** · latencia local mediana 27.2 ms, p95 90.2 ms, máxima 271.0 ms (sin red ni modelo).

| Área | Superados |
|---|---|
| Configuración | 7/7 |
| Topología | 4/4 |
| Continuidad | 5/5 |
| Proveedores | 5/5 |
| Conocimiento | 4/4 |
| Seguridad | 3/3 |

| # | Área | Escenario | Resultado | Detalle | ms |
|---|---|---|---|---|---|
| CF1 | Configuración | Datos completos: comandos y verificaciones deterministas | ✅ | HTTP 200; 18 comandos; estado reglas_aprobadas | 271 |
| CF2 | Configuración | Modelo ausente: se pide el dato y no se llama a la IA | ✅ | HTTP 422; faltantes ['Modelo del switch']; llamadas IA 0 | 9 |
| CF3 | Configuración | VLAN inválida (4095) rechazada sin llamar a la IA ni guardar el caso | ✅ | HTTP 422; sin caso guardado | 13 |
| CF4 | Configuración | Puerto repetido en dos VLAN rechazado | ✅ | HTTP 422 | 4 |
| CF5 | Configuración | Objetivo fuera del alcance (OSPF): advertencia explícita | ✅ | HTTP 200; 3 advertencias | 23 |
| CF6 | Configuración | Objetivo que excluye trunk/IP no genera falso aviso de alcance | ✅ | 2 advertencias, ninguna de alcance | 22 |
| CF7 | Configuración | Modelo distinto de 2960: advertencia, no bloqueo | ✅ | HTTP 200 | 23 |
| TP1 | Topología | Dos PC y un switch: nodos, enlaces y Mermaid | ✅ | 3 nodos, 2 enlaces | 23 |
| TP2 | Topología | Datos incompletos (puerto y host ausentes): se piden juntos | ✅ | HTTP 422; faltantes ['Fila 1: Puerto de acceso', 'Fila 2: Equipo conectado'] | 7 |
| TP3 | Topología | Sin IP declarada: no se inventa direccionamiento | ✅ | supuesto declarado; ninguna dirección IPv4 en la salida | 24 |
| TP4 | Topología | Enlace no declarado: solo aparecen los enlaces del formulario | ✅ | 2 enlaces declarados | 25 |
| CT1 | Continuidad | Reabrir el caso conserva datos y propuesta | ✅ | estado propuesta | 47 |
| CT2 | Continuidad | Misma salida pegada dos veces: no se duplica ni repite el paso | ✅ | 1 evidencia; omitidos 1 | 67 |
| CT3 | Continuidad | Hallazgo → corrección → resolución confirmada con historial | ✅ | con_hallazgos → coherente; 4 evidencias en historial | 90 |
| CT4 | Continuidad | Salida cortada: ambigua, pide aclaración y no afirma error | ✅ | estado requiere_aclaracion | 59 |
| CT5 | Continuidad | Informe exportable con comandos, fuentes y evidencias | ✅ | 4405 caracteres | 56 |
| PV1 | Proveedores | Primario caído: responde el respaldo | ✅ | llamadas {'gemini': 1, 'groq': 1} | 32 |
| PV2 | Proveedores | Primario devuelve respuesta vacía: responde el respaldo | ✅ | llamadas {'gemini': 1, 'groq': 1} | 30 |
| PV3 | Proveedores | Ambos caídos: se conserva la propuesta determinista y el caso | ✅ | estado propuesta_sin_explicacion; caso guardado True | 30 |
| PV4 | Proveedores | Solo el respaldo y captura: aviso de que no se analizó la imagen | ✅ | llamadas {'gemini': 1, 'groq': 1} | 151 |
| PV5 | Proveedores | Chat con ambos proveedores caídos: aviso fijo | ✅ | mensaje de contingencia | 4 |
| CN1 | Conocimiento | Fuente válida: las fuentes citadas existen en el corpus | ✅ | fuentes ['cisco_ios_basico.txt'] | 77 |
| CN2 | Conocimiento | Búsqueda del índice falla: la propuesta sigue, sin fuentes | ✅ | HTTP 200 | 30 |
| CN3 | Conocimiento | Índice no disponible: 503 y no se llama a la IA | ✅ | HTTP 503 | 4 |
| CN4 | Conocimiento | Diagnóstico disponible aunque el índice falle | ✅ | HTTP 200 | 32 |
| SG1 | Seguridad | Datos sensibles en el chat: bloqueo antes del proveedor | ✅ | llamadas IA 0 | 4 |
| SG2 | Seguridad | Datos sensibles en el formulario: no se guarda ni se envía | ✅ | HTTP 422 | 10 |
| SG3 | Seguridad | Otro usuario no accede al caso (404) ni lo ve listado | ✅ | códigos [404, 404, 404] | 42 |

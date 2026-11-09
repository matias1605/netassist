# Verificación de fase 1

Fecha: 9 de noviembre de 2026. Estado: completada para uso local de una instancia.

## Ejecución

```powershell
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
.venv/Scripts/python.exe -m compileall -q backend streamlit_app.py pruebas/automatizadas
node --check frontend/app.js
git diff --check
```

Resultado: **18 pruebas, OK** (2,380 s de ejecución de pruebas; no incluye importación inicial de dependencias). Compilación, sintaxis JavaScript y revisión de espacios: correctas. Suite en `automatizadas/test_fase1.py`; salida detallada en `resultado_fase1.txt`.

## Cobertura y evidencia

| Área | Casos comprobados | Resultado |
|---|---|---|
| Datos | IP privadas/documentación/máscaras, IPv6, IP inválidas y preguntas conceptuales permitidas; IP públicas y valores de credenciales bloqueados | Conforme |
| Historial | Dato bloqueado en usuario o asistente anterior; API, cadena compartida y ruta alternativa no llaman al proveedor | Conforme |
| Presupuesto | Lista vacía, más de 40 mensajes, mensaje mayor a 12000, total mayor a 48000, rol inválido y último turno incorrecto; límite exacto admitido | Conforme |
| Imágenes | PNG real admitido; firma truncada, base64 inválido, MIME incorrecto, exceso de tamaño/dimensiones y falta de confirmación rechazados | Conforme |
| Contexto | Seguimiento conserva VLAN, equipo y resultado previo en la consulta RAG; sin fichas relevantes no se completa artificialmente el corpus visual | Conforme |
| Respaldo | Primario correcto, primario fallido, respuesta vacía, ambos caídos; aviso visual ante respuesta de Groq | Conforme |
| Transporte | HTTP simulado: Gemini recibe imagen y clave en cabecera, sin clave en URL; Groq recibe texto y aviso, sin bytes de imagen | Conforme |
| Registros | Una excepción con un secreto ficticio no expone su contenido en el registro de contingencia | Conforme |
| Reindexación | Fallos de lectura, embeddings, inserción, colección incompleta, consulta y publicación; tras cada fallo el índice anterior sigue consultable | Conforme |
| Persistencia de referencia | Nueva generación publicada, referencia recuperada por otro servicio y arranque sin recalcular embeddings; generación anterior conservada | Conforme |
| Concurrencia | Bloqueo de archivo ocupado rechaza otra reconstrucción; corpus vacío conserva índice anterior | Conforme |
| API administrativa | Rechazo sin token, fallo controlado con token y salud del índice anterior conservada | Conforme |
| Compatibilidad | Dos acciones rápidas intactas, borradores sin datos bloqueados; prompt completo y corpus pasan la política de laboratorio | Conforme |

## Alcance y límites

- Proveedores simulados; ninguna llamada a Gemini o Groq ni claves reales utilizadas por la suite. Transporte con `httpx.MockTransport`.
- Chroma real en memoria, modelo de embeddings determinista y directorio temporal para referencia/bloqueo. Sin descarga de modelos ni modificación del índice del proyecto. No se verificó recuperación de un corte de energía ni durabilidad física del almacenamiento.
- La política distingue rangos permitidos, no la procedencia real de una dirección privada. El usuario debe sustituir los datos reales localmente. No hay anonimización automática de texto ni OCR/anonimización visual.
- Las reglas de precisión y concisión permanecen en el prompt; no hay validador posterior de estilo o corrección de respuestas.
- Sin prueba visual de web/Streamlit, carga, proveedores reales, simulador ni equipos Cisco. La revisión de interfaz en esta fase fue de código y sintaxis.
- Las generaciones previas se retienen sin limpieza automática. Las instancias abiertas siguen con su referencia hasta reiniciar; coordinación prevista para almacenamiento local compartido.
- Antes de publicar tras un proxy, configurar `REINDEX_ADMIN_TOKEN`. Para incorporar el cambio DNS del corpus, ejecutar una reindexación administrativa.

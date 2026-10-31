# NetAssist

Prototipo educativo de asistente de soporte para Cisco IOS. Usa FastAPI, recuperación local de manuales (RAG), Gemini con failover a Groq y una interfaz web en HTML, CSS y JavaScript sin frameworks. El soporte para MikroTik RouterOS queda como trabajo futuro.

## Estructura

```text
netassist/
├── backend/
│   ├── main.py
│   ├── llm.py
│   ├── rag.py
│   ├── prompts.py
│   ├── config.py
│   ├── __init__.py
│   └── requirements.txt
├── docs/
│   └── cisco_ios_basico.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .env.example
├── .gitignore
└── README.md
```

## Requisitos previos

- Python 3.11 o superior.
- Acceso a Internet durante la instalación y la primera descarga del modelo de embeddings.
- Claves de Google AI Studio y Groq para obtener respuestas de LLM y habilitar el failover.

## Instalación y ejecución

1. Abre una terminal en la carpeta `netassist`.
2. Crea y activa un entorno virtual:

   **Windows PowerShell**
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS o Linux**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. Instala las dependencias del backend:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r backend/requirements.txt
   ```

4. Copia `.env.example` como `.env` y configura las claves, modelos y contacto humano:

   **Windows PowerShell**
   ```powershell
   Copy-Item .env.example .env
   ```

   **macOS o Linux**
   ```bash
   cp .env.example .env
   ```

   Completa `GEMINI_API_KEY` y `GEMINI_MODEL` para Gemini, y `GROQ_API_KEY` y `GROQ_MODEL` para Groq. NetAssist intenta primero Gemini y usa Groq ante errores o timeout. Si un proveedor no se configura, se intentará el otro. Obtén las claves en [Google AI Studio](https://aistudio.google.com/) y [Groq Console](https://console.groq.com/). Los nombres de modelo son configurables; usa modelos habilitados para tus cuentas y APIs.

5. Coloca manuales `.txt` o `.pdf` en `docs/`. El prototipo incluye un TXT de ejemplo con fichas de Cisco. Los PDFs se indexan usando el texto que pueda extraerse de sus páginas; documentos escaneados requieren OCR previo.
6. Inicia el backend desde la carpeta `netassist`:

   ```bash
   python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```

   Al primer inicio se descarga el modelo multilingüe de embeddings y se genera la base ChromaDB local en `backend/chroma_db/`. La inicialización puede tardar varios minutos. Comprueba el estado en `http://localhost:8000/health`.

7. En otra terminal, sirve el frontend en el origen permitido:

   **Windows PowerShell**
   ```powershell
   cd frontend
   py -3.11 -m http.server 5500
   ```

   **macOS o Linux**
   ```bash
   cd frontend
   python3 -m http.server 5500
   ```

8. Abre `http://localhost:5500` en el navegador. Si cambias el host o puerto del frontend, actualiza `FRONTEND_ORIGIN` en `.env` y reinicia el backend.

## Endpoints

- `POST /chat`: recibe `{ "messages": [{ "role": "user|assistant", "content": "..." }] }`, recupera hasta cuatro fragmentos relevantes y devuelve `{ "reply": "...", "contact": "..." }`.
- `POST /reindexar`: reconstruye el índice desde los documentos actuales de `docs/`.
- `GET /health`: informa el estado de la API y del índice RAG.
- `GET /contacto`: devuelve el contacto de derivación configurado.

El frontend persiste el historial en `localStorage` y lo envía completo en cada turno. No se guardan conversaciones en el backend. No ingreses contraseñas ni datos sensibles: el historial queda en ese navegador hasta pulsar **Nueva conversación**.

## RAG y relevancia

El backend acepta `.txt` y `.pdf`, genera embeddings localmente e indexa en ChromaDB. En los `.txt` con fichas separadas por una línea `---`, cada ficha se indexa como un fragmento independiente (una ficha, un resultado); el resto del texto y los PDFs se dividen en fragmentos de 500 palabras con 50 de solapamiento. En cada turno consulta un máximo de cuatro fragmentos. `RAG_DISTANCE_THRESHOLD` configura el umbral de distancia coseno para tratar un resultado como relevante; ajústalo si el conjunto de manuales requiere otra calibración. Sin fragmentos relevantes, la instrucción del sistema impide inventar referencias.

## Detección de datos sensibles

Antes de llamar al modelo, el backend revisa el último mensaje del usuario y, si detecta una dirección IP o palabras como «password», «secret» o «contraseña», responde con un aviso y no envía nada al LLM. El frontend hace la misma comprobación para avisar de inmediato. Trabaja siempre con valores de ejemplo (por ejemplo, `192.168.X.1`), nunca con IPs o credenciales reales.

## Casos de prueba QA

1. **Flujo ideal Cisco (interfaz):** pregunta por una interfaz en `administratively down` y proporciona modelo/versión; la respuesta debe citar la ficha y sugerir `no shutdown` con verificación en sintaxis IOS.
2. **Flujo ideal Cisco (conectividad):** reporta conectividad fallida; la guía debe respetar el orden de capa física, IP y enrutamiento, usando los comandos de verificación del manual IOS.
3. **Memoria de la conversación:** ejecuta una verificación, envía su resultado y pregunta por el siguiente paso; el asistente no debe volver a proponer como pendiente el comando ya probado.
4. **Faltan datos del equipo:** pregunta por un cambio de configuración sin marca, modelo ni versión; NetAssist debe preguntar esos datos antes de proponer el cambio.
5. **Advertencia de riesgo:** consulta cómo reiniciar o cambiar acceso remoto; la respuesta debe advertir el riesgo antes del comando y recomendar respaldo.
6. **Derivación humana:** reporta una falla física o un caso que persiste tras varios intentos; la respuesta debe recomendar contacto y mostrar la información configurada.
7. **Failover con API primaria caída:** simula error o timeout de Gemini; la solicitud debe intentar Groq y responder sin revelar claves.
8. **Todas las APIs caídas / error de servicio:** simula fallos en Gemini y Groq o detén el backend; la interfaz debe mostrar un mensaje amable y una vía de contacto humano, sin quedarse en estado «escribiendo».

## Límites del prototipo

- Los manuales de ejemplo son referencias introductorias, no sustituyen la documentación oficial ni una validación en laboratorio.
- La búsqueda semántica y su umbral deben validarse con el corpus de la institución.
- No ejecutes comandos de cambio sin verificar modelo, versión, topología, permisos y respaldo.

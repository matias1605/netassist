# NetAssist

Prototipo educativo de asistente de soporte para Cisco IOS. Usa recuperación local de manuales (RAG con ChromaDB), orquestación con LangChain, Gemini con failover a Groq, y dos interfaces: una app en Streamlit (desplegable en Streamlit Community Cloud) y una web en HTML, CSS y JavaScript servida por FastAPI. El soporte para MikroTik RouterOS queda como trabajo futuro.

## Estructura

```text
netassist/
├── backend/
│   ├── main.py
│   ├── cadena.py
│   ├── llm.py
│   ├── rag.py
│   ├── prompts.py
│   ├── config.py
│   ├── seguridad.py
│   ├── __init__.py
│   └── requirements.txt
├── docs/
│   └── cisco_ios_basico.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── streamlit_app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Requisitos previos

### Inicio local preparado en Windows

Haz doble clic en **Iniciar NetAssist.cmd** y abre `http://localhost:8501`.
Para usar la interfaz HTML con FastAPI, ejecuta `& '.\Iniciar NetAssist.cmd' -Interfaz Web`
desde PowerShell y abre `http://localhost:5500`.
Detén la aplicación con Ctrl+C en su terminal.

La instalación local usa Python en `.runtime/`, las librerías en `.venv/`,
los modelos en `.cache/` y ChromaDB en `backend/chroma_db/`.
No requiere instalar un servidor de base de datos ni modificar el PATH global.
Los archivos de inicio configuran las cachés únicamente para la aplicación.
Completa las claves de Gemini o Groq en `.env` para habilitar las respuestas del chat.
`requirements-local.txt` incluye las dependencias de ambas interfaces y ajustes de
compatibilidad; `requirements-local.lock.txt` registra las versiones instaladas.
Para reinstalarlas en este entorno sin instalar paquetes globales:

```powershell
.\.runtime\uv\uv.exe pip install --python .venv/Scripts/python.exe -r requirements-local.lock.txt
```

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

## Interfaz Streamlit y despliegue

Además de la web en HTML/JS, NetAssist tiene una interfaz en **Streamlit** (`streamlit_app.py`). Muestra una página del laboratorio con el chat como **burbuja flotante** abajo a la derecha: se abre y se cierra con el botón 💬. Las dos usan la misma orquestación con **LangChain** (`backend/cadena.py`): bloqueo de datos sensibles → recuperación de fichas en ChromaDB → Gemini, con Groq como respaldo (política compartida de respaldo).

**En local** (con el `.env` configurado):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Abre `http://localhost:8501`. No hace falta arrancar FastAPI ni el servidor del frontend.

**En Streamlit Community Cloud:**

1. Entra a https://share.streamlit.io con tu cuenta de GitHub.
2. *Create app* → elige el repositorio, la rama `main` y el archivo `streamlit_app.py`.
3. En *Advanced settings*, elige **Python 3.11** y pega en *Secrets* el contenido de `.streamlit/secrets.toml.example` con tus claves reales.
4. *Deploy*. El primer arranque tarda varios minutos: instala PyTorch (versión CPU) y descarga el modelo de embeddings.

Las claves van solo en los Secrets de Streamlit o en `.env`; nunca en el repositorio.

## Endpoints

- `GET /acciones`: devuelve borradores de configuración y topología con el escenario ficticio compartido de `docs/datos_prueba_vlan.json`.
- `POST /chat`: recibe `{ "messages": [{ "role": "user|assistant", "content": "..." }] }`, recupera hasta cuatro fragmentos relevantes y devuelve `{ "reply": "...", "contact": "..." }`.
- `POST /reindexar`: reconstruye el índice desde los documentos actuales de `docs/`.
- `GET /health`: informa el estado de la API y del índice RAG.
- `GET /contacto`: devuelve el contacto de derivación configurado.

El frontend persiste el historial en `localStorage` y lo envía completo en cada turno. No se guardan conversaciones en el backend. No ingreses contraseñas ni datos sensibles: el historial queda en ese navegador hasta pulsar **Nueva conversación**.

## RAG y relevancia

El backend acepta `.txt` y `.pdf`, genera embeddings localmente e indexa en ChromaDB. En los `.txt` con fichas separadas por una línea `---`, cada ficha se indexa como un fragmento independiente (una ficha, un resultado); el resto del texto y los PDFs se dividen en fragmentos de 500 palabras con 50 de solapamiento. En cada turno consulta un máximo de cuatro fragmentos usando el último mensaje y una ventana acotada de los seis turnos anteriores. Las capturas no agregan fichas sin relevancia medida. `RAG_DISTANCE_THRESHOLD` configura el umbral de distancia coseno para tratar un resultado como relevante; ajústalo si el conjunto de manuales requiere otra calibración. Sin fragmentos relevantes, la instrucción del sistema impide inventar referencias.

## Detección de datos sensibles

Ambas interfaces aplican la misma política de laboratorio antes de recuperar fichas o llamar al proveedor: se revisan todos los mensajes, incluidos los del asistente. Se permiten direcciones privadas, loopback, IPv6 local/documentación, IPv4 de documentación y máscaras válidas. Las IP fuera de ese alcance y los valores de credenciales (`password`, `secret`, `token`, `api_key`, etc.) bloquean el envío completo. Preguntas conceptuales como «¿Qué hace enable secret?» están permitidas. Esto es un filtro heurístico, no un detector universal de información personal ni una prueba de que una IP privada sea ficticia.

Usa solo datos ficticios: sustituye localmente los datos reales por ejemplos antes de pegarlos. No se altera automáticamente una evidencia ni se inventan direcciones. Si un turno anterior está bloqueado, corrígelo o inicia una conversación nueva. Las capturas requieren confirmar que se revisaron y eliminaron datos reales y credenciales; el sistema valida el archivo, pero no realiza OCR ni anonimización visual. La confirmación no certifica el contenido.

Límites compartidos: 40 mensajes, 12000 caracteres por mensaje y 48000 en total; se rechaza el exceso sin truncar evidencias. Imágenes PNG/JPEG/WEBP estáticas, decodificables, hasta 4 MB y 16 millones de píxeles. Cuando Groq responde a una consulta con captura se antepone un aviso explícito de que solo usa texto.

## Índice seguro y pruebas de fase 1

Al iniciar se reutiliza el índice vigente. `POST /reindexar` prepara y consulta una colección nueva antes de publicar `backend/chroma_db/indice_activo.json` mediante reemplazo atómico. Si falla lectura, embeddings, escritura o publicación, conserva la generación anterior. Un bloqueo de archivo coordina reconstrucciones locales; FastAPI realiza este trabajo fuera del bucle de atención. Las generaciones anteriores se conservan para lectores activos y aún no tienen limpieza automática; otras instancias abiertas conservan su generación hasta reiniciarse.

Sin `REINDEX_ADMIN_TOKEN`, reindexar solo acepta conexiones de loopback. Para acceso remoto o detrás de un proxy, configura ese secreto y envía la cabecera `X-Admin-Token`; nunca lo incluyas en la interfaz pública.

Regresiones locales (sin proveedores ni descarga de modelos):

```powershell
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
```

Ver resultados y límites en `pruebas/verificacion_fase1.md`.

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

## Acciones rápidas y próximas fases

Ambas interfaces incluyen **Generar configuración** y **Generar topología** con datos de prueba de VLAN. Los botones cargan una solicitud editable; revisa los datos y pulsa **Enviar** o **Enviar a IA**. No ejecutan comandos ni verifican equipos. En la web, envía o borra el borrador existente antes de cargar otro ejemplo; en Streamlit puedes descartarlo.

La IA tiene instrucciones de responder de forma concisa y precisa, usando comandos por equipo, verificaciones y advertencias breves. Esta guía de respuesta no sustituye validadores ni pruebas en laboratorio.

El alcance, los entregables y los criterios de aceptación se encuentran en [FASES_IMPLEMENTACION.md](FASES_IMPLEMENTACION.md). El primer escenario previsto es VLAN con puertos de acceso; la persistencia de casos y los validadores siguen pendientes.

## Espacio de laboratorio (fase 2)

En web y Streamlit puedes preparar una práctica de VLAN con un switch y hasta 16 conexiones:

1. Completa el nombre, alias, modelo/IOS, VLAN, puertos, equipos conectados y requisitos, o carga el ejemplo compartido.
2. Pulsa **Revisar datos**. Se muestran juntos los campos faltantes y la solicitud que se enviará; este paso no consulta a la IA.
3. Confirma la revisión y pulsa **Generar propuesta**. El resultado queda identificado como pendiente de verificación en laboratorio.

Editar datos descarta la revisión y el resultado anteriores; debes revisarlos nuevamente. El modelo y la versión de IOS son obligatorios para configuración. La topología permite dejarlos vacíos. El chat y las acciones rápidas siguen disponibles por separado.

Este formulario comprueba campos y límites de tamaño. Los validadores técnicos de VLAN/interfaces y los casos persistentes corresponden a la fase 3. No ejecuta comandos ni marca una práctica como comprobada. El resultado solo permanece en la página/sesión actual.

API adicional: `GET /laboratorio/ejemplo`, `POST /laboratorio/preparar` (tarea estructurada) y `POST /laboratorio/generar` (`tarea` y `confirmado`). Ambas rutas de escritura utilizan las reglas compartidas de laboratorio.

Pruebas de servicios y Streamlit:

```powershell
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
```

Smoke opcional con Chrome instalado y la dependencia de `requirements-pruebas.txt`:

```powershell
.runtime/uv/uv.exe pip install --python .venv/Scripts/python.exe -r requirements-pruebas.txt
.venv/Scripts/python.exe -m pruebas.verificar_web_fase2
```

Resultados, capturas y límites en `pruebas/verificacion_fase2.md`.

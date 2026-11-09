# NetAssist — Guía del proyecto

Asistente de IA generativa para soporte de **redes Cisco IOS**. Combina un modelo de lenguaje (LLM) con recuperación local de manuales (RAG) para orientar en el diagnóstico y la configuración de equipos Cisco, con controles de seguridad y derivación a un humano.

> Prototipo académico (USMP). Usa datos de ejemplo; no se conecta a equipos reales ni reemplaza la validación de un técnico.

---

## 1. ¿Qué hace?

- Responde consultas de redes Cisco (interfaces, rutas, VLAN, DNS, SVI) con un **formato fijo**: *Posible causa → Pasos a verificar → Comando sugerido → Aviso*.
- Basa las respuestas en **fichas de manuales** (no inventa comandos; si no sabe, lo dice).
- **Genera la topología** del caso como diagrama (Mermaid) cuando intervienen dos o más equipos, marcando el enlace o la interfaz con falla. Si el diagrama no se puede dibujar, se muestra como código.
- **Acepta imágenes** (PNG, JPG o WEBP, hasta 4 MB) con el botón del clip o pegándolas con `Ctrl + V`: por ejemplo, una captura de Packet Tracer o de un error. Solo Gemini puede verlas; si responde el respaldo (Groq), avisa que no pudo analizar la imagen.
- **Bloquea datos sensibles** (IP reales, contraseñas) antes de enviarlos al modelo. En las imágenes no puede detectarlos: tápalos o recórtalos antes de subirlas.
- Si un proveedor de IA falla, **cambia a otro automáticamente** (failover).
- Deriva a un docente/técnico cuando el caso lo amerita.

---

## 2. ¿Cómo funciona? (arquitectura)

```
Navegador (frontend)              Servidor (backend Python)
┌───────────────────┐  POST /chat ┌──────────────────────────────┐
│ Chat web          │ ──────────► │ FastAPI                      │
│ HTML/CSS/JS       │             │  ├─ Detección datos sensibles│
│                   │ ◄────────── │  ├─ RAG (ChromaDB + embeddings)
└───────────────────┘   respuesta │  ├─ Prompt del sistema       │
                                  │  └─ LLM: Gemini → Groq (resp.)│
                                  └──────────────────────────────┘
                                        ▲
                                   docs/ (fichas Cisco .txt)
```

1. El usuario envía una consulta desde la web.
2. El backend revisa si hay **datos sensibles**; si los hay, responde con un aviso y no llama al modelo.
3. El **RAG** busca en las fichas los fragmentos más relevantes (ChromaDB + embeddings locales).
4. Se arma el **prompt** con ese contexto y se llama al LLM: primero **Gemini**, y si falla, **Groq**.
5. Se devuelve la respuesta al navegador, que la muestra con formato (bloques de código, etc.).

Los pasos 2 a 4 están encadenados con **LangChain** en `backend/cadena.py`. La misma cadena la usan la web (vía FastAPI) y la app de **Streamlit** (`streamlit_app.py`).

---

## 3. Requisitos

- **Python 3.11** (ojo: 3.15 u otras versiones muy nuevas **no** sirven, las dependencias no son compatibles).
- Conexión a internet (la primera vez descarga el modelo de embeddings).
- Una **clave de Google Gemini** (gratis) y, recomendado, una de **Groq** (gratis) como respaldo.

Claves:
- Gemini: https://aistudio.google.com/apikey
- Groq: https://console.groq.com → API Keys

---

## 4. Instalación (Windows, paso a paso)

1. **Instalar Python 3.11** (si no lo tienes). Con el gestor `py`:
   ```powershell
   py install 3.11
   py -3.11 --version
   ```
   (Debe decir `Python 3.11.x`.)

2. **Clonar el repositorio** y entrar a la carpeta:
   ```powershell
   git clone https://github.com/matias1605/netassist.git
   cd netassist
   ```

3. **Crear e activar el entorno virtual:**
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   > Si PowerShell bloquea el script: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` y repite.

4. **Instalar dependencias:**
   ```powershell
   python -m pip install -r backend/requirements.txt
   ```

---

## 5. Configuración (`.env`)

Cada persona debe crear su propio `.env` con **sus** claves (el `.env` no se sube al repo).

```powershell
Copy-Item .env.example .env
notepad .env
```

Completa al menos `GEMINI_API_KEY`. Recomendado también `GROQ_API_KEY` (respaldo). Sin comillas ni espacios:

```
GEMINI_API_KEY=tu_clave_de_gemini
GEMINI_MODEL=gemini-3.8-flash
GROQ_API_KEY=tu_clave_de_groq
GROQ_MODEL=openai/gpt-oss-20b
FRONTEND_ORIGIN=http://localhost:5500
SUPPORT_CONTACT=Docente de laboratorio: soporte@ejemplo.edu | Extension 1234
```

> Los nombres de modelo cambian con el tiempo. Verifícalos en Google AI Studio y en la consola de Groq si algo falla.

---

## 6. Arrancar el proyecto (dos terminales)

**Terminal 1 — backend:**
```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
La primera vez tarda unos minutos (descarga el modelo de embeddings). Espera `Application startup complete`.
Comprueba el estado en: http://localhost:8000/health

**Terminal 2 — frontend:**
```powershell
cd frontend
py -3.11 -m http.server 5500
```

Abre el chat en: **http://localhost:5500**

**Alternativa — interfaz Streamlit (una sola terminal):**
```powershell
.\.venv\Scripts\Activate.ps1
streamlit run streamlit_app.py
```
Abre **http://localhost:8501**. Para publicarla en Streamlit Community Cloud, sigue la sección *Interfaz Streamlit y despliegue* del `README.md`.

---

## 7. Cómo usarlo

Escribe tu problema de red. Ejemplos:
- *"La interfaz G0/1 aparece como administratively down, ¿cómo la activo?"*
- *"No tengo conectividad entre dos redes, el ping falla."*
- *"¿Cómo configuro una VLAN en el switch?"*

El botón **"Nueva conversación"** limpia el historial. **"Hablar con un docente/técnico"** muestra el contacto de derivación.

---

## 8. Endpoints (API)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/chat` | Recibe el historial y devuelve `{ reply, contact }` |
| POST | `/reindexar` | Reconstruye el índice desde `docs/` |
| GET | `/health` | Estado de la API y del índice RAG |
| GET | `/contacto` | Contacto de derivación configurado |

---

## 9. Estructura del proyecto

```
netassist/
├── backend/
│   ├── main.py          # API FastAPI y endpoints
│   ├── cadena.py        # Orquestación con LangChain
│   ├── llm.py           # Gemini + Groq con failover
│   ├── rag.py           # Indexado y búsqueda (ChromaDB)
│   ├── prompts.py       # Prompt del sistema (comportamiento)
│   ├── seguridad.py     # Detección de datos sensibles
│   ├── config.py        # Lectura de variables de entorno
│   └── requirements.txt
├── docs/
│   └── cisco_ios_basico.txt   # Fichas de conocimiento (RAG)
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── pruebas/
│   └── casos_de_prueba.md     # 20 casos de evaluación
├── .streamlit/                # Tema y ejemplo de Secrets
├── streamlit_app.py           # Interfaz Streamlit
├── requirements.txt           # Dependencias para Streamlit Cloud
├── .env.example
└── README.md
```

---

## 10. Agregar o editar conocimiento (fichas)

El RAG lee los `.txt` y `.pdf` de `docs/`. Para los `.txt`, cada **ficha** se separa con una línea `---` y usa este formato:

```
PROBLEMA: ...
SÍNTOMA: ...
CAUSA: ...
COMANDOS: ...
VERIFICACIÓN: ...
ADVERTENCIA: ...
---
PROBLEMA: (siguiente ficha)
...
```

Tras agregar o cambiar fichas, reindexa sin reiniciar:
```powershell
curl -X POST http://localhost:8000/reindexar
```

---

## 11. Pruebas y evaluación

En `pruebas/casos_de_prueba.md` hay **20 consultas** (12 normales, 4 fuera de tema, 2 con datos sensibles, 2 sin respuesta en fichas) con su respuesta esperada. Ejecuta cada una contra el bot y rellena: respuesta, ¿correcta?, ¿alucinó?, latencia. Metas: ≥ 80 % correctas y 0 comandos inventados en los casos críticos.

---

## 12. Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| "No pude obtener una respuesta…" | Gemini falló y no hay respaldo. Configura `GROQ_API_KEY` en `.env` y **reinicia el backend**. |
| Cambié el `.env` pero no surte efecto | El backend lee el `.env` al arrancar. Deténlo (Ctrl+C) y vuelve a iniciarlo. |
| Error 404 "model is no longer available" | El nombre del modelo cambió. Pon uno vigente en `.env` (ver AI Studio / Groq). |
| Aparece `@@NETASSIST_CODE_0@@` en el chat | JavaScript viejo en caché. Recarga con `Ctrl + F5`. |
| `py --version` instala una versión nueva (3.15) | Usa siempre `py -3.11`. Instálala con `py install 3.11`. |
| Adjunto una imagen y responde "no puedo ver la imagen" | Gemini estaba saturado (error 503) y respondió Groq, que no ve imágenes. Reintenta en un momento. |
| El backend no responde | Verifica que esté corriendo en el puerto 8000 y revisa `http://localhost:8000/health`. |

---

## 13. Seguridad

- Las **claves API** van solo en `.env` (ignorado por git), nunca en el código ni en el repositorio.
- No ingreses **contraseñas ni IP reales**: el sistema las detecta y bloquea; usa valores de ejemplo (p. ej. `192.168.X.1`).
- Las respuestas del asistente **deben verificarse** en laboratorio o simulador antes de aplicarlas en equipos reales.

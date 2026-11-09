# Rediseño de la interfaz Streamlit

La interfaz Streamlit (`http://127.0.0.1:8501`) adopta el diseño de la web HTML/JS
(`http://localhost:5500/#laboratorio`). Solo cambió la presentación: el RAG en ChromaDB, la
cadena de LangChain, los validadores, los casos y los informes son los mismos de siempre.

## Qué se hizo

| Archivo | Cambio |
|---|---|
| `estilos_streamlit.py` (nuevo) | CSS con la paleta teal/navy de la web, la mascota Nexo en SVG y los bloques HTML del encabezado y de las tarjetas. |
| `streamlit_app.py` | Usa los estilos nuevos; botón flotante con Nexo y su globo; cabecera del chat con avatar y "En línea"; Nexo como avatar del asistente. |
| `laboratorio_ui.py` | El laboratorio se reorganiza como en la web (ver abajo). La lógica no cambia. |
| `.streamlit/config.toml` | Tema: color principal `#14958a`, fondo `#f2f5f8`, campos blancos. |

### Estructura del laboratorio

1. Encabezado: «Aprende · Configura · Comprueba», «Tu próxima red empieza aquí.» y el sello «Cisco IOS».
2. Desplegables: «Probar con un ejemplo», «Mi clave de casos» y «Mis prácticas guardadas».
3. Tarjeta **01 · Prepara tu práctica**: nombre, alias y modelo del switch, y la tabla de grupos de puertos. Tipo de tarea, versión de IOS y objetivo quedan en «Más detalles».
4. Tarjeta **02 · Tu práctica**, con tres pestañas:
   - **Revisión**: revisar datos y generar propuesta.
   - **Configuración**: resultado, informe (.md) y archivar o restaurar el caso.
   - **Comprobaciones**: diagnóstico con evidencia a partir de las salidas del simulador.

## Cómo ejecutarlo

```bash
# Interfaz Streamlit (un solo proceso)
.venv/Scripts/python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501

# Web HTML/JS (backend + frontend)
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
.venv/Scripts/python.exe -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Si se editan módulos como `laboratorio_ui.py` con el servidor en marcha, hay que reiniciar
Streamlit para que los recargue. La primera carga tarda unos 30 s porque indexa las fichas.

## Pendiente

- **Probar «Generar propuesta»** de extremo a extremo: usa la IA (Gemini con Groq de respaldo) y no se
  ejecutó durante esta revisión; tampoco se enviaron mensajes al chat de Streamlit.
- **Correr las pruebas automáticas** (`pruebas/automatizadas`) y revisar que sigan en verde.
- **Llevar a Streamlit el flujo nuevo de Nexo** que hoy solo existe en la web: «Guardar y hablar con Nexo»
  (`guardar_practica`), el saludo con sugerencias, los datos del formulario como contexto del chat y el
  resumen de la sesión (`guardar_sesion`). Se dejó fuera a propósito: se pidió solo el diseño.
- **Barra lateral y barra superior** de la web: no se replicaron en Streamlit.
- **Grupos de puertos** como tarjetas «Grupo 1 / Grupo 2»: en Streamlit siguen siendo una tabla editable.
- **Revisar en móvil**: el CSS incluye ajustes para pantallas pequeñas, pero no se verificaron.
- Tras generar la propuesta hay que abrir la pestaña «Configuración» a mano (Streamlit no cambia de pestaña solo).

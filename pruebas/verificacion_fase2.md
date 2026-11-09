# Verificación de la fase 2

Fecha: 9 de noviembre de 2026. Estado: completada en el alcance local de formulario, revisión y panel de resultados.

## Resultados

- **31 pruebas automatizadas: OK**, en 4,066 s de ejecución de pruebas (sin importación inicial). Incluye las 18 regresiones de fase 1 y 13 pruebas nuevas de servicios, API y Streamlit.
- **Chrome, escritorio 1440 px y móvil 390 px: OK**, con API simulada. Sin errores JavaScript ni desbordamiento horizontal en móvil.
- Compilación Python, sintaxis de `app.js` y `laboratorio.js`, y revisión de espacios: sin errores.

## Cobertura

| Área | Evidencia |
|---|---|
| Ejemplo común | El mismo escenario y preparación se obtienen desde el servicio compartido; revisar no llama a la IA. |
| Campos faltantes | Modelo, IOS y puertos ausentes se informan juntos. Configuración incompleta no llega a la cadena; topología no inventa modelo/IOS. |
| Confirmación | Sin confirmación explícita no se genera. Web y Streamlit invalidan revisión y resultado cuando cambia un dato. |
| Resultados | Respuesta etiquetada como pendiente de verificación; validación técnica pendiente y comprobación no realizada. Respaldo total produce aviso sin propuesta. |
| Errores | Datos bloqueados no llegan a la IA; límites de filas/campos rechazados. API devuelve fallo controlado sin texto interno de excepción. Índice caído devuelve 503. |
| Streamlit | AppTest ejecuta revisar → confirmar → generar → editar; además faltantes, descarte y recarga del ejemplo. Sin excepciones de interfaz. |
| Web | Chrome ejecuta revisión, confirmación, generación simulada, edición, faltantes, descarte, ejemplo, añadir/quitar conexión, topología y fallo de generación con controles recuperados. |
| Compatibilidad | Las acciones de configuración y topología siguen preparando el borrador del chat. Se ejecutan también todas las pruebas de fase 1. |
| Adaptación visual | Capturas revisadas en escritorio y móvil de 390 px; campos legibles y flujo de una columna en móvil. |

## Reproducción

```powershell
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
.venv/Scripts/python.exe -m compileall -q backend laboratorio_ui.py streamlit_app.py pruebas/automatizadas
node --check frontend/app.js
node --check frontend/laboratorio.js
git diff --check
```

Para el navegador, instalar la dependencia opcional con el entorno local y disponer de Google Chrome:

```powershell
.runtime/uv/uv.exe pip install --python .venv/Scripts/python.exe -r requirements-pruebas.txt
.venv/Scripts/python.exe -m pruebas.verificar_web_fase2
```

El script abre un servidor temporal en loopback y lo cierra al terminar; la API se intercepta con datos ficticios. No se usa el índice local ni proveedores reales.

## Archivos de evidencia

- `automatizadas/test_fase2.py`: 13 pruebas nuevas.
- `resultado_fase2.txt`: ejecución completa de 31 pruebas.
- `verificar_web_fase2.py` y `resultado_web_fase2.txt`: recorrido de navegador.
- `evidencias/fase2-web-escritorio.png`: propuesta simulada en el panel de resultados.
- `evidencias/fase2-web-movil.png`: revisión y error recuperable en móvil, con acciones rápidas conservadas.

## Límites

Se revisan presencia y tamaño de campos, no rangos VLAN, sintaxis de interfaces, duplicación de puertos ni compatibilidad del modelo. El panel nunca marca una comprobación real. No hay persistencia de casos ni validación en simulador. La suite usa proveedores simulados; el navegador intercepta la API y bloquea el CDN, por lo que no prueba Mermaid ni la integración con un proveedor real. Streamlit se prueba mediante AppTest, sin revisión visual en navegador. Los resultados no certifican corrección técnica de comandos generados por IA.

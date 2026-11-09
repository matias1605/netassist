# Verificación de la fase 5

Fecha: 9 de noviembre de 2026. Estado: implementada y probada localmente. La separación por usuario usa una clave opaca, **no es autenticación**.

## Resultados

- **102 pruebas automatizadas: OK** (`pruebas/resultado_fase5.txt`): 86 previas y 16 nuevas en `test_fase5.py`.
- Chrome con API real y base temporal: caso generado y guardado con la clave del navegador; informe Markdown descargable; otra clave y la ausencia de clave reciben 404 y lista vacía; archivar desde la interfaz oculta el caso y «Incluir archivados» lo muestra.

## Cobertura

| Área | Evidencia |
|---|---|
| Aislamiento | Ocho operaciones del almacén y nueve rutas HTTP devuelven 404 a otra clave o sin clave, y no escriben nada. |
| Claves | Formato inválido → error/422; la base guarda solo la huella. |
| Compatibilidad | Base de la versión 2 migrada; casos sin propietario accesibles y adoptados al regenerar. |
| Estados | Filtro por estado, resumen en la lista (evidencias, comprobación), archivar/restaurar sin perder datos. |
| Informe | Sin propuesta ni evidencias; completo (requisitos, comandos, fuentes, explicación, comprobación, hallazgos con `E<n>`); bloques de código seguros; evidencias obsoletas; nombre de archivo sin acentos ni `/`. |
| API y UI | Flujo lista → informe → archivar; CORS admite `X-Usuario`; Streamlit: la clave de sesión separa casos y una clave inválida se informa. |

## Reproducción

```powershell
.venv/Scripts/python.exe -m unittest discover -s pruebas/automatizadas -v
```

## Pendiente

- Probar desde un segundo navegador real usando la misma clave para confirmar el acceso a los casos.
- Si se publica, servir por HTTPS y sustituir la clave por autenticación real.

"""Smoke de navegador con API interceptada; captura de datos ficticios, sin IA real."""
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright
from backend.acciones import obtener_acciones
from backend.laboratorio import TareaLaboratorio, ejemplo_laboratorio, preparar_tarea

ROOT = Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass



def main():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(ROOT / "frontend")))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    estados = {"generaciones": 0, "error": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        errores = []
        page.on("pageerror", lambda error: errores.append(str(error)))
        page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
        def api(route):
            path = route.request.url.split("8000")[-1]
            body = route.request.post_data_json
            try:
                if path == "/acciones":
                    data = obtener_acciones()
                elif path == "/contacto":
                    data = {"contact": "Docente de laboratorio"}
                elif path == "/laboratorio/ejemplo":
                    data = ejemplo_laboratorio()
                elif path == "/laboratorio/preparar":
                    data = preparar_tarea(TareaLaboratorio(**body))
                elif path == "/laboratorio/generar":
                    if estados["error"]:
                        route.fulfill(status=503, json={"detail": "Proveedor simulado no disponible."}, headers={"Access-Control-Allow-Origin": "*"})
                        return
                    estados["generaciones"] += 1
                    data = {**preparar_tarea(TareaLaboratorio(**body["tarea"])), "estado": "respuesta_generada", "respuesta": "**Propuesta de laboratorio:** SW1\n```cisco\nshow vlan brief\n```\nVerifica los puertos en el simulador."}
                else:
                    raise AssertionError(path)
                route.fulfill(json=data, headers={"Access-Control-Allow-Origin": "*"})
            except ValueError as error:
                route.fulfill(status=422, json={"detail": str(error)}, headers={"Access-Control-Allow-Origin": "*"})
        page.route("http://localhost:8000/**", api)
        page.goto(f"http://127.0.0.1:{servidor.server_port}")
        page.get_by_text("Ejemplo ficticio cargado.", exact=False).wait_for()
        assert estados["generaciones"] == 0
        page.get_by_role("button", name="Revisar datos", exact=True).click()
        page.get_by_text("Campos completos. Revisa", exact=False).wait_for()
        assert page.locator("#lab-generate").is_disabled()
        page.locator("#lab-confirm").check()
        page.locator("#lab-generate").click()
        page.get_by_text("Respuesta generada · Propuesta", exact=False).wait_for()
        assert estados["generaciones"] == 1
        assert "show vlan brief" in page.locator("#lab-result").inner_text()
        page.screenshot(path=str(ROOT / "pruebas/evidencias/fase2-web-escritorio.png"), full_page=True)
        page.locator('[name="alias"]').fill("SW_EDITADO")
        assert page.locator("#lab-review").is_hidden()
        assert page.locator("#lab-result").is_hidden()
        assert not page.locator("#lab-confirm").is_checked()
        page.locator('[name="modelo"]').fill("")
        page.get_by_role("button", name="Revisar datos", exact=True).click()
        page.get_by_text("Completa estos datos: Modelo", exact=False).wait_for()
        assert page.locator("#lab-generate").is_disabled()
        page.get_by_role("button", name="Descartar revisión", exact=True).click()
        assert page.locator("#lab-review").is_hidden()
        page.get_by_role("button", name="Cargar ejemplo", exact=True).click()
        page.get_by_text("Ejemplo ficticio cargado.", exact=False).wait_for()
        page.get_by_role("button", name="Añadir conexión", exact=True).click()
        assert page.locator(".lab-port").count() == 3
        page.get_by_role("button", name="Quitar conexión", exact=True).last.click()
        assert page.locator(".lab-port").count() == 2
        page.locator('[name="tipo"]').select_option("topologia")
        page.locator('[name="modelo"]').fill("")
        page.locator('[name="ios"]').fill("")
        page.get_by_role("button", name="Revisar datos", exact=True).click()
        page.get_by_text("Campos completos. Revisa", exact=False).wait_for()
        page.locator("#lab-confirm").check()
        estados["error"] = True
        page.locator("#lab-generate").click()
        page.get_by_text("Proveedor simulado no disponible.", exact=True).wait_for()
        assert page.locator("#lab-result").is_hidden()
        assert not page.locator('[name="alias"]').is_disabled()
        assert page.get_by_role("button", name="Generar configuración", exact=True).count() == 1
        assert page.get_by_role("button", name="Generar topología", exact=True).count() == 1
        page.get_by_role("button", name="Generar topología", exact=True).click()
        assert "Mermaid" in page.locator("#message-input").input_value()
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#laboratorio-titulo").scroll_into_view_if_needed()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(ROOT / "pruebas/evidencias/fase2-web-movil.png"), full_page=True)
        assert not errores, errores
        browser.close()
    servidor.shutdown()
    print("OK: revisión sin IA, confirmación, generación, edición invalida, faltantes, descarte, ejemplo, conexiones, topología, fallo recuperable, acciones rápidas y ancho móvil 390 px; sin errores JavaScript.")

if __name__ == "__main__":
    main()

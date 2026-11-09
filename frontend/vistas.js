/* Vistas del espacio de trabajo, pestañas de la práctica y estado del servicio. Solo presentación. */
"use strict";

(() => {
  const shell = document.querySelector(".app-shell");
  const vistas = ["presentacion", "laboratorio", "practicas"];
  const titulos = { presentacion: "Presentación", laboratorio: "Laboratorio", practicas: "Mis prácticas" };

  function irAVista(nombre, { enfocar = true } = {}) {
    if (!vistas.includes(nombre)) nombre = "laboratorio";
    for (const v of vistas) document.getElementById(`vista-${v}`).hidden = v !== nombre;
    for (const a of document.querySelectorAll(".side-nav a[data-ir]")) {
      const activa = a.dataset.ir === nombre;
      a.classList.toggle("activo", activa);
      if (activa) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    }
    document.getElementById("crumb-actual").textContent = titulos[nombre];
    shell.dataset.vista = nombre;
    document.querySelector(".workspace").scrollTop = 0;
    if (enfocar) document.querySelector(`#vista-${nombre} h1`)?.setAttribute("tabindex", "-1");
    if (enfocar) document.querySelector(`#vista-${nombre} h1`)?.focus({ preventScroll: true });
    // app.js declara su propio «history» (historial del chat): se usa el del navegador explícitamente.
    if (location.hash !== `#${nombre}`) window.history.replaceState(null, "", `#${nombre}`);
  }
  window.irAVista = irAVista;

  document.addEventListener("click", (evento) => {
    const destino = evento.target.closest("[data-ir]");
    if (!destino) return;
    evento.preventDefault();
    irAVista(destino.dataset.ir);
  });
  irAVista(location.hash.slice(1) || "laboratorio", { enfocar: false });

  // ---------- Pestañas ----------
  const pestanas = [...document.querySelectorAll(".tab")];
  function abrirPestana(nombre) {
    for (const tab of pestanas) {
      const activa = tab.dataset.tab === nombre;
      tab.classList.toggle("activa", activa);
      tab.setAttribute("aria-selected", String(activa));
      tab.tabIndex = activa ? 0 : -1;
      document.getElementById(`panel-${tab.dataset.tab}`).hidden = !activa;
    }
  }
  pestanas.forEach((tab, i) => {
    tab.addEventListener("click", () => abrirPestana(tab.dataset.tab));
    tab.addEventListener("keydown", (evento) => {
      const paso = { ArrowRight: 1, ArrowLeft: -1 }[evento.key];
      if (!paso) return;
      const siguiente = pestanas[(i + paso + pestanas.length) % pestanas.length];
      abrirPestana(siguiente.dataset.tab);
      siguiente.focus();
    });
  });

  // ---------- Panel de la práctica: sigue al resto del laboratorio ----------
  const estado = document.getElementById("lab-result-state");
  const resultado = document.getElementById("lab-result");
  const vacio = document.getElementById("lab-result-empty");
  const pildora = document.getElementById("practica-estado");
  const nombre = document.querySelector('#laboratorio-form [name="nombre"]');

  function sincronizar() {
    const texto = estado.textContent.trim();
    const hayResultado = !resultado.classList.contains("hidden");
    estado.classList.toggle("hidden", !texto || /^Sin propuesta/i.test(texto));
    vacio.classList.toggle("hidden", hayResultado || (!!texto && !/^Sin propuesta/i.test(texto)));
    const abierta = nombre.value.trim();
    pildora.textContent = hayResultado ? "Propuesta generada" : (abierta ? "Borrador" : "Sin práctica abierta");
    pildora.classList.toggle("pill-activa", hayResultado || !!abierta);
  }
  const observador = new MutationObserver(sincronizar);
  observador.observe(estado, { childList: true, characterData: true, subtree: true });
  observador.observe(resultado, { attributes: true, attributeFilter: ["class"] });
  nombre.addEventListener("input", sincronizar);
  document.getElementById("laboratorio-form").addEventListener("change", sincronizar);
  sincronizar();

  // Al terminar una revisión o una propuesta, lleva a la pestaña que corresponde.
  new MutationObserver(() => {
    if (!document.getElementById("lab-review").classList.contains("hidden")) abrirPestana("comprob");
  }).observe(document.getElementById("lab-review"), { attributes: true, attributeFilter: ["class"] });
  new MutationObserver(() => {
    if (!resultado.classList.contains("hidden")) abrirPestana("config");
  }).observe(resultado, { attributes: true, attributeFilter: ["class"] });
  const diag = document.getElementById("lab-diag-box");
  new MutationObserver(() => {
    if (!diag.classList.contains("hidden") && document.getElementById("lab-result").classList.contains("hidden")) abrirPestana("comprob");
  }).observe(diag, { attributes: true, attributeFilter: ["class"] });

  // ---------- Estado del servicio ----------
  const indicador = document.getElementById("servicio-estado");
  const textoServicio = document.getElementById("servicio-texto");
  async function comprobarServicio() {
    let activo = false;
    try {
      const controlador = new AbortController();
      const limite = window.setTimeout(() => controlador.abort(), 4000);
      const respuesta = await fetch(`${API_BASE}/health`, { signal: controlador.signal });
      window.clearTimeout(limite);
      activo = respuesta.ok;
    } catch { /* sin conexión con el backend */ }
    indicador.classList.toggle("servicio-caido", !activo);
    textoServicio.textContent = activo ? "Servicio conectado" : "Servicio sin conexión";
  }
  comprobarServicio();
  window.setInterval(comprobarServicio, 30000);
})();

/* Nexo: mascota animada del chat. Solo presentación; no envía datos ni toca el historial.
   Nexo no tiene un globo aparte: responde en persona dentro del chat. Solo su avatar más reciente
   (la última respuesta o el indicador de "pensando") está "vivo"; si nadie le habla, se duerme. */
"use strict";

(() => {
  const shell = document.querySelector(".app-shell");
  const plantilla = document.getElementById("nexo-template");
  const practica = document.getElementById("chat-practica");
  const lanzador = document.getElementById("nexo-launcher");
  const mensajes = document.getElementById("messages");
  const escribiendo = document.getElementById("typing-indicator");
  const entrada = document.getElementById("message-input");
  const reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SUENO_MS = 25000;

  // Dibuja a Nexo en los huecos marcados con data-nexo que aún estén vacíos.
  function rellenar() {
    for (const destino of document.querySelectorAll("[data-nexo]")) {
      if (!destino.querySelector(".nexo")) destino.prepend(plantilla.content.cloneNode(true));
    }
  }
  rellenar();

  // ---------- Avatar vivo ----------
  let vivo = null;
  let animoBase = "neutral";
  let temporizadorAnimo = null;
  let temporizadorSueno = null;

  function avatarActual() {
    if (!escribiendo.classList.contains("hidden")) return escribiendo.querySelector(".message-avatar");
    const avatares = mensajes.querySelectorAll(".message-assistant .message-avatar");
    return avatares[avatares.length - 1] || null;
  }

  function enfocar() {
    const nuevo = avatarActual();
    if (nuevo === vivo) return;
    if (vivo) {
      vivo.classList.remove("vivo");
      vivo.dataset.mood = "quieto";
      const ojos = vivo.querySelector(".nexo-ojos");
      if (ojos) ojos.style.transform = "";
    }
    vivo = nuevo;
    if (vivo) vivo.classList.add("vivo");
  }

  function setAnimo(animo, duracionMs = 0) {
    if (vivo) vivo.dataset.mood = animo;
    const bot = lanzador.querySelector("[data-nexo]");
    if (bot) bot.dataset.mood = animo === "pensando" ? "neutral" : animo;
    window.clearTimeout(temporizadorAnimo);
    if (duracionMs) temporizadorAnimo = window.setTimeout(() => setAnimo(animoBase), duracionMs);
  }

  function despertar(animo = null, duracionMs = 1600) {
    window.clearTimeout(temporizadorSueno);
    if (animoBase === "dormido") animoBase = "neutral";
    setAnimo(animo || animoBase, animo ? duracionMs : 0);
    temporizadorSueno = window.setTimeout(dormir, SUENO_MS);
  }

  function dormir() {
    if (!escribiendo.classList.contains("hidden")) return;
    animoBase = "dormido";
    setAnimo("dormido");
  }

  // ---------- Ojos que siguen el cursor ----------
  if (!reducido) {
    window.addEventListener("pointermove", (evento) => {
      if (!vivo || ["dormido", "pensando"].includes(vivo.dataset.mood)) return;
      const ojos = vivo.querySelector(".nexo-ojos");
      const caja = vivo.getBoundingClientRect();
      if (!ojos || !caja.width) return;
      const dx = evento.clientX - (caja.left + caja.width / 2);
      const dy = evento.clientY - (caja.top + caja.height * 0.42);
      const distancia = Math.hypot(dx, dy) || 1;
      const alcance = Math.min(1, distancia / 260);
      ojos.style.transform = `translate(${((dx / distancia) * 4 * alcance).toFixed(2)}px, ${((dy / distancia) * 3 * alcance).toFixed(2)}px)`;
    });
  }

  // ---------- El usuario le habla ----------
  entrada.addEventListener("focus", () => despertar("atento", 1800));
  entrada.addEventListener("input", () => despertar());

  // ---------- Pensando ----------
  new MutationObserver(() => {
    enfocar();
    if (!escribiendo.classList.contains("hidden")) {
      animoBase = "pensando";
      window.clearTimeout(temporizadorSueno);
      setAnimo("pensando");
    } else if (animoBase === "pensando") {
      animoBase = "neutral";
    }
  }).observe(escribiendo, { attributes: true, attributeFilter: ["class"] });

  // ---------- Responde ----------
  new MutationObserver((cambios) => {
    rellenar();
    enfocar();
    for (const cambio of cambios) {
      for (const nodo of cambio.addedNodes) {
        if (!(nodo instanceof HTMLElement) || !nodo.classList.contains("message-assistant")) continue;
        const texto = nodo.textContent || "";
        if (/no pude|no disponible|error/i.test(texto)) despertar("sorpresa", 1600);
        else despertar("habla", 1500);
      }
    }
  }).observe(mensajes, { childList: true });

  // ---------- Práctica abierta (cabecera) ----------
  const nombrePractica = document.querySelector('#laboratorio-form [name="nombre"]');
  function actualizarPractica() {
    const nombre = nombrePractica?.value.trim();
    practica.textContent = nombre ? `Práctica: ${nombre}` : "Sin práctica abierta";
  }
  nombrePractica?.addEventListener("input", actualizarPractica);
  for (const id of ["lab-status", "lab-missing", "lab-result-state"]) {
    const el = document.getElementById(id);
    if (el) new MutationObserver(actualizarPractica).observe(el, { childList: true, characterData: true, subtree: true });
  }

  // ---------- Abrir, minimizar y ampliar ----------
  function abrirChat() {
    shell.classList.remove("chat-cerrado");
    despertar("saluda", 1600);
    entrada.focus({ preventScroll: true });
  }
  function cerrarChat() {
    shell.classList.add("chat-cerrado");
    shell.classList.remove("chat-ampliado");
    lanzador.focus({ preventScroll: true });
  }
  document.getElementById("chat-minimize").addEventListener("click", cerrarChat);
  lanzador.addEventListener("click", abrirChat);
  document.getElementById("chat-expand").addEventListener("click", () => {
    const ampliado = shell.classList.toggle("chat-ampliado");
    const boton = document.getElementById("chat-expand");
    boton.setAttribute("aria-label", ampliado ? "Reducir chat" : "Ampliar chat");
    boton.title = ampliado ? "Reducir" : "Ampliar";
  });
  document.addEventListener("keydown", (evento) => {
    if (evento.key !== "Escape") return;
    if (shell.classList.contains("chat-ampliado")) shell.classList.remove("chat-ampliado");
    else if (!shell.classList.contains("chat-cerrado")) cerrarChat();
  });

  // ---------- Estado inicial ----------
  for (const avatar of mensajes.querySelectorAll(".message-avatar")) avatar.dataset.mood = "quieto";
  actualizarPractica();
  enfocar();
  despertar("saluda", 1700);
})();

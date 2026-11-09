/* Nexo: mascota animada del chat. Solo presentación; no envía datos ni toca el historial. */
"use strict";

(() => {
  const shell = document.querySelector(".app-shell");
  const plantilla = document.getElementById("nexo-template");
  const escenario = document.getElementById("nexo-stage");
  const bot = document.getElementById("nexo-bot");
  const globo = document.getElementById("nexo-speech");
  const practica = document.getElementById("chat-practica");
  const lanzador = document.getElementById("nexo-launcher");  const mensajes = document.getElementById("messages");
  const escribiendo = document.getElementById("typing-indicator");
  const entrada = document.getElementById("message-input");
  const reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Clona el dibujo en cada sitio marcado con data-nexo (cabecera, escenario y lanzador).
  for (const destino of document.querySelectorAll("[data-nexo]")) {
    destino.prepend(plantilla.content.cloneNode(true));
  }
  const ojosEscenario = bot.querySelector(".nexo-ojos");

  // ---------- Estado de ánimo ----------
  let temporizadorAnimo = null;
  let temporizadorSueno = null;
  let animoBase = "neutral";

  function setAnimo(animo, duracionMs = 0) {
    for (const el of document.querySelectorAll("[data-nexo]")) el.dataset.mood = animo;
    window.clearTimeout(temporizadorAnimo);
    if (duracionMs) temporizadorAnimo = window.setTimeout(() => setAnimo(animoBase), duracionMs);
  }

  function decir(texto, animo = null, duracionMs = 2600) {
    globo.classList.add("cambia");
    window.setTimeout(() => {
      globo.textContent = texto;
      globo.classList.remove("cambia");
    }, reducido ? 0 : 160);    if (animo) setAnimo(animo, duracionMs);
    despertar();
  }

  function despertar() {
    if (escenario.dataset.dormido === "1") {
      escenario.dataset.dormido = "0";
      setAnimo("sorpresa", 900);
    }
    window.clearTimeout(temporizadorSueno);
    temporizadorSueno = window.setTimeout(() => {
      if (!escribiendo.classList.contains("hidden")) return;
      escenario.dataset.dormido = "1";
      setAnimo("dormido");
      globo.textContent = "Zzz… Escríbeme cuando me necesites.";
    }, 60000);
  }

  // ---------- Ojos que siguen el cursor ----------
  if (!reducido) {
    window.addEventListener("pointermove", (evento) => {
      if (!ojosEscenario || bot.dataset.mood === "dormido" || bot.dataset.mood === "pensando") return;
      const caja = bot.getBoundingClientRect();
      if (!caja.width) return;
      const dx = evento.clientX - (caja.left + caja.width / 2);
      const dy = evento.clientY - (caja.top + caja.height * 0.42);
      const distancia = Math.hypot(dx, dy) || 1;
      const alcance = Math.min(1, distancia / 260);
      ojosEscenario.style.transform = `translate(${((dx / distancia) * 4 * alcance).toFixed(2)}px, ${((dy / distancia) * 3 * alcance).toFixed(2)}px)`;
    });
  }

  // ---------- Interacción directa ----------
  const consejos = [
    "Tip: «show vlan brief» te dice qué puertos están en cada VLAN.",
    "Recuerda: un puerto de acceso solo pertenece a una VLAN.",
    "Usa datos ficticios en las prácticas. ¡Nada de contraseñas reales!",
    "Tip: «show interfaces fa0/1 switchport» confirma el modo del puerto.",
    "Si algo falla, pega la salida del comando y lo miramos juntos.",
    "¿Atascado? Carga el ejemplo del laboratorio y partimos de ahí.",
  ];
  let indiceConsejo = 0;
  bot.addEventListener("click", () => {
    decir(consejos[indiceConsejo++ % consejos.length], "saluda", 1600);
  });

  entrada.addEventListener("focus", () => {
    if (bot.dataset.mood !== "pensando") setAnimo("atento", 1800);
    despertar();
  });
  let avisoLargo = false;
  entrada.addEventListener("input", () => {
    despertar();
    if (!avisoLargo && entrada.value.length > 400) {
      avisoLargo = true;
      decir("¡Uf, eso es largo! Lo leo con calma.", "sorpresa", 1200);
    }
    if (!entrada.value) avisoLargo = false;
  });

  // ---------- Reacciones al chat ----------
  new MutationObserver(() => {
    if (!escribiendo.classList.contains("hidden")) {
      animoBase = "pensando";
      decir("Déjame pensar…", "pensando");
    } else if (animoBase === "pensando") {
      animoBase = "neutral";
    }
  }).observe(escribiendo, { attributes: true, attributeFilter: ["class"] });

  let limpiando = false;
  document.getElementById("new-chat-button").addEventListener("click", () => {
    limpiando = true;
    decir("Chat limpio. ¡Empecemos de nuevo!", "saluda", 1600);
  });

  new MutationObserver((cambios) => {
    if (limpiando) {
      limpiando = false;
      return;
    }
    for (const cambio of cambios) {
      for (const nodo of cambio.addedNodes) {
        if (!(nodo instanceof HTMLElement) || !nodo.classList.contains("message")) continue;
        if (nodo.classList.contains("message-user")) {
          decir("¡Recibido! Voy con ello.", "atento", 1200);
        } else {
          const texto = nodo.textContent || "";
          if (/No pude comunicarme|no disponible|error/i.test(texto)) {
            decir("Algo no salió bien… revisa el mensaje.", "sorpresa", 1600);
          } else {
            setAnimo("habla", 1500);
            window.setTimeout(() => decir("¡Listo! ¿Te explico algo más?", "feliz", 1600), 1500);
          }
        }
      }
    }
  }).observe(mensajes, { childList: true });

  // ---------- Reacciones al laboratorio ----------
  const nombrePractica = document.querySelector('#laboratorio-form [name="nombre"]');
  function actualizarPractica() {
    const nombre = nombrePractica?.value.trim();
    practica.textContent = nombre ? `Práctica: ${nombre}` : "Sin práctica abierta";
  }
  nombrePractica?.addEventListener("input", actualizarPractica);

  function observarTexto(id, reaccion) {
    const el = document.getElementById(id);
    if (!el) return;
    let anterior = el.textContent;
    new MutationObserver(() => {
      if (el.textContent === anterior) return;
      anterior = el.textContent;
      actualizarPractica();
      reaccion(anterior);
    }).observe(el, { childList: true, characterData: true, subtree: true });
  }
  observarTexto("lab-status", (t) => {
    if (/ejemplo/i.test(t)) decir("Ejemplo cargado. Revisa los datos y pulsa «Revisar datos».", "feliz", 1400);
  });
  observarTexto("lab-missing", (t) => {
    if (/Completa|falta/i.test(t)) decir("Faltan algunos datos en la práctica. ¡Échales un ojo!", "sorpresa", 1400);
    else if (t) decir("¡Datos correctos! Confirma y genera la propuesta.", "feliz", 1400);
  });
  observarTexto("lab-result-state", (t) => {
    if (/^Sin propuesta/i.test(t)) return;
    if (/Generando/i.test(t)) decir("Preparando la propuesta…", "pensando", 4000);
    else if (/Propuesta|reabierto|Respuesta generada/i.test(t)) decir("¡Propuesta lista! Pruébala en el simulador antes de darla por buena.", "feliz", 1800);
    else if (/No se pudo/i.test(t)) decir("No pude generar la propuesta. Revisa el aviso.", "sorpresa", 1500);
  });
  observarTexto("lab-diag-status", (t) => {
    if (t) decir("He comparado tus salidas. Mira el diagnóstico.", "habla", 1500);
  });

  // ---------- Abrir, minimizar y ampliar ----------
  function abrirChat() {
    shell.classList.remove("chat-cerrado");
    decir("¡Aquí estoy! ¿En qué te ayudo?", "saluda", 1600);
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

  // ---------- Saludo inicial ----------
  actualizarPractica();
  setAnimo("saluda", 1700);
  despertar();
})();

/* Cliente sencillo de chat: la memoria se conserva en el navegador, nunca en claves API. */
"use strict";

const API_BASE = "http://localhost:8000";
const STORAGE_KEY = "netassist.historial.v1";
const messagesElement = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const inputElement = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const typingIndicator = document.getElementById("typing-indicator");
const contactDialog = document.getElementById("contact-dialog");
const contactDetails = document.getElementById("contact-details");
const fileInput = document.getElementById("file-input");
const attachButton = document.getElementById("attach-button");
const adjuntoPreview = document.getElementById("adjunto-preview");
const adjuntoMiniatura = document.getElementById("adjunto-miniatura");
const adjuntoNombre = document.getElementById("adjunto-nombre");

const TIPOS_IMAGEN = ["image/png", "image/jpeg", "image/webp"];
const MAX_IMAGEN_BYTES = 4 * 1024 * 1024;
// Imagen pendiente de envío: { mime, data (base64 sin prefijo), nombre, url (data URL para la miniatura) }.
let imagenAdjunta = null;

let history = loadHistory();
let supportContact = "Contacta al docente o técnico responsable del laboratorio.";

// La política autoritativa y compartida se aplica en el servicio.

function loadHistory() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(stored)) return [];
    return stored.filter(
      (item) =>
        item &&
        (item.role === "user" || item.role === "assistant") &&
        typeof item.content === "string"
    );
  } catch (error) {
    console.error("No se pudo leer el historial guardado:", error);
    return [];
  }
}

function saveHistory() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch (error) {
    console.error("No se pudo guardar el historial:", error);
  }
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (character) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[character];
  });
}

function codigoHtml(bloque) {
  const codigoSeguro = escapeHtml(bloque.code);
  const idioma = bloque.language ? ` data-language="${escapeHtml(bloque.language)}"` : "";
  return `<div class="code-block"${idioma}><button class="copy-button" type="button">Copiar</button><pre><code>${codigoSeguro}</code></pre></div>`;
}

// Los diagramas mermaid quedan pendientes y se dibujan al insertar el mensaje (renderTopologias).
function topologiaHtml(bloque) {
  return `<figure class="topologia" data-estado="pendiente"><pre class="topologia-fuente">${escapeHtml(bloque.code)}</pre></figure>`;
}

let contadorTopologias = 0;

async function renderTopologias(contenedor) {
  const pendientes = contenedor.querySelectorAll('.topologia[data-estado="pendiente"]');
  for (const figura of pendientes) {
    const fuente = figura.querySelector(".topologia-fuente").textContent;
    figura.dataset.estado = "procesada";
    if (!window.mermaid) {
      figura.outerHTML = codigoHtml({ language: "mermaid", code: fuente });
      continue;
    }
    const id = `topologia-${++contadorTopologias}`;
    try {
      const { svg } = await window.mermaid.render(id, fuente);
      figura.innerHTML = `${svg}<figcaption>Topología generada por NetAssist</figcaption>`;
    } catch (error) {
      console.error("No se pudo dibujar la topología:", error);
      document.getElementById(`d${id}`)?.remove();
      figura.outerHTML = codigoHtml({ language: "mermaid", code: fuente });
    }
  }
  messagesElement.scrollTop = messagesElement.scrollHeight;
}

function renderMarkdown(text) {
  const bloquesCodigo = [];
  const conMarcadores = text.replace(/```([^\n`]*)\n?([\s\S]*?)```/g, (_, language, code) => {
    const index = bloquesCodigo.length;
    bloquesCodigo.push({ language: language.trim(), code: code.replace(/\n$/, "") });
    return `@@NETASSIST_CODE_${index}@@`;
  });
  const lineas = escapeHtml(conMarcadores).split(/\r?\n/);
  const resultado = [];
  let lista = null;

  const cerrarLista = () => {
    if (lista) {
      resultado.push(`</${lista}>`);
      lista = null;
    }
  };
  const inline = (line) =>
    line
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  const bloqueHtml = (bloque) =>
    bloque.language.toLowerCase() === "mermaid" ? topologiaHtml(bloque) : codigoHtml(bloque);

  for (const linea of lineas) {
    const marcadorSolo = linea.match(/^\s*@@NETASSIST_CODE_(\d+)@@\s*$/);
    if (marcadorSolo && bloquesCodigo[Number(marcadorSolo[1])]) {
      cerrarLista();
      resultado.push(bloqueHtml(bloquesCodigo[Number(marcadorSolo[1])]));
      continue;
    }
    const headingMatch = linea.match(/^\s*#{1,6}\s+(.+?)\s*$/);
    if (headingMatch) {
      cerrarLista();
      resultado.push(`<p><strong>${inline(headingMatch[1])}</strong></p>`);
      continue;
    }
    const ulMatch = linea.match(/^\s*[-*]\s+(.+)$/);
    const olMatch = linea.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ulMatch || olMatch) {
      const tipo = ulMatch ? "ul" : "ol";
      if (lista !== tipo) {
        cerrarLista();
        resultado.push(`<${tipo}>`);
        lista = tipo;
      }
      resultado.push(`<li>${inline((ulMatch || olMatch)[1])}</li>`);
      continue;
    }
    cerrarLista();
    if (!linea.trim()) continue;
    resultado.push(`<p>${inline(linea)}</p>`);
  }
  cerrarLista();
  // Red de seguridad: reemplaza cualquier marcador que haya quedado suelto (p. ej. pegado a otro texto).
  return resultado
    .join("")
    .replace(/@@NETASSIST_CODE_(\d+)@@/g, (_, i) =>
      bloquesCodigo[Number(i)] ? bloqueHtml(bloquesCodigo[Number(i)]) : ""
    );
}

function appendMessage(role, content, persist = true, imagenUrl = null) {
  const article = document.createElement("article");
  article.className = `message message-${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
    renderTopologias(bubble);
  } else {
    if (imagenUrl) {
      const imagen = document.createElement("img");
      imagen.className = "bubble-imagen";
      imagen.src = imagenUrl;
      imagen.alt = "Imagen adjunta";
      bubble.appendChild(imagen);
    }
    const paragraph = document.createElement("p");
    paragraph.textContent = content;
    bubble.appendChild(paragraph);
  }
  if (role === "assistant") {
    // Nexo responde en persona: su avatar acompaña cada respuesta (mascota.js lo anima).
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.dataset.nexo = "";
    avatar.setAttribute("aria-hidden", "true");
    avatar.append(document.getElementById("nexo-template").content.cloneNode(true));
    article.append(avatar);
  }
  article.append(bubble);
  messagesElement.appendChild(article);
  messagesElement.scrollTop = messagesElement.scrollHeight;
  if (persist) {
    history.push({ role, content });
    saveHistory();
  }
}

// ----- Sugerencias de Nexo: bloques concretos al empezar y un siguiente paso tras cada respuesta -----
const NEXO_TEMAS = {
  configurar: { etiqueta: "Generar la configuración", pregunta: "¿Te genero la configuración?", prompt: (n) => `Genera la configuración Cisco IOS de mi práctica «${n}».` },
  explicar: { etiqueta: "Explicar cada comando", pregunta: "¿Quieres que te explique qué hace cada comando?", prompt: () => "Explícame qué hace cada comando de la configuración de mi práctica." },
  verificar: { etiqueta: "Comandos para comprobarlo", pregunta: "¿Quieres que te dé comandos para que lo compruebes?", prompt: () => "Dame los comandos para comprobar mi práctica en el simulador y qué debería ver en cada uno." },
  topologia: { etiqueta: "Dibujar la topología", pregunta: "¿Te dibujo la topología?", prompt: () => "Genera la topología de mi práctica." },
  errores: { etiqueta: "Errores comunes", pregunta: "¿Repasamos los errores más comunes?", prompt: () => "¿Qué errores comunes debo evitar en esta práctica y cómo los reviso?" },
};
const NEXO_SIGUIENTE = {
  configurar: ["verificar", "explicar", "topologia", "errores"],
  verificar: ["explicar", "errores", "topologia", "configurar"],
  explicar: ["verificar", "topologia", "errores", "configurar"],
  topologia: ["configurar", "verificar", "explicar", "errores"],
  errores: ["verificar", "configurar", "explicar", "topologia"],
};
let temasUsados = new Set();

function temaDe(texto) {
  if (/topolog/i.test(texto)) return "topologia";
  if (/comprob|verific|\bshow\b/i.test(texto)) return "verificar";
  if (/expl[ií]ca|qu[eé] hace/i.test(texto)) return "explicar";
  if (/error|falla|no funciona/i.test(texto)) return "errores";
  if (/configur|comando|vlan/i.test(texto)) return "configurar";
  return null;
}

function quitarSugerencias() {
  for (const bloque of messagesElement.querySelectorAll(".sugerencias")) bloque.remove();
}

function mostrarSugerencias(temas, intro = "") {
  quitarSugerencias();
  const ultimo = messagesElement.lastElementChild;
  if (!temas.length || !ultimo || !ultimo.classList.contains("message-assistant")) return;
  const bloque = document.createElement("div");
  bloque.className = "sugerencias";
  if (intro) {
    const texto = document.createElement("p");
    texto.textContent = intro;
    bloque.appendChild(texto);
  }
  const lista = document.createElement("div");
  lista.className = "sugerencias-lista";
  for (const tema of temas) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "sugerencia";
    boton.textContent = NEXO_TEMAS[tema].etiqueta;
    boton.addEventListener("click", () => enviarMensaje(NEXO_TEMAS[tema].prompt(window.labNombre ? window.labNombre() : "mi práctica"), null, tema));
    lista.appendChild(boton);
  }
  bloque.appendChild(lista);
  ultimo.appendChild(bloque);
  messagesElement.scrollTop = messagesElement.scrollHeight;
}

// Tras una respuesta sobre la práctica, Nexo propone el siguiente paso que aún no se ha visto.
function sugerirSiguiente(tema) {
  if (!tema || typeof window.labContexto !== "function" || !window.labContexto()) return;
  temasUsados.add(tema);
  const pendientes = NEXO_SIGUIENTE[tema].filter((t) => !temasUsados.has(t)).slice(0, 3);
  if (!pendientes.length) return;
  const intro = pendientes.length > 1 ? `${NEXO_TEMAS[pendientes[0]].pregunta} También puedo ayudarte con esto:` : NEXO_TEMAS[pendientes[0]].pregunta;
  mostrarSugerencias(pendientes, intro);
}

// Abre el chat y Nexo saluda: ya tiene los datos guardados de la práctica y propone por dónde seguir.
window.nexoSaludo = (nombre) => {
  document.getElementById("nexo-launcher").click();
  temasUsados = new Set();
  appendMessage(
    "assistant",
    `¡Hola! Ya tengo los datos de tu práctica «${nombre}» (equipo, VLAN y puertos). ¿Qué dudas tienes? Te sugiero empezar por alguno de estos bloques:`,
    false
  );
  mostrarSugerencias(["configurar", "explicar", "topologia", "errores"]);
};

// Añade al último mensaje (solo en lo que se envía, no en el historial visible) los datos del formulario de la práctica.
function conContexto(mensajes) {
  const contexto = typeof window.labContexto === "function" ? window.labContexto() : "";
  if (!contexto || !mensajes.length) return mensajes;
  const copia = mensajes.map(m => ({ ...m }));
  const ultimo = copia[copia.length - 1];
  const extra = `\n\nDatos de mi práctica (formulario del laboratorio, ficticios):\n${contexto}`;
  if (ultimo.content.length + extra.length > 12000) return mensajes; // límite por mensaje del backend
  ultimo.content += extra;
  return copia;
}

function restoreHistory() {
  for (const message of history) appendMessage(message.role, message.content, false);
}

async function fetchContact() {
  try {
    const response = await fetch(`${API_BASE}/contacto`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (typeof data.contact === "string" && data.contact.trim()) {
      supportContact = data.contact;
    }
  } catch (error) {
    console.error("No se pudo consultar el contacto configurado:", error);
  }
}

function quitarAdjunto() {
  imagenAdjunta = null;
  document.getElementById("captura-revisada").checked = false;
  fileInput.value = "";
  adjuntoMiniatura.removeAttribute("src");
  adjuntoPreview.classList.add("hidden");
}

function leerComoDataUrl(archivo) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(lector.result);
    lector.onerror = () => reject(lector.error);
    lector.readAsDataURL(archivo);
  });
}

async function adjuntarArchivo(archivo) {
  if (!archivo || !TIPOS_IMAGEN.includes(archivo.type)) {
    appendMessage("assistant", "Solo puedo recibir imágenes PNG, JPG o WEBP.", false);
    return;
  }
  if (archivo.size > MAX_IMAGEN_BYTES) {
    appendMessage("assistant", "La imagen supera el límite de 4 MB. Recórtala o redúcela e inténtalo de nuevo.", false);
    return;
  }
  try {
    const url = await leerComoDataUrl(archivo);
    imagenAdjunta = { mime: archivo.type, data: url.split(",")[1], nombre: archivo.name || "imagen", url };
    adjuntoMiniatura.src = url;
    adjuntoNombre.textContent = imagenAdjunta.nombre;
    adjuntoPreview.classList.remove("hidden");
    inputElement.focus();
  } catch (error) {
    console.error("No se pudo leer la imagen:", error);
    appendMessage("assistant", "No pude leer la imagen. Inténtalo con otro archivo.", false);
  }
}

attachButton.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => adjuntarArchivo(fileInput.files[0]));
document.getElementById("adjunto-quitar").addEventListener("click", quitarAdjunto);
inputElement.addEventListener("paste", (event) => {
  const item = [...event.clipboardData.items].find((elemento) => elemento.type.startsWith("image/"));
  if (!item) return;
  event.preventDefault();
  adjuntarArchivo(item.getAsFile());
});

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const texto = inputElement.value.trim();
  const imagen = imagenAdjunta;
  if ((!texto && !imagen) || sendButton.disabled) return;

  if (imagen && !document.getElementById("captura-revisada").checked) {
    appendMessage("assistant", "Revisa la captura, elimina datos reales y confirma la casilla antes de enviarla.", false);
    return;
  }
  inputElement.value = "";
  enviarMensaje(texto, imagen);
});

// Envía un mensaje al chat. Las sugerencias lo llaman sin imagen y sin tocar el borrador del campo de texto.
async function enviarMensaje(texto, imagen = null, tema = null) {
  if (sendButton.disabled) return;
  quitarSugerencias();
  // El historial guarda solo texto; la nota deja constancia de que hubo una imagen en ese turno.
  const content = imagen
    ? `${texto || "Analiza la imagen adjunta."}\n\n[Imagen adjunta: ${imagen.nombre}]`
    : texto;
  appendMessage("user", content, true, imagen ? imagen.url : null);
  if (imagen) quitarAdjunto();
  sendButton.disabled = true;
  typingIndicator.classList.remove("hidden");
  messagesElement.scrollTop = messagesElement.scrollHeight;

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        imagen ? { messages: conContexto(history), imagen: { mime: imagen.mime, data: imagen.data, laboratorio_confirmado: true } } : { messages: conContexto(history) }
      ),
    });
    const data = await response.json();
    if (!response.ok) {
      if (typeof data.detail === "string") {
        appendMessage("assistant", data.detail);
        return;
      }
      throw new Error(`El servidor respondió HTTP ${response.status}`);
    }
    if (typeof data.reply !== "string" || !data.reply.trim()) {
      throw new Error("El servidor devolvió una respuesta vacía.");
    }
    if (typeof data.contact === "string" && data.contact.trim()) {
      supportContact = data.contact;
    }
    appendMessage("assistant", data.reply);
    // Si Nexo entregó comandos o un diagrama, lo deja también en el panel de la práctica.
    if (/```/.test(data.reply) && typeof window.labDesdeChat === "function") window.labDesdeChat(data.reply);
    // Y le propone a la persona el siguiente paso (comprobar, explicar, topología…).
    sugerirSiguiente(tema || temaDe(texto) || (/```mermaid/.test(data.reply) ? "topologia" : null));
  } catch (error) {
    console.error("Falló la solicitud de chat:", error);
    appendMessage(
      "assistant",
      `No pude comunicarme con el servicio de NetAssist. Verifica que el backend esté iniciado o contacta al docente o técnico: ${supportContact}`
    );
  } finally {
    typingIndicator.classList.add("hidden");
    sendButton.disabled = false;
    inputElement.focus();
  }
}

document.getElementById("new-chat-button").addEventListener("click", () => {
  history = [];
  temasUsados = new Set();
  saveHistory();
  quitarAdjunto();
  messagesElement.replaceChildren();
  appendMessage(
    "assistant",
    "¡Hola! Soy Nexo, tu compañero de NetAssist. Cuéntame qué problema tienes y, si puedes, incluye el modelo del equipo Cisco, la versión de IOS y el error exacto."
  );
});

function openContactDialog() {
  contactDetails.textContent = supportContact;
  contactDialog.showModal();
}

document.getElementById("contact-button").addEventListener("click", openContactDialog);
document.getElementById("close-contact-button").addEventListener("click", () => contactDialog.close());
document.getElementById("dialog-ok-button").addEventListener("click", () => contactDialog.close());

messagesElement.addEventListener("click", async (event) => {
  const button = event.target.closest(".copy-button");
  if (!button) return;
  const code = button.parentElement.querySelector("code").textContent;
  try {
    await navigator.clipboard.writeText(code);
    button.textContent = "Copiado";
    window.setTimeout(() => (button.textContent = "Copiar"), 1400);
  } catch (error) {
    console.error("No se pudo copiar el bloque de código:", error);
    button.textContent = "No disponible";
    window.setTimeout(() => (button.textContent = "Copiar"), 1400);
  }
});

if (window.mermaid) {
  window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
}

restoreHistory();
fetchContact();

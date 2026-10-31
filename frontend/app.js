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

let history = loadHistory();
let supportContact = "Contacta al docente o técnico responsable del laboratorio.";

// Aviso instantáneo ante posibles datos sensibles; el backend hace la validación autoritativa.
const SENSIBLE_REGEX = /(\b\d{1,3}(\.\d{1,3}){3}\b|password|secret|contrase)/i;
const SENSIBLE_MENSAJE =
  "Detecté posibles datos sensibles (una IP real o una contraseña). Por seguridad, reemplázalos por valores de ejemplo (por ejemplo, 192.168.X.1) y vuelve a enviar tu consulta.";

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

  for (const linea of lineas) {
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
    const marcador = linea.match(/^@@NETASSIST_CODE_(\d+)@@$/);
    if (marcador) {
      const bloque = bloquesCodigo[Number(marcador[1])];
      const codigoSeguro = escapeHtml(bloque.code);
      const idioma = bloque.language ? ` data-language="${escapeHtml(bloque.language)}"` : "";
      resultado.push(
        `<div class="code-block"${idioma}><button class="copy-button" type="button">Copiar</button><pre><code>${codigoSeguro}</code></pre></div>`
      );
    } else {
      resultado.push(`<p>${inline(linea)}</p>`);
    }
  }
  cerrarLista();
  return resultado.join("");
}

function appendMessage(role, content, persist = true) {
  const article = document.createElement("article");
  article.className = `message message-${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    const paragraph = document.createElement("p");
    paragraph.textContent = content;
    bubble.appendChild(paragraph);
  }
  const meta = document.createElement("span");
  meta.className = "message-meta";
  meta.textContent = role === "assistant" ? "NetAssist" : "Tú";
  article.append(bubble, meta);
  messagesElement.appendChild(article);
  messagesElement.scrollTop = messagesElement.scrollHeight;
  if (persist) {
    history.push({ role, content });
    saveHistory();
  }
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

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = inputElement.value.trim();
  if (!content || sendButton.disabled) return;

  if (SENSIBLE_REGEX.test(content)) {
    appendMessage("user", content);
    inputElement.value = "";
    appendMessage("assistant", SENSIBLE_MENSAJE);
    inputElement.focus();
    return;
  }

  appendMessage("user", content);
  inputElement.value = "";
  sendButton.disabled = true;
  typingIndicator.classList.remove("hidden");
  messagesElement.scrollTop = messagesElement.scrollHeight;

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `El servidor respondió HTTP ${response.status}`);
    }
    if (typeof data.reply !== "string" || !data.reply.trim()) {
      throw new Error("El servidor devolvió una respuesta vacía.");
    }
    if (typeof data.contact === "string" && data.contact.trim()) {
      supportContact = data.contact;
    }
    appendMessage("assistant", data.reply);
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
});

document.getElementById("new-chat-button").addEventListener("click", () => {
  history = [];
  saveHistory();
  messagesElement.replaceChildren();
  appendMessage(
    "assistant",
    "¡Hola! Soy NetAssist. Cuéntame qué problema tienes y, si puedes, incluye el modelo del equipo Cisco, la versión de IOS y el error exacto."
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

restoreHistory();
fetchContact();

/* Formulario de laboratorio: revisión local de campos compartida con Streamlit. */
"use strict";
const labForm = document.getElementById("laboratorio-form");
const labPorts = document.getElementById("laboratorio-puertos");
const labStatus = document.getElementById("lab-status");
const labConfirm = document.getElementById("lab-confirm");
const labGenerate = document.getElementById("lab-generate");
let labRevision = null;
let labBusy = false;

function labInvalidate() {
  labRevision = null;
  labConfirm.checked = false;
  labGenerate.disabled = true;
  document.getElementById("lab-review").classList.add("hidden");
  document.getElementById("lab-review-empty").classList.remove("hidden");
  document.getElementById("lab-result").replaceChildren();
  document.getElementById("lab-result").classList.add("hidden");
  document.getElementById("lab-result-state").textContent = "Sin propuesta para estos datos";
}

function labSetBusy(busy) {
  labBusy = busy;
  for (const element of labForm.elements) element.disabled = busy;
  labConfirm.disabled = busy;
  document.getElementById("lab-discard").disabled = busy;
  labGenerate.disabled = busy || !labRevision || labRevision.faltantes.length > 0 || !labConfirm.checked;
  document.getElementById("lab-add").disabled = busy || labPorts.children.length >= 16;
}

function labAddPort(data = {}) {
  if (labPorts.children.length >= 16) return;
  const row = document.createElement("div");
  row.className = "lab-port";
  for (const [key, title, max] of [["id", "VLAN", 5], ["nombre", "Nombre", 32], ["puerto", "Puerto", 64], ["host", "Equipo conectado", 64]]) {
    const label = document.createElement("label");
    label.textContent = title;
    const input = document.createElement("input");
    input.dataset.field = key;
    input.value = data[key] || "";
    input.maxLength = max;
    label.appendChild(input);
    row.appendChild(label);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "button button-quiet";
  remove.textContent = "Quitar conexión";
  remove.addEventListener("click", () => {
    if (labBusy) return;
    if (labPorts.children.length === 1) {
      labStatus.textContent = "Mantén al menos una conexión para revisar la práctica.";
      return;
    }
    row.remove(); labInvalidate(); labSetBusy(false);
  });
  row.appendChild(remove);
  labPorts.appendChild(row);
}

function labRead() {
  const value = (name) => labForm.elements.namedItem(name).value.trim();
  return { tipo: value("tipo"), nombre: value("nombre"), equipo: { alias: value("alias"), modelo: value("modelo"), ios: value("ios") }, objetivo: value("objetivo"),
    vlans: [...labPorts.children].map(row => Object.fromEntries([...row.querySelectorAll("input")].map(input => [input.dataset.field, input.value.trim()]))) };
}

async function labRequest(path, body) {
  const response = await fetch(`${API_BASE}/laboratorio/${path}`, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Revisa los campos y los límites de longitud del formulario.");
  return data;
}

async function labLoadExample() {
  if (labBusy) return;
  labSetBusy(true);
  try {
    const data = await labRequest("ejemplo");
    for (const key of ["tipo", "nombre", "objetivo"]) labForm.elements.namedItem(key).value = data[key];
    for (const key of ["alias", "modelo", "ios"]) labForm.elements.namedItem(key).value = data.equipo[key];
    labPorts.replaceChildren();
    data.vlans.forEach(labAddPort);
    labInvalidate();
    labStatus.textContent = "Ejemplo ficticio cargado. Puedes editarlo antes de revisar.";
  } catch (error) {
    if (!labPorts.children.length) labAddPort();
    labStatus.textContent = `No se pudo cargar el ejemplo. Puedes completar los datos. ${error.message}`;
  } finally { labSetBusy(false); }
}

labForm.addEventListener("input", () => { labInvalidate(); labStatus.textContent = "Datos editados. Revisa nuevamente antes de generar."; });
labForm.addEventListener("change", labInvalidate);
document.getElementById("lab-add").addEventListener("click", () => { if (!labBusy) { labAddPort(); labInvalidate(); labSetBusy(false); } });
document.getElementById("lab-example").addEventListener("click", labLoadExample);
document.getElementById("lab-discard").addEventListener("click", labInvalidate);
labConfirm.addEventListener("change", () => labSetBusy(labBusy));
labForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (labBusy) return;
  const datos = labRead();
  labInvalidate(); labSetBusy(true);
  labStatus.textContent = "Revisando campos…";
  try {
    labRevision = await labRequest("preparar", datos);
    document.getElementById("lab-draft").textContent = labRevision.prompt;
    document.getElementById("lab-missing").textContent = labRevision.faltantes.length ? `Completa estos datos: ${labRevision.faltantes.join("; ")}.` : "Campos completos. Revisa la solicitud antes de generar.";
    document.getElementById("lab-review").classList.remove("hidden");
    document.getElementById("lab-review-empty").classList.add("hidden");
    labStatus.textContent = "Revisión preparada. No se consultó a la IA.";
  } catch (error) { labStatus.textContent = error.message; }
  finally { labSetBusy(false); }
});
labGenerate.addEventListener("click", async () => {
  if (labBusy || !labRevision || !labConfirm.checked || labRevision.faltantes.length) return;
  labSetBusy(true);
  document.getElementById("lab-result").replaceChildren();
  document.getElementById("lab-result").classList.add("hidden");
  labStatus.textContent = "Generando propuesta…";
  document.getElementById("lab-result-state").textContent = "Generando respuesta…";
  try {
    const data = await labRequest("generar", { tarea: labRevision.datos, confirmado: true });
    const result = document.getElementById("lab-result");
    result.innerHTML = renderMarkdown(data.respuesta);
    renderTopologias(result);
    result.classList.remove("hidden");
    document.getElementById("lab-result-state").textContent = data.estado === "respuesta_generada" ? "Respuesta generada · Propuesta pendiente de verificación" : "Sin propuesta · Revisa el aviso";
    labStatus.textContent = "Respuesta recibida. No se ejecutaron comandos.";
  } catch (error) {
    document.getElementById("lab-result-state").textContent = "No se pudo generar una propuesta";
    labStatus.textContent = error.message;
  } finally { labSetBusy(false); }
});
// El panel de resultados comparte el comportamiento de copiado del chat.
document.getElementById("lab-result").addEventListener("click", async event => {
  const button = event.target.closest(".copy-button");
  if (!button) return;
  try { await navigator.clipboard.writeText(button.parentElement.querySelector("code").textContent); button.textContent = "Copiado"; }
  catch { button.textContent = "No disponible"; }
});
labLoadExample();

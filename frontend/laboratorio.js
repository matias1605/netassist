/* Formulario de laboratorio: revisión local de campos compartida con Streamlit. */
"use strict";
const labForm = document.getElementById("laboratorio-form");
const labPorts = document.getElementById("laboratorio-puertos");
const labStatus = document.getElementById("lab-status");
const labConfirm = document.getElementById("lab-confirm");
const labGenerate = document.getElementById("lab-generate");
let labRevision = null;
let labBusy = false;
let labCaseId = null;
const labCases = document.getElementById("lab-cases");

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
  labGenerate.disabled = busy || !labRevision || labRevision.faltantes.length > 0 || labRevision.errores.length > 0 || !labConfirm.checked;
  labCases.disabled = busy; document.getElementById("lab-reopen").disabled = busy || !labCases.options.length;
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
    labCaseId = null;
    labResetDiagnosis(null);
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
    const problemas = [];
    if (labRevision.errores.length) problemas.push(`Corrige estos datos: ${labRevision.errores.join(" ")}`);
    if (labRevision.faltantes.length) problemas.push(`Completa estos datos: ${labRevision.faltantes.join("; ")}.`);
    document.getElementById("lab-missing").textContent = problemas.length ? problemas.join(" ") : "Campos completos y reglas aprobadas. Revisa la solicitud antes de generar.";
    const preview = document.getElementById("lab-preview");
    preview.replaceChildren();
    if (labRevision.propuesta) { preview.innerHTML = renderMarkdown(labRevision.texto_previo); renderTopologias(preview); }
    document.getElementById("lab-review").classList.remove("hidden");
    document.getElementById("lab-review-empty").classList.add("hidden");
    labStatus.textContent = "Revisión preparada. No se consultó a la IA.";
  } catch (error) { labStatus.textContent = error.message; }
  finally { labSetBusy(false); }
});
labGenerate.addEventListener("click", async () => {
  if (labBusy || !labRevision || !labConfirm.checked || labRevision.faltantes.length || labRevision.errores.length) return;
  labSetBusy(true);
  document.getElementById("lab-result").replaceChildren();
  document.getElementById("lab-result").classList.add("hidden");
  labStatus.textContent = "Generando propuesta…";
  document.getElementById("lab-result-state").textContent = "Generando respuesta…";
  try {
    const data = await labRequest("generar", { tarea: labRevision.datos, confirmado: true, caso_id: labCaseId });
    const result = document.getElementById("lab-result");
    result.innerHTML = renderMarkdown(data.texto);
    labCaseId = data.caso_id;
    renderTopologias(result);
    result.classList.remove("hidden");
    document.getElementById("lab-result-state").textContent = data.estado === "respuesta_generada" ? "Propuesta con explicación de IA · Validada por reglas, pendiente de comprobar en laboratorio" : "Propuesta sin explicación de IA · Revisa el aviso";
    labStatus.textContent = `Caso guardado (${String(data.caso_id).slice(0, 8)}). No se ejecutaron comandos.`;
    labResetDiagnosis(labCaseId);
    labLoadCases();
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

async function labLoadCases() {
  try {
    const casos = await labRequestRoot("casos");
    const selected = labCases.value;
    labCases.replaceChildren(...casos.map(caso => new Option(`${caso.nombre || "Sin nombre"} · ${caso.estado} · ${caso.actualizado.slice(0, 16).replace("T", " ")}`, caso.id)));
    if (selected && casos.some(caso => caso.id === selected)) labCases.value = selected;
    document.getElementById("lab-cases-empty").classList.toggle("hidden", casos.length > 0);
    labCases.closest(".lab-buttons").classList.toggle("hidden", casos.length === 0);
    labSetBusy(labBusy);
  } catch { /* La lista es opcional: el formulario sigue disponible. */ }
}

async function labRequestRoot(path) {
  const response = await fetch(`${API_BASE}/${path}`);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo leer el caso.");
  return data;
}

document.getElementById("lab-reopen").addEventListener("click", async () => {
  if (labBusy || !labCases.value) return;
  labSetBusy(true);
  try {
    const caso = await labRequestRoot(`casos/${encodeURIComponent(labCases.value)}`);
    const data = caso.tarea;
    for (const key of ["tipo", "nombre", "objetivo"]) labForm.elements.namedItem(key).value = data[key];
    for (const key of ["alias", "modelo", "ios"]) labForm.elements.namedItem(key).value = data.equipo[key];
    labPorts.replaceChildren();
    data.vlans.forEach(labAddPort);
    labInvalidate();
    labCaseId = caso.caso_id;
    if (caso.propuesta) {
      const result = document.getElementById("lab-result");
      result.innerHTML = renderMarkdown(caso.propuesta.texto);
      renderTopologias(result);
      result.classList.remove("hidden");
      const comprobacion = caso.propuesta.comprobacion_laboratorio;
      document.getElementById("lab-result-state").textContent = `Caso reabierto · ${comprobacion === "no_realizada" ? "pendiente de comprobar en laboratorio" : `comprobación en laboratorio: ${comprobacion}`}`;
    }
    labStatus.textContent = "Caso reabierto. Si editas un dato y generas de nuevo, se actualiza el mismo caso.";
    labResetDiagnosis(labCaseId);
  } catch (error) { labStatus.textContent = error.message; }
  finally { labSetBusy(false); }
});

// ----- Fase 4: diagnóstico con evidencia -----
const labDiag = document.getElementById("lab-diag");
const labEvidence = document.getElementById("lab-evidence");
const labDiagStatus = document.getElementById("lab-diag-status");

function labShowDiagnosis(data, omitidos = []) {
  labDiag.innerHTML = renderMarkdown(data.texto);
  labDiag.classList.remove("hidden");
  const motivos = omitidos.map(item => item.motivo);
  if (motivos.length) {
    const aviso = document.createElement("p");
    aviso.textContent = `No se registró: ${motivos.join(" ")}`;
    labDiag.prepend(aviso);
  }
}

function labResetDiagnosis(caseId) {
  labDiag.replaceChildren(); labDiag.classList.add("hidden");
  labEvidence.value = ""; labDiagStatus.textContent = "";
  document.getElementById("lab-diag-box").classList.toggle("hidden", !caseId);
  document.getElementById("lab-diag-empty").classList.toggle("hidden", !!caseId);
  if (!caseId) return;
  labRequestRoot(`casos/${encodeURIComponent(caseId)}/diagnostico`).then(data => {
    if (labCaseId === caseId && data.estado !== "sin_evidencia") labShowDiagnosis(data);
  }).catch(() => { /* El diagnóstico es opcional hasta pegar salidas. */ });
}

document.getElementById("lab-diagnose").addEventListener("click", async () => {
  const salida = labEvidence.value.trim();
  if (labBusy || !labCaseId) return;
  if (!salida) { labDiagStatus.textContent = "Pega primero la salida de un comando de verificación."; return; }
  labSetBusy(true);
  labDiagStatus.textContent = "Analizando salidas…";
  try {
    const response = await fetch(`${API_BASE}/casos/${encodeURIComponent(labCaseId)}/evidencias`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ salida }) });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo analizar la salida.");
    labShowDiagnosis(data, data.omitidos);
    if (data.registradas.length) labEvidence.value = "";
    labDiagStatus.textContent = data.registradas.length ? `${data.registradas.length} evidencia(s) registrada(s). No se ejecutaron comandos.` : "No se registró ninguna evidencia nueva.";
    labLoadCases();
  } catch (error) { labDiagStatus.textContent = error.message; }
  finally { labSetBusy(false); }
});

labResetDiagnosis(null);
labLoadCases();
labLoadExample();

/* Laboratorio: formulario de la práctica, ejemplos, envío a Nexo y resumen de la sesión. */
"use strict";
const labForm = document.getElementById("laboratorio-form");
const labPorts = document.getElementById("laboratorio-puertos");
const labStatus = document.getElementById("lab-status");
let labBusy = false;
let labCaseId = null;
const labCases = document.getElementById("lab-cases");
const labUserInput = document.getElementById("lab-user");
const labFilter = document.getElementById("lab-filter");
const labArchived = document.getElementById("lab-archived");
const labCasesStatus = document.getElementById("lab-cases-status");
const LAB_ESTADOS = { borrador: "Borrador", propuesta: "Propuesta generada", comprobado: "Comprobado en laboratorio", comprobacion_fallida: "Comprobación fallida", en_diagnostico: "En diagnóstico", diagnostico_coherente: "Salidas coherentes" };
const LAB_GUARDADO = "netassist_practica";
let labArchivedCase = false;

// Prácticas de ejemplo (datos ficticios) que solo rellenan el formulario.
const LAB_EJEMPLOS = [
  { titulo: "Administración y Laboratorio", nombre: "Segmentación de Administración y Laboratorio", equipo: { alias: "SW1", modelo: "Cisco Catalyst 2960" },
    vlans: [{ id: "10", nombre: "ADMINISTRACION", puerto: "GigabitEthernet0/1", host: "PC_ADMIN" }, { id: "20", nombre: "LABORATORIO", puerto: "GigabitEthernet0/2", host: "PC_LAB" }] },
  { titulo: "Ventas y Soporte", nombre: "Separar Ventas y Soporte", equipo: { alias: "SW_OFICINA", modelo: "Cisco Catalyst 2960" },
    vlans: [{ id: "30", nombre: "VENTAS", puerto: "Fa0/1", host: "PC_VENTAS" }, { id: "40", nombre: "SOPORTE", puerto: "Fa0/2", host: "PC_SOPORTE" }] },
  { titulo: "Aulas, profesores e invitados", nombre: "Red del colegio con tres VLAN", equipo: { alias: "SW_COLEGIO", modelo: "Cisco Catalyst 2960" },
    vlans: [{ id: "50", nombre: "AULAS", puerto: "Fa0/1", host: "PC_AULA1" }, { id: "60", nombre: "PROFESORES", puerto: "Fa0/2", host: "PC_PROFE" }, { id: "70", nombre: "INVITADOS", puerto: "Fa0/3", host: "PC_INVITADO" }] },
];

// Clave personal opaca para separar casos entre personas del mismo navegador/servidor; no es autenticación.
function labNewUser() {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  return [...bytes].map(b => b.toString(16).padStart(2, "0")).join("");
}
function labUser() {
  if (!labUser.value) {
    try { labUser.value = localStorage.getItem("netassist_usuario"); } catch { /* sin almacenamiento */ }
    if (!/^[A-Za-z0-9_-]{16,64}$/.test(labUser.value || "")) {
      labUser.value = labNewUser();
      try { localStorage.setItem("netassist_usuario", labUser.value); } catch { /* la clave dura lo que dure la pestaña */ }
    }
  }
  return labUser.value;
}
function labHeaders(extra = {}) { return { "X-Usuario": labUser(), ...extra }; }

// El formulario no muestra tipo, IOS ni objetivo (eso se pide en el chat); se conservan los de un caso reabierto.
let labExtra = { tipo: "configuracion", ios: "", objetivo: "" };
function labFill(data) {
  labExtra = { tipo: data.tipo || "configuracion", ios: data.equipo.ios || "", objetivo: data.objetivo || "" };
  labForm.elements.namedItem("nombre").value = data.nombre || "";
  for (const key of ["alias", "modelo"]) labForm.elements.namedItem(key).value = data.equipo[key] || "";
  labPorts.replaceChildren();
  (data.vlans.length ? data.vlans : [{}]).forEach(labAddPort);
  // Avisa a quien escucha el formulario (p. ej. el nombre de la práctica en la cabecera del chat).
  labForm.elements.namedItem("nombre").dispatchEvent(new Event("input", { bubbles: true }));
}

function labSetBusy(busy) {
  labBusy = busy;
  for (const element of labForm.elements) element.disabled = busy;
  labCases.disabled = busy; document.getElementById("lab-reopen").disabled = busy || !labCases.options.length;
  document.getElementById("lab-report").disabled = busy || !labCaseId;
  document.getElementById("lab-archive").disabled = busy || !labCaseId;
  document.getElementById("lab-add").disabled = busy || labPorts.children.length >= 16;
}

function labAddPort(data = {}) {
  if (labPorts.children.length >= 16) return;
  const row = document.createElement("div");
  row.className = "lab-port";
  row.dataset.color = String(labPorts.children.length % 2);
  const titulo = document.createElement("p");
  titulo.className = "lab-port-titulo";
  titulo.textContent = `Grupo ${labPorts.children.length + 1}`;
  row.appendChild(titulo);
  for (const [key, title, max] of [["id", "ID de VLAN", 5], ["nombre", "Nombre", 32], ["puerto", "Puertos de acceso", 64], ["host", "Equipo conectado", 64]]) {
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
  remove.textContent = "Quitar grupo";
  remove.addEventListener("click", () => {
    if (labBusy) return;
    if (labPorts.children.length === 1) {
      labStatus.textContent = "Mantén al menos un grupo de puertos.";
      return;
    }
    row.remove();
    [...labPorts.children].forEach((hermano, i) => { hermano.querySelector(".lab-port-titulo").textContent = `Grupo ${i + 1}`; hermano.dataset.color = String(i % 2); });
    labSetBusy(false);
  });
  row.appendChild(remove);
  labPorts.appendChild(row);
}

function labRead() {
  const value = (name) => labForm.elements.namedItem(name).value.trim();
  return { tipo: labExtra.tipo, nombre: value("nombre"), equipo: { alias: value("alias"), modelo: value("modelo"), ios: labExtra.ios }, objetivo: labExtra.objetivo,
    vlans: [...labPorts.children].map(row => Object.fromEntries([...row.querySelectorAll("input[data-field]")].map(input => [input.dataset.field, input.value.trim()]))) };
}

async function labRequest(path, body) {
  const response = await fetch(`${API_BASE}/laboratorio/${path}`, body ? { method: "POST", headers: labHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body) } : { headers: labHeaders() });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Revisa los campos y los límites de longitud del formulario.");
  return data;
}

// ----- Ejemplos y guardado local -----
function labSave() {
  try { localStorage.setItem(LAB_GUARDADO, JSON.stringify(labRead())); return true; } catch { return false; }
}
function labRestore() {
  try {
    const guardado = JSON.parse(localStorage.getItem(LAB_GUARDADO) || "null");
    if (guardado && guardado.equipo && Array.isArray(guardado.vlans)) { labFill(guardado); return; }
  } catch { /* datos guardados ilegibles: se empieza vacío */ }
  labAddPort();
}

const labEjemplos = document.getElementById("lab-ejemplos");
for (const ejemplo of LAB_EJEMPLOS) {
  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "ejemplo-boton";
  const titulo = document.createElement("strong");
  titulo.textContent = ejemplo.titulo;
  const detalle = document.createElement("span");
  detalle.textContent = `${ejemplo.equipo.alias} · ${ejemplo.vlans.length} VLAN`;
  boton.append(titulo, detalle);
  boton.addEventListener("click", () => {
    if (labBusy) return;
    labFill(ejemplo);
    labCaseId = null;
    labStatus.textContent = "";
    labForm.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  labEjemplos.appendChild(boton);
}

document.getElementById("lab-add").addEventListener("click", () => { if (!labBusy) { labAddPort(); labSetBusy(false); } });
document.getElementById("lab-save").addEventListener("click", () => {
  labStatus.textContent = labSave() ? "Datos guardados." : "No se pudieron guardar en este navegador.";
});
labForm.addEventListener("input", () => { labStatus.textContent = ""; });

// ----- Enviar a la IA: reglas primero (sin IA) y, si pasan, se lo pide a Nexo en el chat -----
labForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (labBusy) return;
  labSetBusy(true);
  labStatus.textContent = "";
  let mensaje = "";
  try {
    const revision = await labRequest("preparar", labRead());
    const problemas = [];
    if (revision.errores.length) problemas.push(`Corrige estos datos: ${revision.errores.join(" ")}`);
    if (revision.faltantes.length) problemas.push(`Completa estos datos: ${revision.faltantes.join("; ")}.`);
    if (problemas.length) { labStatus.textContent = problemas.join(" "); return; }
    labSave();
    mensaje = `Genera la configuración Cisco IOS de mi práctica «${labRead().nombre}»: comandos, verificaciones y una advertencia breve.`;
  } catch (error) { labStatus.textContent = error.message; }
  finally { labSetBusy(false); }
  if (mensaje && typeof window.enviarANexo === "function") window.enviarANexo(mensaje);
});

// El panel de resultados comparte el comportamiento de copiado del chat.
document.getElementById("lab-result").addEventListener("click", async event => {
  const button = event.target.closest(".copy-button");
  if (!button) return;
  try { await navigator.clipboard.writeText(button.parentElement.querySelector("code").textContent); button.textContent = "Copiado"; }
  catch { button.textContent = "No disponible"; }
});

// Muestra el resumen de la sesión (oculto hasta que haya algo que mostrar).
function labShowResult(texto, estado) {
  const result = document.getElementById("lab-result");
  result.innerHTML = renderMarkdown(texto);
  renderTopologias(result);
  result.classList.remove("hidden");
  const etiqueta = document.getElementById("lab-result-state");
  etiqueta.textContent = estado;
  etiqueta.classList.remove("hidden");
  document.getElementById("lab-practica").hidden = false;
}

async function labLoadCases() {
  try {
    const consulta = new URLSearchParams();
    if (labFilter.value) consulta.set("estado", labFilter.value);
    if (labArchived.checked) consulta.set("archivados", "true");
    const casos = await labRequestRoot(`casos${consulta.size ? `?${consulta}` : ""}`);
    const selected = labCases.value;
    labCases.replaceChildren(...casos.map(caso => new Option(`${caso.nombre || "Sin nombre"} · ${LAB_ESTADOS[caso.estado] || caso.estado}${caso.archivado ? " · archivado" : ""} · ${caso.actualizado.slice(0, 16).replace("T", " ")}`, caso.id)));
    if (selected && casos.some(caso => caso.id === selected)) labCases.value = selected;
    const filtrando = !!labFilter.value || labArchived.checked;
    document.getElementById("lab-cases-empty").textContent = filtrando ? "No hay casos con este filtro." : "Aún no hay casos. Al generar una propuesta se guarda el caso para reabrirlo.";
    document.getElementById("lab-cases-empty").classList.toggle("hidden", casos.length > 0);
    labCases.closest(".lab-buttons").classList.toggle("hidden", casos.length === 0);
    labSetBusy(labBusy);
  } catch { /* La lista es opcional: el formulario sigue disponible. */ }
}

async function labRequestRoot(path) {
  const response = await fetch(`${API_BASE}/${path}`, { headers: labHeaders() });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo leer el caso.");
  return data;
}

document.getElementById("lab-reopen").addEventListener("click", async () => {
  if (labBusy || !labCases.value) return;
  labSetBusy(true);
  try {
    const caso = await labRequestRoot(`casos/${encodeURIComponent(labCases.value)}`);
    labFill(caso.tarea);
    labCaseId = caso.caso_id;
    labMarkArchived(caso.archivado);
    if (caso.propuesta) {
      const comprobacion = caso.propuesta.comprobacion_laboratorio;
      labShowResult(caso.propuesta.texto, `Práctica reabierta · ${comprobacion === "no_realizada" ? "pendiente de comprobar en laboratorio" : `comprobación en laboratorio: ${comprobacion}`}`);
    }
    labStatus.textContent = "";
    if (window.irAVista) window.irAVista("laboratorio");
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
    const response = await fetch(`${API_BASE}/casos/${encodeURIComponent(labCaseId)}/evidencias`, { method: "POST", headers: labHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ salida }) });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo analizar la salida.");
    labShowDiagnosis(data, data.omitidos);
    if (data.registradas.length) labEvidence.value = "";
    labDiagStatus.textContent = data.registradas.length ? `${data.registradas.length} evidencia(s) registrada(s). No se ejecutaron comandos.` : "No se registró ninguna evidencia nueva.";
    labLoadCases();
  } catch (error) { labDiagStatus.textContent = error.message; }
  finally { labSetBusy(false); }
});

// ----- Fase 5: informe, archivado y clave personal -----
function labMarkArchived(archived) {
  labArchivedCase = archived;
  document.getElementById("lab-archive").textContent = archived ? "Restaurar caso" : "Archivar caso";
}

document.getElementById("lab-report").addEventListener("click", async () => {
  if (labBusy || !labCaseId) return;
  labSetBusy(true);
  try {
    const data = await labRequestRoot(`casos/${encodeURIComponent(labCaseId)}/informe`);
    const url = URL.createObjectURL(new Blob([data.markdown], { type: "text/markdown;charset=utf-8" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: data.nombre_archivo });
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    labCasesStatus.textContent = `Informe descargado: ${data.nombre_archivo}`;
  } catch (error) { labCasesStatus.textContent = error.message; }
  finally { labSetBusy(false); }
});

document.getElementById("lab-archive").addEventListener("click", async () => {
  if (labBusy || !labCaseId) return;
  labSetBusy(true);
  try {
    const response = await fetch(`${API_BASE}/casos/${encodeURIComponent(labCaseId)}/archivado`, { method: "POST", headers: labHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ archivado: !labArchivedCase }) });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo cambiar el estado de archivo.");
    labMarkArchived(data.archivado);
    labCasesStatus.textContent = data.archivado ? "Caso archivado. Actívalo con «Incluir archivados»." : "Caso restaurado.";
    await labLoadCases();
  } catch (error) { labCasesStatus.textContent = error.message; }
  finally { labSetBusy(false); }
});

labFilter.append(...Object.entries(LAB_ESTADOS).map(([valor, texto]) => new Option(texto, valor)));
labFilter.addEventListener("change", labLoadCases);
labArchived.addEventListener("change", labLoadCases);
labUserInput.value = labUser();
labUserInput.addEventListener("change", () => {
  const value = labUserInput.value.trim();
  if (!/^[A-Za-z0-9_-]{16,64}$/.test(value)) { labCasesStatus.textContent = "Clave no válida: usa entre 16 y 64 letras, números, guion o guion bajo."; labUserInput.value = labUser(); return; }
  labUser.value = value;
  try { localStorage.setItem("netassist_usuario", value); } catch { /* solo esta pestaña */ }
  labCaseId = null; labMarkArchived(false); labResetDiagnosis(null);
  document.getElementById("lab-practica").hidden = true;
  labCasesStatus.textContent = "Clave cambiada. Se muestran los casos de esa clave.";
  labLoadCases();
});

// ----- Puente con el chat de Nexo -----
// Datos del formulario que acompañan a cada consulta del chat (solo si hay algo escrito).
window.labContexto = () => {
  const datos = labRead();
  const hayDatos = datos.nombre || datos.equipo.alias || datos.equipo.modelo || datos.vlans.some(v => Object.values(v).some(Boolean));
  if (!hayDatos) return "";
  const { tipo, objetivo, ...resto } = datos;
  if (!resto.equipo.ios) delete resto.equipo.ios;
  return JSON.stringify(resto, null, 2);
};
// Cuando Nexo termina una configuración o topología en el chat, aparece el resumen de la sesión
// y, si los datos del formulario pasan las reglas, se guarda como práctica (sin volver a llamar a la IA).
window.labDesdeChat = async (texto) => {
  labShowResult(texto, "Resumen de la sesión con Nexo · pendiente de comprobar en laboratorio");
  try {
    const data = await labRequest("guardar", { tarea: labRead(), resumen: texto, caso_id: labCaseId });
    labCaseId = data.caso_id;
    labMarkArchived(false);
    labResetDiagnosis(labCaseId);
    labLoadCases();
  } catch { /* Sin datos válidos en el formulario el resumen se muestra, pero no se guarda como práctica. */ }
  labSetBusy(labBusy);
};

labResetDiagnosis(null);
labLoadCases();
labRestore();

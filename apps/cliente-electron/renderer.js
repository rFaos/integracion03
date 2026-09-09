/**
 * ==============================================================================
 * PROYECTO: INTEGRACION03 - PROMPT 04 (CLIENTE DE ESCRITORIO ELECTRON)
 * ARCHIVO: renderer.js - Lógica del Cliente y Motor de Clasificación XML
 * AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
 * MATERIA: Integración de Aplicaciones Computacionales (SC-2236)
 * PROFESOR: Dr. Raúl Morales Salcedo
 * UNIVERSIDAD DE MONTERREY (UDEM) - PRIMAVERA 2026
 * ==============================================================================
 * 
 * DESCRIPCIÓN TÉCNICA:
 * Este archivo implementa la capa de presentación y análisis semántico del cliente
 * de escritorio Electron. Cumple estrictamente con las directrices del Prompt 04:
 * 1. Consume EXCLUSIVAMENTE datos en formato XML del microservicio en la nube (GCP).
 * 2. Captura Nombre y Apellido del usuario evaluador.
 * 3. Analiza descripciones técnicas mediante métodos independientes para cada
 *    categoría de servicio en la nube (IaaS, PaaS, SaaS, FaaS).
 * 4. Maneja CORS y ofrece compatibilidad con sobres SOAP (Sesión 04).
 */

const DEFAULT_CLOUD_URL = "http://34.51.75.114:5001";
const LOCALHOST_URL = "http://127.0.0.1:5000";

const CLOUD_LEXICON = {
  IaaS: [
    "iaas", "infraestructura", "infrastructure", "maquina virtual", "maquinas virtuales",
    "vm", "compute engine", "ec2", "servidor dedicado", "red", "redes", "vpc", "subnet",
    "almacenamiento en bloque", "disco persistente", "ebs", "enrutador", "firewall",
    "ip publica", "hipervisor", "hardware", "virtualizacion", "kvm", "bare metal",
    "particionamiento", "replicacion", "balanceador de carga"
  ],
  PaaS: [
    "paas", "plataforma", "platform", "app engine", "elastic beanstalk", "heroku",
    "runtime", "ciclo de desarrollo", "entorno administrado", "despliegue de codigo",
    "middleware", "base de datos administrada", "cloud sql", "rds", "orquestador",
    "kubernetes", "pods", "contenedores", "docker", "cgroups", "namespaces",
    "ci/cd", "pipeline", "framework de ejecucion"
  ],
  SaaS: [
    "saas", "software", "aplicacion final", "correo", "email", "google workspace",
    "microsoft 365", "salesforce", "crm", "erp", "ofimatica", "zoom", "dropbox",
    "consumo por navegador", "usuario final", "suscripcion", "sin mantenimiento tecnico",
    "software empaquetado", "servicio web terminado", "suite empresarial"
  ],
  FaaS: [
    "faas", "serverless", "sin servidor", "funciones efimeras", "cloud functions",
    "aws lambda", "azure functions", "ejecucion por eventos", "event-driven",
    "eventos http", "triggers", "pub/sub", "escalado a cero", "scale to zero",
    "microbilling", "pago por milisegundo", "tiempo de ejecucion corto", "stateless"
  ]
};

let cachedTopicsFromXml = [];

/**
 * Evalúa afinidad con Infraestructura como Servicio (IaaS)
 */
function classifyIaaS(text, xmlTopics) {
  const normalizedText = text.toLowerCase();
  let score = 0;
  const matchedKeywords = [];
  const matchedBookConcepts = [];

  for (const term of CLOUD_LEXICON.IaaS) {
    if (normalizedText.includes(term)) {
      score += 15;
      matchedKeywords.push(term);
    }
  }

  if (Array.isArray(xmlTopics)) {
    for (const item of xmlTopics) {
      const topicName = (item.tema || "").toLowerCase();
      const topicDesc = (item.descripcion || "").toLowerCase();
      if (topicName.includes("red") || topicName.includes("sistema") || topicName.includes("storage") || 
          topicDesc.includes("recursos de computacion") || topicDesc.includes("particionamiento")) {
        if (normalizedText.includes(topicName) || normalizedText.split(/\s+/).some(w => w.length > 4 && topicDesc.includes(w))) {
          score += 20;
          matchedBookConcepts.push({ libro: item.libro, tema: item.tema, isbn: item.isbn });
        }
      }
    }
  }

  return {
    modelo: "IaaS",
    nombreCompleto: "Infrastructure as a Service (IaaS)",
    score: score,
    keywords: [...new Set(matchedKeywords)],
    bookMatches: matchedBookConcepts,
    justificacion: "El texto se enfoca en recursos fundamentales de computación, redes (VPC), almacenamiento en bloque, particionamiento de bajo nivel o virtualización de hardware."
  };
}

/**
 * Evalúa afinidad con Plataforma como Servicio (PaaS)
 */
function classifyPaaS(text, xmlTopics) {
  const normalizedText = text.toLowerCase();
  let score = 0;
  const matchedKeywords = [];
  const matchedBookConcepts = [];

  for (const term of CLOUD_LEXICON.PaaS) {
    if (normalizedText.includes(term)) {
      score += 15;
      matchedKeywords.push(term);
    }
  }

  if (Array.isArray(xmlTopics)) {
    for (const item of xmlTopics) {
      const topicName = (item.tema || "").toLowerCase();
      const topicDesc = (item.descripcion || "").toLowerCase();
      if (topicName.includes("contenedor") || topicName.includes("kubernetes") || topicName.includes("microservice") ||
          topicDesc.includes("plataforma") || topicDesc.includes("aislamiento") || topicDesc.includes("orquestador")) {
        if (normalizedText.includes(topicName) || normalizedText.split(/\s+/).some(w => w.length > 4 && topicDesc.includes(w))) {
          score += 20;
          matchedBookConcepts.push({ libro: item.libro, tema: item.tema, isbn: item.isbn });
        }
      }
    }
  }

  return {
    modelo: "PaaS",
    nombreCompleto: "Platform as a Service (PaaS)",
    score: score,
    keywords: [...new Set(matchedKeywords)],
    bookMatches: matchedBookConcepts,
    justificacion: "El texto hace referencia a runtimes de ejecución administrados, contenedores, orquestación de servicios o entornos de desarrollo donde el proveedor gestiona el SO subyacente."
  };
}

/**
 * Evalúa afinidad con Software como Servicio (SaaS)
 */
function classifySaaS(text, xmlTopics) {
  const normalizedText = text.toLowerCase();
  let score = 0;
  const matchedKeywords = [];
  const matchedBookConcepts = [];

  for (const term of CLOUD_LEXICON.SaaS) {
    if (normalizedText.includes(term)) {
      score += 15;
      matchedKeywords.push(term);
    }
  }

  if (Array.isArray(xmlTopics)) {
    for (const item of xmlTopics) {
      const topicName = (item.tema || "").toLowerCase();
      const topicDesc = (item.descripcion || "").toLowerCase();
      if (topicName.includes("software") || topicName.includes("usuario") || topicDesc.includes("empaquetado") ||
          topicDesc.includes("servicio web") || topicDesc.includes("crm") || topicDesc.includes("ofimatica")) {
        if (normalizedText.includes(topicName) || normalizedText.split(/\s+/).some(w => w.length > 4 && topicDesc.includes(w))) {
          score += 20;
          matchedBookConcepts.push({ libro: item.libro, tema: item.tema, isbn: item.isbn });
        }
      }
    }
  }

  return {
    modelo: "SaaS",
    nombreCompleto: "Software as a Service (SaaS)",
    score: score,
    keywords: [...new Set(matchedKeywords)],
    bookMatches: matchedBookConcepts,
    justificacion: "El texto describe aplicaciones listas para su consumo final directo vía navegador, sin gestión técnica de infraestructura ni desarrollo de software por parte del cliente."
  };
}

/**
 * Evalúa afinidad con Funciones como Servicio (FaaS / Serverless)
 */
function classifyFaaS(text, xmlTopics) {
  const normalizedText = text.toLowerCase();
  let score = 0;
  const matchedKeywords = [];
  const matchedBookConcepts = [];

  for (const term of CLOUD_LEXICON.FaaS) {
    if (normalizedText.includes(term)) {
      score += 15;
      matchedKeywords.push(term);
    }
  }

  if (Array.isArray(xmlTopics)) {
    for (const item of xmlTopics) {
      const topicName = (item.tema || "").toLowerCase();
      const topicDesc = (item.descripcion || "").toLowerCase();
      if (topicName.includes("serverless") || topicName.includes("function") || topicName.includes("event") ||
          topicDesc.includes("efimera") || topicDesc.includes("eventos") || topicDesc.includes("escalado a cero")) {
        if (normalizedText.includes(topicName) || normalizedText.split(/\s+/).some(w => w.length > 4 && topicDesc.includes(w))) {
          score += 20;
          matchedBookConcepts.push({ libro: item.libro, tema: item.tema, isbn: item.isbn });
        }
      }
    }
  }

  return {
    modelo: "FaaS",
    nombreCompleto: "Function as a Service (FaaS / Serverless)",
    score: score,
    keywords: [...new Set(matchedKeywords)],
    bookMatches: matchedBookConcepts,
    justificacion: "El texto enfatiza ejecución de código efímero y stateless disparado por eventos (HTTP/PubSub) con facturación por tiempo de cómputo y escalado automático a cero."
  };
}

/**
 * Consulta el endpoint XML en la nube y lo procesa con DOMParser
 */
async function fetchCatalogTopicsFromXml(baseUrl) {
  const endpointUrl = `${baseUrl.replace(/\/+$/, '')}/books/temas?format=XML`;
  logToConsole(`[HTTP GET] Solicitando catalogo en formato XML puro a: ${endpointUrl}`);

  const response = await fetch(endpointUrl, {
    method: "GET",
    headers: {
      "Accept": "application/xml, text/xml, */*"
    }
  });

  if (!response.ok) {
    throw new Error(`Fallo HTTP al consultar microservicio: ${response.status} ${response.statusText}`);
  }

  const rawXmlText = await response.text();
  logToConsole(`[XML RECIBIDO] Tamaño del payload XML: ${rawXmlText.length} bytes`);

  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(rawXmlText, "application/xml");

  const parserError = xmlDoc.querySelector("parsererror");
  if (parserError) {
    throw new Error(`Error en el formato del XML recibido: ${parserError.textContent}`);
  }

  const extractedTopics = [];
  const libroNodes = xmlDoc.querySelectorAll("libro");

  libroNodes.forEach(libroNode => {
    const isbn = libroNode.getAttribute("isbn") || "Sin ISBN";
    const nombreLibro = libroNode.querySelector("nombre_libro") ? libroNode.querySelector("nombre_libro").textContent : "Libro desconocido";
    
    const temaNodes = libroNode.querySelectorAll("temas > tema");
    temaNodes.forEach(temaNode => {
      const nombreTema = temaNode.querySelector("nombre") ? temaNode.querySelector("nombre").textContent : "";
      const descTema = temaNode.querySelector("descripcion") ? temaNode.querySelector("descripcion").textContent : "";
      const refTema = temaNode.querySelector("referencia") ? temaNode.querySelector("referencia").textContent : "";

      extractedTopics.push({
        isbn: isbn,
        libro: nombreLibro,
        tema: nombreTema,
        descripcion: descTema,
        referencia: refTema
      });
    });
  });

  logToConsole(`[XML PARSED] Éxito: Se extrajeron ${extractedTopics.length} conceptos de ${libroNodes.length} libros en catálogo.`);
  cachedTopicsFromXml = extractedTopics;

  return {
    rawXml: rawXmlText,
    topics: extractedTopics,
    totalBooks: libroNodes.length
  };
}

async function sendSoapRegistration(baseUrl, payload) {
  const soapEndpoint = `${baseUrl.replace(/\/+$/, '')}/soap`;
  const soapEnvelope = `<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:m="http://udem.edu/sc3705/soap/library">
  <soap:Body>
    <m:RegistrarClasificacionRequest>
      <m:nombre>${escapeXml(payload.nombre)}</m:nombre>
      <m:apellidos>${escapeXml(payload.apellidos)}</m:apellidos>
      <m:correo>${escapeXml(payload.correo)}</m:correo>
      <m:isbn>${escapeXml(payload.isbn || '978-1492056010')}</m:isbn>
      <m:concept_id>${payload.concept_id || 1}</m:concept_id>
      <m:texto_evaluado>${escapeXml(payload.texto)}</m:texto_evaluado>
      <m:modelo_cloud>${payload.modelo}</m:modelo_cloud>
      <m:justificacion>${escapeXml(payload.justificacion)}</m:justificacion>
    </m:RegistrarClasificacionRequest>
  </soap:Body>
</soap:Envelope>`;

  logToConsole(`[SOAP POST] Enviando sobre SOAP Envelope a: ${soapEndpoint}`);
  
  const response = await fetch(soapEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": "text/xml; charset=utf-8",
      "SOAPAction": "http://udem.edu/sc3705/soap/library/RegistrarClasificacion"
    },
    body: soapEnvelope
  });

  const responseText = await response.text();
  logToConsole(`[SOAP RESPUESTA] HTTP Status: ${response.status}`);

  return {
    status: response.status,
    rawXml: responseText
  };
}

function escapeXml(unsafe) {
  return (unsafe || '').toString().replace(/[<>&'"]/g, function (c) {
    switch (c) {
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '&': return '&amp;';
      case "'": return '&apos;';
      case '"': return '&quot;';
    }
  });
}

async function handleAnalyzeClick() {
  const nombreInput = document.getElementById("inputNombre").value.trim();
  const apellidosInput = document.getElementById("inputApellidos").value.trim();
  const correoInput = document.getElementById("inputCorreo").value.trim();
  const textoInput = document.getElementById("inputText").value.trim();
  const serverUrl = document.getElementById("inputServerUrl").value.trim() || DEFAULT_CLOUD_URL;
  const protocolMode = document.getElementById("selectProtocol").value;

  if (!nombreInput || !apellidosInput) {
    alert("Por favor ingrese el Nombre y Apellido del evaluador.");
    document.getElementById("inputNombre").focus();
    return;
  }
  if (!textoInput) {
    alert("Por favor ingrese palabras, frases o una descripción relacionada con Cloud Computing.");
    document.getElementById("inputText").focus();
    return;
  }

  setLoadingState(true);
  logToConsole(`\n--- NUEVO ANÁLISIS SOLICITADO ---`);
  logToConsole(`Evaluador: ${nombreInput} ${apellidosInput} (${correoInput || 'Sin correo'})`);
  logToConsole(`Texto de entrada: "${textoInput}"`);

  try {
    if (cachedTopicsFromXml.length === 0) {
      const xmlData = await fetchCatalogTopicsFromXml(serverUrl);
      displayRawXml(xmlData.rawXml);
    }

    const resIaaS = classifyIaaS(textoInput, cachedTopicsFromXml);
    const resPaaS = classifyPaaS(textoInput, cachedTopicsFromXml);
    const resSaaS = classifySaaS(textoInput, cachedTopicsFromXml);
    const resFaaS = classifyFaaS(textoInput, cachedTopicsFromXml);

    const allResults = [resIaaS, resPaaS, resSaaS, resFaaS];
    allResults.sort((a, b) => b.score - a.score);
    const winner = allResults[0];

    const totalScore = allResults.reduce((acc, curr) => acc + curr.score, 0);
    const confidence = totalScore > 0 ? Math.round((winner.score / totalScore) * 100) : 50;

    logToConsole(`[DIAGNÓSTICO FINAL] Modelo Ganador: ${winner.modelo} (Score: ${winner.score}, Confianza: ${confidence}%)`);

    renderResults(winner, allResults, totalScore, confidence, {
      nombre: nombreInput,
      apellidos: apellidosInput,
      correo: correoInput,
      texto: textoInput
    });

    if (protocolMode === "SOAP" && correoInput) {
      logToConsole(`[MODO SOAP] Despachando sobre SOAP para registrar la clasificación en PostgreSQL...`);
      const soapRes = await sendSoapRegistration(serverUrl, {
        nombre: nombreInput,
        apellidos: apellidosInput,
        correo: correoInput,
        texto: textoInput,
        modelo: winner.modelo,
        justificacion: winner.justificacion,
        concept_id: winner.bookMatches.length > 0 ? 1 : 4
      });

      if (soapRes.status === 409) {
        logToConsole(`⚠️ [SOAP FAULT 409 RECIBIDO] El concepto ya fue clasificado previamente por este usuario en PostgreSQL.`);
        showToast("⚠️ SOAP Fault 409: Concepto ya clasificado por este usuario.", "warning");
      } else if (soapRes.status === 200) {
        logToConsole(`✅ [SOAP 200 OK] Clasificación registrada exitosamente en PostgreSQL (tabla clasificaciones_cloud).`);
        showToast("✅ Clasificación registrada en la base de datos vía SOAP.", "success");
      }
      displayRawXml(soapRes.rawXml);
    }

  } catch (error) {
    logToConsole(`❌ [ERROR]: ${error.message}`);
    alert(`Ocurrió un error al procesar el análisis: ${error.message}\n\nAsegúrese de que el microservicio esté corriendo en ${serverUrl}`);
  } finally {
    setLoadingState(false);
  }
}

function renderResults(winner, allResults, totalScore, confidence, userInfo) {
  const resultCard = document.getElementById("resultCard");
  const winnerBadge = document.getElementById("winnerBadge");
  const winnerTitle = document.getElementById("winnerTitle");
  const winnerDesc = document.getElementById("winnerDesc");
  const confidenceBar = document.getElementById("confidenceBar");
  const confidenceText = document.getElementById("confidenceText");
  const breakdownList = document.getElementById("breakdownList");
  const bookReferences = document.getElementById("bookReferences");

  resultCard.style.display = "block";
  resultCard.scrollIntoView({ behavior: "smooth" });

  winnerBadge.textContent = winner.modelo;
  winnerBadge.className = `model-pill pill-${winner.modelo.toLowerCase()}`;
  winnerTitle.textContent = winner.nombreCompleto;
  winnerDesc.textContent = winner.justificacion;

  confidenceBar.style.width = `${confidence}%`;
  confidenceText.textContent = `${confidence}% de afinidad identificada`;

  breakdownList.innerHTML = allResults.map(item => {
    const pct = totalScore > 0 ? Math.round((item.score / totalScore) * 100) : 0;
    return `
      <div class="score-row">
        <span class="score-model">${item.modelo}</span>
        <div class="score-track">
          <div class="score-fill fill-${item.modelo.toLowerCase()}" style="width: ${pct}%"></div>
        </div>
        <span class="score-pct">${pct}% (${item.score} pts)</span>
      </div>
    `;
  }).join("");

  if (winner.bookMatches && winner.bookMatches.length > 0) {
    bookReferences.innerHTML = `
      <h4 style="margin-top: 1rem; margin-bottom: 0.5rem; color: #38bdf8; font-size: 0.95rem;">
        📚 Libros del Catálogo XML que avalan esta clasificación:
      </h4>
      <ul style="list-style: none; padding-left: 0; font-size: 0.85rem; color: #cbd5e1;">
        ${winner.bookMatches.map(m => `
          <li style="margin-bottom: 0.35rem; padding: 0.4rem 0.6rem; background: rgba(255,255,255,0.03); border-radius: 4px; border-left: 3px solid #38bdf8;">
            <strong>${m.libro}</strong> (ISBN: <code>${m.isbn}</code>) — Concepto: <em>${m.tema}</em>
          </li>
        `).join("")}
      </ul>
    `;
  } else {
    bookReferences.innerHTML = `
      <p style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.75rem; font-style: italic;">
        ℹ️ Clasificación fundamentada en reglas heurísticas del léxico formal de Cloud Computing.
      </p>
    `;
  }
}

function logToConsole(message) {
  const consoleElem = document.getElementById("xmlConsole");
  if (consoleElem) {
    const timeStr = new Date().toLocaleTimeString();
    consoleElem.textContent += `[${timeStr}] ${message}\n`;
    consoleElem.scrollTop = consoleElem.scrollHeight;
  }
}

function displayRawXml(xmlText) {
  const xmlDisplay = document.getElementById("rawXmlPayload");
  if (xmlDisplay) {
    xmlDisplay.textContent = xmlText;
  }
}

function setLoadingState(isLoading) {
  const btn = document.getElementById("btnAnalyze");
  if (btn) {
    btn.disabled = isLoading;
    btn.textContent = isLoading ? "Analizando XML de la Nube..." : "Analizar y Clasificar (XML)";
  }
}

function showToast(msg, type) {
  const toast = document.getElementById("toastNotification");
  if (toast) {
    toast.textContent = msg;
    toast.className = `toast-box show toast-${type}`;
    setTimeout(() => {
      toast.className = "toast-box";
    }, 4500);
  }
}

const SAMPLE_QUERIES = {
  iaas: "Necesito aprovisionar máquinas virtuales en Compute Engine con una VPC personalizada, subredes privadas y almacenamiento persistente en bloques para soportar particionamiento.",
  paas: "Queremos desplegar nuestros contenedores y Pods en Kubernetes sin gestionar servidores físicos, utilizando Google App Engine y un runtime administrado con integración CI/CD.",
  saas: "La empresa migrará sus cuentas corporativas a Google Workspace y una plataforma de CRM en la nube consumida 100% por navegador web sin requerir instalación local.",
  faas: "Buscamos implementar funciones sin servidor efímeras en Cloud Functions que se activen automáticamente ante eventos HTTP y escalen a cero cuando no haya tráfico."
};

function insertSample(type) {
  const input = document.getElementById("inputText");
  if (input && SAMPLE_QUERIES[type]) {
    input.value = SAMPLE_QUERIES[type];
  }
}

document.addEventListener("DOMContentLoaded", () => {
  logToConsole("Iniciando Cliente Electron XML para SC3705...");
  logToConsole(`Instancia remota objetivo: ${DEFAULT_CLOUD_URL}`);

  document.getElementById("btnAnalyze").addEventListener("click", handleAnalyzeClick);
  
  document.getElementById("btnLoadXml").addEventListener("click", async () => {
    const serverUrl = document.getElementById("inputServerUrl").value.trim() || DEFAULT_CLOUD_URL;
    try {
      setLoadingState(true);
      const res = await fetchCatalogTopicsFromXml(serverUrl);
      displayRawXml(res.rawXml);
      showToast(`Catálogo XML cargado: ${res.topics.length} temas disponibles.`, "success");
    } catch (err) {
      logToConsole(`Error al cargar catálogo XML: ${err.message}`);
      alert(`Error al conectar con la instancia cloud: ${err.message}`);
    } finally {
      setLoadingState(false);
    }
  });

  document.getElementById("btnTestHealth").addEventListener("click", async () => {
    const serverUrl = document.getElementById("inputServerUrl").value.trim() || DEFAULT_CLOUD_URL;
    const healthUrl = `${serverUrl.replace(/\/+$/, '')}/health`;
    logToConsole(`Comprobando conectividad en: ${healthUrl}`);
    try {
      const res = await fetch(healthUrl);
      const data = await res.json();
      logToConsole(`Estado del servidor: ${JSON.stringify(data)}`);
      showToast(`Servidor ONLINE: Base de datos ${data.database}`, "success");
    } catch (e) {
      logToConsole(`Fallo de conexión: ${e.message}`);
      showToast("Fallo al conectar con el servidor", "danger");
    }
  });

  document.getElementById("btnClearConsole").addEventListener("click", () => {
    document.getElementById("xmlConsole").textContent = "";
  });
});

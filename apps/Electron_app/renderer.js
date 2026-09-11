/**
 * ==============================================================================
 * PROYECTO: INTEGRACION03 - CLASIFICADOR DE LIBROS CLOUD (ELECTRON_APP)
 * ARCHIVO: renderer.js - Lógica del Cliente y Motor de Clasificación XML
 * AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
 * MATERIA: Integración de Aplicaciones Computacionales (SC-2236)
 * PROFESOR: Dr. Raúl Morales Salcedo
 * UNIVERSIDAD DE MONTERREY (UDEM) - PRIMAVERA 2026
 * ==============================================================================
 */

const DEFAULT_CLOUD_URL = "http://34.51.8.146:5001";
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
let cachedBooksFromXml = [];

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
    justificacion: "El libro o texto se enfoca en recursos fundamentales de computación física/virtual, redes (VPC), almacenamiento en bloques persistentes, particionamiento de bajo nivel o virtualización de hardware."
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
      if (topicName.includes("plataforma") || topicName.includes("kubernetes") || topicName.includes("contenedor") ||
          topicDesc.includes("runtime") || topicDesc.includes("despliegue") || topicDesc.includes("microservices") ||
          topicDesc.includes("api gateway") || topicDesc.includes("middleware")) {
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
    justificacion: "El libro o texto hace referencia a runtimes de ejecución administrados, contenedores, Kubernetes, orquestación de servicios, microservicios o entornos de despliegue donde el proveedor gestiona el SO subyacente."
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
    justificacion: "El libro o texto describe aplicaciones completas y listas para su consumo directo por el usuario final vía web/navegador, sin gestión técnica de infraestructura ni mantenimiento de código por parte del cliente."
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
    justificacion: "El libro o texto enfatiza arquitecturas Serverless y ejecución de código efímero y stateless disparado por eventos (HTTP/triggers) con facturación por tiempo de cómputo y autoescalado a cero."
  };
}

/**
 * Consulta el endpoint XML en la nube y extrae libros y temas con DOMParser
 */
async function fetchCatalogTopicsFromXml(baseUrl) {
  const endpointUrl = `${baseUrl.replace(/\/+$/, '')}/books/temas?format=XML`;
  logToConsole(`[HTTP GET] Solicitando catalogo en XML a: ${endpointUrl}`);

  const response = await fetch(endpointUrl, {
    method: "GET",
    headers: {
      "Accept": "application/xml, text/xml, */*"
    }
  });

  if (!response.ok) {
    throw new Error(`Fallo HTTP: ${response.status} ${response.statusText}`);
  }

  const rawXmlText = await response.text();
  logToConsole(`[XML RECIBIDO] ${rawXmlText.length} bytes recibidos.`);

  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(rawXmlText, "application/xml");

  const parserError = xmlDoc.querySelector("parsererror");
  if (parserError) {
    throw new Error(`Error en formato XML: ${parserError.textContent}`);
  }

  const extractedTopics = [];
  const extractedBooks = [];
  const libroNodes = xmlDoc.querySelectorAll("libro");

  libroNodes.forEach(libroNode => {
    const isbn = libroNode.getAttribute("isbn") || "Sin ISBN";
    const nombreLibroNode = libroNode.querySelector("nombre_libro");
    const nombreLibro = nombreLibroNode ? nombreLibroNode.textContent.trim() : "Libro desconocido";
    
    const bookTopics = [];
    const temaNodes = libroNode.querySelectorAll("temas > tema");
    temaNodes.forEach(temaNode => {
      const nombreTema = temaNode.querySelector("nombre") ? temaNode.querySelector("nombre").textContent.trim() : "";
      const descTema = temaNode.querySelector("descripcion") ? temaNode.querySelector("descripcion").textContent.trim() : "";
      const refTema = temaNode.querySelector("referencia") ? temaNode.querySelector("referencia").textContent.trim() : "";

      const topicObj = {
        isbn: isbn,
        libro: nombreLibro,
        tema: nombreTema,
        descripcion: descTema,
        referencia: refTema
      };

      bookTopics.push(topicObj);
      extractedTopics.push(topicObj);
    });

    extractedBooks.push({
      isbn: isbn,
      titulo: nombreLibro,
      temas: bookTopics
    });
  });

  logToConsole(`[XML PARSED] Éxito: Se extrajeron ${extractedTopics.length} conceptos de ${extractedBooks.length} libros en catálogo.`);
  cachedTopicsFromXml = extractedTopics;
  cachedBooksFromXml = extractedBooks;

  populateBookSelector(extractedBooks);

  return {
    rawXml: rawXmlText,
    topics: extractedTopics,
    books: extractedBooks,
    totalBooks: extractedBooks.length
  };
}

function populateBookSelector(books) {
  const select = document.getElementById("selectBook");
  if (!select) return;

  select.innerHTML = '<option value="">-- Selecciona un libro del catálogo XML para clasificar --</option>';
  books.forEach(b => {
    const opt = document.createElement("option");
    opt.value = b.isbn;
    opt.textContent = `${b.titulo} (${b.isbn}) - [${b.temas.length} temas]`;
    select.appendChild(opt);
  });

  select.onchange = function() {
    const selectedIsbn = select.value;
    if (!selectedIsbn) {
      document.getElementById("selectedBookInfo").style.display = "none";
      return;
    }

    const book = cachedBooksFromXml.find(b => b.isbn === selectedIsbn);
    if (!book) return;

    document.getElementById("selectedBookInfo").style.display = "block";
    document.getElementById("lblIsbn").textContent = book.isbn;
    document.getElementById("lblTopicCount").textContent = `${book.temas.length} concepto(s)`;

    // Auto-fill textarea with book details and technical descriptions
    let autoText = `Libro: ${book.titulo}\nISBN: ${book.isbn}\n`;
    if (book.temas.length > 0) {
      autoText += "Temas Técnicos de Cloud:\n";
      book.temas.forEach(t => {
        autoText += `• ${t.tema}: ${t.descripcion} (${t.referencia})\n`;
      });
    } else {
      autoText += "Temas: Arquitectura limpia, desarrollo de software modular, desacoplamiento de capas y buenas prácticas.";
    }

    document.getElementById("inputText").value = autoText;
    logToConsole(`[LIBRO SELECCIONADO] ${book.titulo} (ISBN: ${book.isbn}). Información cargada al formulario.`);
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
      <m:isbn>${escapeXml(payload.isbn || '978-1491973042')}</m:isbn>
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
  const selectedIsbn = document.getElementById("selectBook").value;

  if (!nombreInput || !apellidosInput) {
    alert("Por favor ingrese el Nombre y Apellido del evaluador.");
    document.getElementById("inputNombre").focus();
    return;
  }
  if (!textoInput) {
    alert("Por favor seleccione un libro o ingrese palabras/descripción técnica para clasificar.");
    document.getElementById("inputText").focus();
    return;
  }

  setLoadingState(true);
  logToConsole(`\n--- CLASIFICANDO LIBRO (XML) ---`);
  logToConsole(`Evaluador: ${nombreInput} ${apellidosInput} (${correoInput || 'Sin correo'})` );
  logToConsole(`Texto de entrada: "${textoInput.substring(0, 100)}..."`);

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

    logToConsole(`[DIAGNÓSTICO] Libro Clasificado como: ${winner.modelo} (Confianza: ${confidence}%)`);

    const selectedBook = cachedBooksFromXml.find(b => b.isbn === selectedIsbn);

    renderResults(winner, allResults, totalScore, confidence, {
      nombre: nombreInput,
      apellidos: apellidosInput,
      correo: correoInput,
      texto: textoInput,
      libro: selectedBook
    });

    if (protocolMode === "SOAP" && correoInput) {
      logToConsole(`[MODO SOAP] Despachando sobre SOAP para registrar clasificación en PostgreSQL...`);
      const soapRes = await sendSoapRegistration(serverUrl, {
        nombre: nombreInput,
        apellidos: apellidosInput,
        correo: correoInput,
        isbn: selectedIsbn || '978-1491973042',
        texto: textoInput,
        modelo: winner.modelo,
        justificacion: winner.justificacion,
        concept_id: 1
      });

      if (soapRes.status === 409) {
        logToConsole(`⚠️ [SOAP FAULT 409] El concepto ya fue clasificado previamente por este usuario.`);
        showToast("⚠️ SOAP Fault 409: Concepto ya clasificado por este usuario.", "warning");
      } else if (soapRes.status === 200) {
        logToConsole(`✅ [SOAP 200 OK] Clasificación registrada en PostgreSQL (clasificaciones_cloud).`);
        showToast("✅ Clasificación registrada en base de datos vía SOAP.", "success");
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

function renderResults(winner, allResults, totalScore, confidence, info) {
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
  
  if (info.libro) {
    winnerTitle.textContent = `${info.libro.titulo} ➔ ${winner.nombreCompleto}`;
  } else {
    winnerTitle.textContent = winner.nombreCompleto;
  }
  
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
        📚 Conceptos y Libros del Catálogo XML que justifican este dictamen:
      </h4>
      <ul style="list-style: none; padding-left: 0; font-size: 0.85rem; color: #cbd5e1;">
        ${winner.bookMatches.map(m => `
          <li style="margin-bottom: 0.35rem; padding: 0.4rem 0.6rem; background: rgba(255,255,255,0.03); border-radius: 4px; border-left: 3px solid #38bdf8;">
            <strong>${m.libro}</strong> (ISBN: <code>${m.isbn}</code>) — Tema: <em>${m.tema}</em>
          </li>
        `).join("")}
      </ul>
    `;
  } else {
    bookReferences.innerHTML = "";
  }

  showToast(`¡Libro clasificado exitosamente como ${winner.modelo}!`, "success");
}

function logToConsole(message) {
  const consoleEl = document.getElementById("consoleLogs");
  if (!consoleEl) return;
  const timestamp = new Date().toLocaleTimeString();
  consoleEl.textContent += `[${timestamp}] ${message}\n`;
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

function displayRawXml(rawXml) {
  const viewer = document.getElementById("rawXmlViewer");
  if (!viewer) return;
  viewer.textContent = rawXml;
}

function showToast(text, type = "info") {
  const toast = document.getElementById("toastNotification");
  if (!toast) return;
  toast.textContent = text;
  toast.className = `toast-box toast-${type} show`;
  setTimeout(() => {
    toast.className = "toast-box";
  }, 4000);
}

function setLoadingState(isLoading) {
  const btn = document.getElementById("btnAnalyze");
  if (!btn) return;
  if (isLoading) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Clasificando...';
  } else {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">⚡</span> Clasificar Libro (XML)';
  }
}

function insertSample(type) {
  const samples = {
    iaas: "Este libro cubre infraestructura como servicio: aprovisionamiento de máquinas virtuales (VM), VPC, subredes, discos persistentes en bloque, balanceadores de carga y reglas de firewall.",
    paas: "Este libro aborda plataformas como servicio: despliegue de contenedores en Kubernetes, gestión de Pods, microservicios distribuidos, API Gateways, middleware y runtimes de ejecución.",
    saas: "Este libro analiza aplicaciones de software como servicio listas para el usuario final: correo electrónico en la nube, ofimática web, CRM, ERP y suites colaborativas consumidas vía navegador.",
    faas: "Este libro se especializa en arquitecturas serverless y funciones como servicio (FaaS): Cloud Functions, AWS Lambda, ejecución disparada por eventos HTTP o triggers y escalado automático a cero."
  };

  const textEl = document.getElementById("inputText");
  if (textEl && samples[type]) {
    textEl.value = samples[type];
    logToConsole(`[EJEMPLO CARGADO] Se insertó descripción de prueba para: ${type.toUpperCase()}`);
  }
}

async function checkServerHealth() {
  const serverUrl = document.getElementById("inputServerUrl").value.trim() || DEFAULT_CLOUD_URL;
  const statusBadge = document.getElementById("serverStatusBadge");
  const statusText = document.getElementById("serverStatusText");

  statusBadge.className = "status-badge checking";
  statusText.textContent = "Verificando conexión...";
  logToConsole(`[HEALTH CHECK] Conectando a ${serverUrl}/health...`);

  try {
    const res = await fetch(`${serverUrl.replace(/\/+$/, '')}/health`, { method: "GET" });
    if (res.ok) {
      const data = await res.json();
      statusBadge.className = "status-badge online";
      statusText.textContent = `Servidor ONLINE: Base de datos connected`;
      logToConsole(`✅ [HEALTH OK] Microservicio activo en Google Cloud. PostgreSQL conectado.`);
      showToast("Conexión con la nube verificada exitosamente.", "success");
      
      // Auto-load books catalog
      fetchCatalogTopicsFromXml(serverUrl).then(data => {
        displayRawXml(data.rawXml);
      }).catch(e => logToConsole(`Advertencia al cargar catalogo: ${e.message}`));

    } else {
      throw new Error(`Status ${res.status}`);
    }
  } catch (err) {
    statusBadge.className = "status-badge offline";
    statusText.textContent = "Servidor OFFLINE / Error de Conexión";
    logToConsole(`❌ [HEALTH ERROR] No se pudo contactar a ${serverUrl}: ${err.message}`);
    showToast("Error de conexión con el microservicio en la nube.", "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btnAnalyze").addEventListener("click", handleAnalyzeClick);
  document.getElementById("btnTestHealth").addEventListener("click", checkServerHealth);
  document.getElementById("btnReloadBooks").addEventListener("click", () => {
    const url = document.getElementById("inputServerUrl").value.trim() || DEFAULT_CLOUD_URL;
    fetchCatalogTopicsFromXml(url);
  });
  document.getElementById("btnLoadXml").addEventListener("click", async () => {
    const url = document.getElementById("inputServerUrl").value.trim() || DEFAULT_CLOUD_URL;
    try {
      const data = await fetchCatalogTopicsFromXml(url);
      displayRawXml(data.rawXml);
      showToast("Catálogo XML recibido y mostrado en consola.", "info");
    } catch (e) {
      alert(`Error al obtener XML: ${e.message}`);
    }
  });
  document.getElementById("btnClearConsole").addEventListener("click", () => {
    document.getElementById("consoleLogs").textContent = "";
    document.getElementById("rawXmlViewer").textContent = "<!-- Consola limpia -->";
  });

  // Automatic connection test on launch
  setTimeout(checkServerHealth, 600);
});

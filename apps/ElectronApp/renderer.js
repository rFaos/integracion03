/**
 * ==============================================================================
 * PROYECTO: INTEGRACION03 - CATALOGO DE LIBROS EN ELECTRON (WINDOWS 11)
 * ARCHIVO: renderer.js - Lógica de Presentación, Paginación y Consumo XML
 * AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
 * MATERIA: Integración de Aplicaciones Computacionales (SC-2236)
 * PROFESOR: Dr. Raúl Morales Salcedo
 * UNIVERSIDAD DE MONTERREY (UDEM) - PRIMAVERA 2026
 * ==============================================================================
 * 
 * ESPECIFICACIONES CUMPLIDAS:
 * 1. GUI Profesional con Cards (Imagen, Autor, ISBN, Stock, Año, Género, Precio).
 * 2. Paginación y Carga por Petición en demanda.
 * 3. Consumo EXCLUSIVAMENTE de XML desde el microservicio remoto.
 * 4. URL y Endpoint configurables y persistentes en LocalStorage.
 * 5. Procesamiento del árbol XML mediante DOMParser nativo.
 */

const DEFAULT_BASE_URL = "http://34.51.8.146:5001";
const DEFAULT_ENDPOINT = "/books";

// Estado de la Aplicación
let allBooksFromXml = [];
let filteredBooks = [];
let currentPage = 1;
let pageSize = 6;
let latestRawXml = "";

/**
 * Carga la configuración persistente desde LocalStorage
 */
function loadConfig() {
  const savedBase = localStorage.getItem("catalog_api_base_url") || DEFAULT_BASE_URL;
  const savedEndpoint = localStorage.getItem("catalog_api_endpoint") || DEFAULT_ENDPOINT;

  document.getElementById("inputBaseUrl").value = savedBase;
  document.getElementById("inputEndpoint").value = savedEndpoint;

  return {
    baseUrl: savedBase.trim(),
    endpoint: savedEndpoint.trim()
  };
}

/**
 * Guarda la configuración en LocalStorage
 */
function saveConfig() {
  const baseUrl = document.getElementById("inputBaseUrl").value.trim();
  const endpoint = document.getElementById("inputEndpoint").value.trim();

  if (!baseUrl || !endpoint) {
    showToast("La URL y el EndPoint no pueden estar vacíos.", "error");
    return;
  }

  localStorage.setItem("catalog_api_base_url", baseUrl);
  localStorage.setItem("catalog_api_endpoint", endpoint);

  showToast("Configuración guardada en LocalStorage exitosamente.", "success");
  loadCatalogOnDemand();
}

/**
 * Restablece la configuración por defecto
 */
function resetConfig() {
  localStorage.removeItem("catalog_api_base_url");
  localStorage.removeItem("catalog_api_endpoint");
  document.getElementById("inputBaseUrl").value = DEFAULT_BASE_URL;
  document.getElementById("inputEndpoint").value = DEFAULT_ENDPOINT;
  showToast("Configuración restablecida a valores por defecto.", "info");
  loadCatalogOnDemand();
}

/**
 * Consume EXCLUSIVAMENTE XML desde el microservicio y parsea con DOMParser
 */
async function loadCatalogOnDemand() {
  const config = loadConfig();
  const statusIndicator = document.getElementById("statusIndicator");
  const statusText = document.getElementById("statusText");

  statusIndicator.className = "status-indicator";
  statusText.textContent = "Consultando XML...";

  // Construir la URL garantizando format=XML
  const cleanBase = config.baseUrl.replace(/\/+$/, '');
  let cleanEndpoint = config.endpoint.startsWith('/') ? config.endpoint : '/' + config.endpoint;
  
  const separator = cleanEndpoint.includes('?') ? '&' : '?';
  const finalUrl = `${cleanBase}${cleanEndpoint}${separator}format=XML`;

  console.log(`[HTTP GET XML] Solicitando catalogo en XML puro: ${finalUrl}`);

  try {
    const response = await fetch(finalUrl, {
      method: "GET",
      headers: {
        "Accept": "application/xml, text/xml, */*"
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }

    const xmlText = await response.text();
    latestRawXml = xmlText;

    // Procesar estrictamente con DOMParser (Exclusivamente XML)
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlText, "application/xml");

    const parserError = xmlDoc.querySelector("parsererror");
    if (parserError) {
      throw new Error(`Error en estructura XML recibida: ${parserError.textContent}`);
    }

    const parsedBooks = parseBooksFromXmlDoc(xmlDoc);
    allBooksFromXml = parsedBooks;
    filteredBooks = [...allBooksFromXml];
    currentPage = 1;

    statusIndicator.className = "status-indicator online";
    statusText.textContent = `Online: ${allBooksFromXml.length} libros (XML)`;

    renderCatalog();
    showToast(`Se cargaron ${allBooksFromXml.length} libros en formato XML.`, "success");

  } catch (error) {
    console.error("[ERROR CARGA XML]", error);
    statusIndicator.className = "status-indicator offline";
    statusText.textContent = "Error de Conexión";
    showToast(`Error al consultar microservicio: ${error.message}`, "error");

    document.getElementById("booksGrid").innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px;">
        <h3 style="color: #f87171; margin-bottom: 0.5rem;">⚠️ No se pudo cargar el catálogo XML</h3>
        <p style="color: #94a3b8; font-size: 0.9rem; max-width: 600px; margin: 0 auto 1.25rem;">
          Verifique que el microservicio esté corriendo en <code>${config.baseUrl}</code> y que el endpoint <code>${config.endpoint}</code> esté activo.
        </p>
        <button onclick="loadCatalogOnDemand()" class="btn btn-primary">Reintentar Carga</button>
      </div>
    `;
    document.getElementById("paginationInfo").textContent = "Sin datos disponibles";
    document.getElementById("pageNumbers").innerHTML = "";
  }
}

/**
 * Extrae los nodos del documento XML a objetos JavaScript
 */
function parseBooksFromXmlDoc(xmlDoc) {
  const bookNodes = xmlDoc.querySelectorAll("library > book, books > book, book");
  const books = [];

  bookNodes.forEach((bNode, index) => {
    const isbn = bNode.getAttribute("isbn") || bNode.querySelector("isbn")?.textContent?.trim() || `ISBN-DESCONOCIDO-${index}`;
    const title = bNode.querySelector("title")?.textContent?.trim() || "Título no disponible";
    
    // Autores
    const authorNodes = bNode.querySelectorAll("authors > author, author");
    let authors = [];
    authorNodes.forEach(a => {
      const name = a.textContent.trim();
      if (name) authors.push(name);
    });
    const authorsStr = authors.length > 0 ? authors.join(", ") : "Autor desconocido";

    // Año de publicación
    const year = bNode.querySelector("publication_year, year")?.textContent?.trim() || "N/A";

    // Precio y Moneda
    const priceNode = bNode.querySelector("price");
    const priceVal = priceNode ? parseFloat(priceNode.textContent.trim()) : 0.00;
    const currency = priceNode?.getAttribute("currency") || "USD";

    // Stock
    const stockVal = parseInt(bNode.querySelector("stock")?.textContent?.trim() || "0", 10);

    // Formato y Categoría
    const formatName = bNode.querySelector("format")?.textContent?.trim() || "Físico";
    const categoryName = bNode.querySelector("category")?.textContent?.trim() || "General";

    // Géneros
    const genreNodes = bNode.querySelectorAll("genres > genre, genre");
    let genres = [];
    genreNodes.forEach(g => {
      const gName = g.textContent.trim();
      if (gName) genres.push(gName);
    });
    if (genres.length === 0 && categoryName) {
      genres.push(categoryName);
    }

    // Portada (cover_image)
    let coverImage = bNode.querySelector("cover_image, image_url, image")?.textContent?.trim();
    if (!coverImage || coverImage.length < 5) {
      // Fallback temático elegante según categoría
      coverImage = "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400";
    }

    books.push({
      id: index + 1,
      isbn: isbn,
      title: title,
      authors: authorsStr,
      year: year,
      price: isNaN(priceVal) ? 0.00 : priceVal,
      currency: currency,
      stock: isNaN(stockVal) ? 0 : stockVal,
      format: formatName,
      category: categoryName,
      genres: genres,
      coverImage: coverImage
    });
  });

  return books;
}

/**
 * Renderiza las tarjetas de libros correspondientes a la página actual
 */
function renderCatalog() {
  const grid = document.getElementById("booksGrid");
  const totalItems = filteredBooks.length;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;

  if (currentPage > totalPages) currentPage = totalPages;
  if (currentPage < 1) currentPage = 1;

  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalItems);
  const currentBooksPage = filteredBooks.slice(startIndex, endIndex);

  if (currentBooksPage.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 4rem; color: #94a3b8;">
        <span style="font-size: 2.5rem; display: block; margin-bottom: 0.75rem;">🔍</span>
        <h3 style="color: #ffffff; margin-bottom: 0.25rem;">No se encontraron libros</h3>
        <p style="font-size: 0.85rem;">Intente con otro criterio de búsqueda en el filtro superior.</p>
      </div>
    `;
  } else {
    grid.innerHTML = currentBooksPage.map(book => {
      // Determinación de Badge de Stock
      let stockClass = "stock-in";
      let stockLabel = `En Stock (${book.stock})`;
      if (book.stock === 0) {
        stockClass = "stock-out";
        stockLabel = "Agotado (0)";
      } else if (book.stock <= 5) {
        stockClass = "stock-low";
        stockLabel = `Bajo Stock (${book.stock})`;
      }

      return `
        <article class="book-card">
          <div class="card-media">
            <img class="card-img" 
                 src="${book.coverImage}" 
                 alt="${book.title}" 
                 loading="lazy"
                 onerror="this.src='https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400';">
            <span class="card-stock-badge ${stockClass}">${stockLabel}</span>
            <span class="card-format-tag">${book.format}</span>
          </div>

          <div class="card-body">
            <h3 class="card-title" title="${book.title}">${book.title}</h3>
            <p class="card-authors" title="${book.authors}">✍️ ${book.authors}</p>

            <div class="card-details-grid">
              <div class="detail-item">
                <span class="detail-label">Año</span>
                <span class="detail-val">${book.year}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Categoría</span>
                <span class="detail-val" title="${book.category}">${book.category}</span>
              </div>
            </div>

            <div class="card-genres">
              ${book.genres.slice(0, 2).map(g => `<span class="genre-pill">${g}</span>`).join('')}
            </div>

            <div class="card-footer">
              <div>
                <span class="card-price">$${book.price.toFixed(2)}</span>
                <span class="card-price-currency">${book.currency}</span>
              </div>
              <span class="isbn-tag" title="Código ISBN">${book.isbn}</span>
            </div>
          </div>
        </article>
      `;
    }).join('');
  }

  // Actualizar Controles de Paginación
  updatePaginationUI(startIndex, endIndex, totalItems, totalPages);
}

/**
 * Actualiza la barra inferior de paginación
 */
function updatePaginationUI(startIndex, endIndex, totalItems, totalPages) {
  const info = document.getElementById("paginationInfo");
  const btnPrev = document.getElementById("btnPrevPage");
  const btnNext = document.getElementById("btnNextPage");
  const pageNumbers = document.getElementById("pageNumbers");

  if (totalItems === 0) {
    info.textContent = "Mostrando 0 de 0 libros";
    btnPrev.disabled = true;
    btnNext.disabled = true;
    pageNumbers.innerHTML = "";
    return;
  }

  info.innerHTML = `Mostrando libros <strong>${startIndex + 1} - ${endIndex}</strong> de un total de <strong>${totalItems}</strong>`;

  btnPrev.disabled = currentPage <= 1;
  btnNext.disabled = currentPage >= totalPages;

  let pagesHtml = "";
  for (let i = 1; i <= totalPages; i++) {
    pagesHtml += `
      <button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">
        ${i}
      </button>
    `;
  }
  pageNumbers.innerHTML = pagesHtml;
}

function goToPage(page) {
  currentPage = page;
  renderCatalog();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function filterBooks() {
  const term = document.getElementById("searchInput").value.toLowerCase().trim();
  if (!term) {
    filteredBooks = [...allBooksFromXml];
  } else {
    filteredBooks = allBooksFromXml.filter(b => 
      b.title.toLowerCase().includes(term) ||
      b.authors.toLowerCase().includes(term) ||
      b.isbn.toLowerCase().includes(term) ||
      b.category.toLowerCase().includes(term) ||
      b.genres.some(g => g.toLowerCase().includes(term))
    );
  }
  currentPage = 1;
  renderCatalog();
}

function showToast(message, type = "info") {
  const toast = document.getElementById("toastNotification");
  toast.textContent = message;
  toast.className = `toast-box toast-${type} show`;
  setTimeout(() => {
    toast.className = "toast-box";
  }, 3500);
}

// Listeners
document.addEventListener("DOMContentLoaded", () => {
  loadConfig();

  document.getElementById("btnSaveConfig").addEventListener("click", saveConfig);
  document.getElementById("btnResetConfig").addEventListener("click", resetConfig);
  document.getElementById("btnReload").addEventListener("click", loadCatalogOnDemand);

  document.getElementById("btnPrevPage").addEventListener("click", () => {
    if (currentPage > 1) goToPage(currentPage - 1);
  });

  document.getElementById("btnNextPage").addEventListener("click", () => {
    const totalPages = Math.ceil(filteredBooks.length / pageSize);
    if (currentPage < totalPages) goToPage(currentPage + 1);
  });

  document.getElementById("selectPageSize").addEventListener("change", (e) => {
    pageSize = parseInt(e.target.value, 10);
    currentPage = 1;
    renderCatalog();
  });

  document.getElementById("searchInput").addEventListener("input", filterBooks);

  // Modal de Inspección XML
  const modal = document.getElementById("xmlModal");
  document.getElementById("btnViewXml").addEventListener("click", () => {
    document.getElementById("xmlRawContent").textContent = latestRawXml || "<!-- No se ha recibido XML aun -->";
    modal.style.display = "flex";
  });

  document.getElementById("btnCloseModal").addEventListener("click", () => {
    modal.style.display = "none";
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });

  // Carga inicial
  setTimeout(loadCatalogOnDemand, 400);
});

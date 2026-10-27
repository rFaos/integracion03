/**
 * ==============================================================================
 * ARCHIVO: discover.js - FASE 2: "Tu perfil lector" (IA generativa sin chat)
 *
 * El usuario NUNCA le pregunta nada a la IA. La app observa señales implícitas
 * mientras navega el catálogo:
 *   - ♥ favoritos            (peso alto)
 *   - tiempo mirando un libro (hover > 1.2 s)
 *   - términos que busca
 * Con eso se calcula un perfil en código (determinista, siempre funciona) y,
 * en segundo plano, qwen2.5:7b (Ollama local) lo convierte en una vista nueva
 * generada: arquetipo de lector, descripción, tema visual y 3 libros con la
 * razón de cada recomendación. Si la IA no responde, se muestra la versión
 * calculada en código.
 *
 * Depende de: allBooksFromXml (renderer.js), normalizeText / bookSearchText /
 * OLLAMA_URL / OLLAMA_MODEL (chat.js).
 * ==============================================================================
 */
(() => {
  const STORE_KEY = "discover.v1";
  const CACHE_KEY = "discover.cache.v1";
  const THRESHOLD = 4;          // señal mínima para ofrecer el perfil
  const DWELL_MIN_MS = 1200;    // mirar una tarjeta menos tiempo no cuenta
  const LLM_TIMEOUT_MS = 90000;
  const THEMES = ["cian", "purpura", "ambar", "verde", "rosa"];

  // Arquetipos base (fallback sin IA), según la categoría dominante.
  const ARCHETYPES = {
    "arquitectura de software": { titulo: "El Arquitecto", emoji: "🏛️", tema: "purpura",
      desc: "Te gusta que los sistemas estén bien pensados antes de escribir una línea. Valoras la claridad, los patrones y el código que envejece con dignidad." },
    "sistemas distribuidos": { titulo: "El Domador de Sistemas Distribuidos", emoji: "🕸️", tema: "cian",
      desc: "Te atraen los problemas donde todo puede fallar a la vez. Disfrutas entender cómo escalan, replican y sobreviven los datos." },
    "cloud computing": { titulo: "El Navegante de la Nube", emoji: "☁️", tema: "cian",
      desc: "Piensas en contenedores, clusters y despliegues. Para ti la infraestructura es algo que se programa." },
    "devops y sre": { titulo: "El Guardián del Pipeline", emoji: "🚀", tema: "ambar",
      desc: "Te importa que el software llegue a producción sin drama. Mezclas cultura, automatización y buen humor." },
    "redes y comunicaciones": { titulo: "El Explorador de Redes", emoji: "📡", tema: "verde",
      desc: "Te gusta ir a lo fundamental: cómo viajan los datos y cómo funciona por dentro una computadora." }
  };
  const DEFAULT_ARCHETYPE = { titulo: "El Lector Curioso", emoji: "📚", tema: "rosa",
    desc: "Exploras de todo un poco y vas descubriendo qué te engancha. Buen punto de partida." };

  let state = loadState();
  let current = null;       // último perfil calculado {books, picks, ...}
  let recIsbns = new Set(); // libros con la etiqueta "Para ti"
  let hoverCard = null, hoverStart = 0;
  let searchTimer = null;
  let llmRun = 0;           // evita que una respuesta vieja pise una más nueva
  let failedSig = "";      // si la IA falló para este perfil, no reintentar en bucle
  let inflight = null;      // {sig, promise}: generación en curso (compartida con el prefetch)

  /* ----------------------------- persistencia ----------------------------- */
  function loadState() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
      return { fav: raw.fav || [], dwell: raw.dwell || {}, searches: raw.searches || [], dismissedSig: raw.dismissedSig || "" };
    } catch { return { fav: [], dwell: {}, searches: [], dismissedSig: "" }; }
  }
  function saveState() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch { /* localStorage no disponible */ }
  }
  function readCache() {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "{}"); } catch { return {}; }
  }
  function writeCache(sig, value) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ sig, value })); } catch { /* ignorar */ }
  }

  const books = () => (typeof allBooksFromXml !== "undefined" ? allBooksFromXml : []);
  const byIsbn = isbn => books().find(b => b.isbn === isbn);
  const norm = t => (typeof normalizeText === "function" ? normalizeText(t) : String(t || "").toLowerCase());

  /* ------------------------------ perfil (código) ------------------------ */
  function bookWeights() {
    const w = {};
    const list = books();
    list.forEach(b => {
      w[b.isbn] = (state.fav.includes(b.isbn) ? 3 : 0) + Math.min((state.dwell[b.isbn] || 0) / 4, 2);
    });
    // Búsquedas: suman a los libros que coinciden (si el término es demasiado genérico se ignora).
    state.searches.forEach(term => {
      const hits = list.filter(b => bookSearchText(b).includes(term));
      if (hits.length === 0 || hits.length > list.length / 2) return;
      hits.forEach(b => { w[b.isbn] += 0.5; });
    });
    return w;
  }

  function computeProfile() {
    const list = books();
    const w = bookWeights();
    const cat = {}, gen = {}, aut = {};
    let signal = 0;
    list.forEach(b => {
      const x = w[b.isbn];
      if (!x) return;
      signal += x;
      cat[b.category] = (cat[b.category] || 0) + x;
      (b.genres || []).forEach(g => { gen[g] = (gen[g] || 0) + x; });
      aut[b.authors] = (aut[b.authors] || 0) + x;
    });

    const favs = list.filter(b => state.fav.includes(b.isbn));
    const topCats = Object.entries(cat).sort((a, b) => b[1] - a[1]);

    // Recomendaciones: afinidad por categoría/género/autor con lo que ya le interesó.
    const scored = list
      .filter(b => !state.fav.includes(b.isbn))
      .map(b => {
        let s = (cat[b.category] || 0) + 0.6 * (b.genres || []).reduce((n, g) => n + (gen[g] || 0), 0) / Math.max((b.genres || []).length, 1) + 0.8 * (aut[b.authors] || 0);
        s -= (w[b.isbn] || 0) * 0.5;             // no insistir en lo ya visto
        s += b.stock > 0 ? 0.3 : -2;             // preferir lo disponible
        return { book: b, score: s };
      })
      .sort((a, b) => b.score - a.score);

    const picks = scored.slice(0, 3).map(({ book }) => ({ book, razon: fallbackReason(book, favs, cat) }));
    const sig = [...state.fav].sort().join(",") + "|" + topCats.slice(0, 3).map(c => c[0]).join(",");
    return { signal, topCats, favs, picks, sig, total: Object.values(cat).reduce((a, b) => a + b, 0) };
  }

  function fallbackReason(book, favs, cat) {
    const sameCat = favs.find(f => f.category === book.category);
    if (sameCat) return `Comparte categoría (${book.category}) con «${sameCat.title}», que marcaste.`;
    const sameAuthor = favs.find(f => f.authors === book.authors);
    if (sameAuthor) return `Del mismo autor que «${sameAuthor.title}».`;
    const sameGenre = favs.find(f => (f.genres || []).some(g => (book.genres || []).includes(g)));
    if (sameGenre) return `Mismo enfoque (${(book.genres || [])[0]}) que «${sameGenre.title}».`;
    return book.category ? `Va con tus intereses en ${book.category}.` : "Encaja con lo que has estado explorando.";
  }

  function archetypeFor(profile) {
    const top = profile.topCats[0];
    return (top && ARCHETYPES[norm(top[0])]) || DEFAULT_ARCHETYPE;
  }

  /* ------------------------------ IA generativa --------------------------- */
  function buildPrompt(profile) {
    const interests = profile.topCats.slice(0, 4).map(([c, v]) => `${c} (${v.toFixed(1)})`).join(", ");
    const favs = profile.favs.map(f => `"${f.title}"`).join(", ") || "(ninguno todavía; solo exploró)";
    const cand = profile.picks.map(p => `- ${p.book.isbn} | "${p.book.title}" | ${p.book.authors} | ${p.book.category}`).join("\n");
    return [
      "Eres un generador de perfiles lectores para una librería técnica. Respondes SOLO con un objeto JSON válido, sin texto extra.",
      "",
      `Libros favoritos del usuario: ${favs}`,
      `Intereses detectados (categoría y peso): ${interests}`,
      "Libros candidatos a recomendar (usa EXACTAMENTE estos ISBN):",
      cand,
      "",
      "Devuelve este JSON:",
      `{"perfil_titulo": "máx 5 palabras, creativo, ej: La Arquitecta de Sistemas",`,
      ` "descripcion": "2 frases en segunda persona (tú), cálidas y con un poco de humor, basadas en sus intereses",`,
      ` "emoji": "un solo emoji",`,
      ` "tema": "uno de: ${THEMES.join(", ")}",`,
      ` "picks": [{"isbn": "...", "razon": "máx 15 palabras, específica, menciona un favorito si aplica"}],`,
      ` "reto": "un mini reto de lectura de una frase"}`,
      "Un pick por cada candidato. No inventes libros ni ISBN."
    ].join("\n");
  }

  async function generateWithLLM(profile) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), LLM_TIMEOUT_MS);
    try {
      const res = await fetch(`${OLLAMA_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          model: OLLAMA_MODEL,
          stream: false,
          format: "json",
          keep_alive: "30m",
          messages: [{ role: "user", content: buildPrompt(profile) }],
          options: { temperature: 0.7, num_ctx: 4096, num_predict: 450 }
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return validateLLM(JSON.parse(data.message?.content || "{}"), profile);
    } finally {
      clearTimeout(timer);
    }
  }

  // Nunca se confía en la salida del modelo: se valida y se limpia.
  function validateLLM(raw, profile) {
    const clean = (t, max) => String(t || "").replace(/[<>]/g, "").trim().slice(0, max);
    const out = {
      titulo: clean(raw.perfil_titulo, 60),
      desc: clean(raw.descripcion, 320),
      emoji: Array.from(clean(raw.emoji, 8))[0] || "",
      tema: THEMES.includes(raw.tema) ? raw.tema : "",
      reto: clean(raw.reto, 160),
      razones: {}
    };
    (Array.isArray(raw.picks) ? raw.picks : []).forEach(p => {
      const isbn = String(p?.isbn || "").trim();
      if (profile.picks.some(x => x.book.isbn === isbn) && p.razon) out.razones[isbn] = clean(p.razon, 140);
    });
    if (!out.titulo || !out.desc) throw new Error("JSON incompleto");
    return out;
  }

  /* -------------------------------- vista --------------------------------- */
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function renderSheet(profile, ai, aiState) {
    const sheet = document.getElementById("discoverSheet");
    const base = archetypeFor(profile);
    const view = {
      titulo: ai?.titulo || base.titulo,
      desc: ai?.desc || base.desc,
      emoji: ai?.emoji || base.emoji,
      tema: ai?.tema || base.tema
    };
    sheet.dataset.theme = view.tema;
    sheet.textContent = "";

    const close = el("button", "discover-close", "×");
    close.type = "button";
    close.addEventListener("click", closeModal);
    sheet.appendChild(close);

    // Cabecera
    const hero = el("header", "discover-hero");
    hero.appendChild(el("div", "discover-emoji", view.emoji));
    const heroText = el("div");
    heroText.appendChild(el("p", "discover-eyebrow", "Tu perfil lector"));
    heroText.appendChild(el("h2", "discover-title", view.titulo));
    heroText.appendChild(el("p", "discover-desc", view.desc));
    hero.appendChild(heroText);
    sheet.appendChild(hero);

    const status = el("p", "discover-status");
    if (aiState === "loading") { status.textContent = "✨ La IA local está afinando tu perfil…"; status.classList.add("shimmer"); }
    else if (aiState === "ai") status.textContent = `Generado en tu equipo con ${OLLAMA_MODEL} · sin enviar datos a la nube`;
    else status.textContent = "Perfil calculado en la app (la IA local no respondió).";
    sheet.appendChild(status);

    // Intereses
    if (profile.topCats.length) {
      const sec = el("section", "discover-section");
      sec.appendChild(el("h3", "", "Lo que más te atrae"));
      const max = profile.topCats[0][1] || 1;
      profile.topCats.slice(0, 4).forEach(([name, val]) => {
        const row = el("div", "interest-row");
        row.appendChild(el("span", "interest-name", name));
        const bar = el("div", "interest-bar");
        const fill = el("div", "interest-fill");
        fill.style.width = `${Math.max(8, Math.round((val / max) * 100))}%`;
        bar.appendChild(fill);
        row.appendChild(bar);
        sec.appendChild(row);
      });
      sheet.appendChild(sec);
    }

    // Recomendaciones
    const recSec = el("section", "discover-section");
    recSec.appendChild(el("h3", "", "Elegidos para ti"));
    const grid = el("div", "discover-picks");
    profile.picks.forEach(({ book, razon }) => {
      const card = el("article", "pick-card");
      const img = el("img", "pick-cover");
      img.src = book.coverImage;
      img.alt = book.title;
      img.addEventListener("error", () => { img.style.visibility = "hidden"; });
      card.appendChild(img);
      const body = el("div", "pick-body");
      body.appendChild(el("h4", "", book.title));
      body.appendChild(el("p", "pick-author", book.authors));
      body.appendChild(el("p", "pick-reason", `“${ai?.razones?.[book.isbn] || razon}”`));
      const foot = el("div", "pick-foot");
      foot.appendChild(el("span", "pick-price", `$${Number(book.price).toFixed(2)} ${book.currency}`));
      const go = el("button", "btn btn-secondary btn-sm", "Ver en catálogo");
      go.type = "button";
      go.addEventListener("click", () => showInCatalog(book));
      foot.appendChild(go);
      body.appendChild(foot);
      card.appendChild(body);
      grid.appendChild(card);
    });
    recSec.appendChild(grid);
    sheet.appendChild(recSec);

    if (ai?.reto) {
      const reto = el("section", "discover-reto");
      reto.appendChild(el("strong", "", "🎯 Tu reto: "));
      reto.appendChild(document.createTextNode(ai.reto));
      sheet.appendChild(reto);
    }

    const reset = el("button", "discover-reset", "Reiniciar mi perfil");
    reset.type = "button";
    reset.addEventListener("click", () => {
      state = { fav: [], dwell: {}, searches: [], dismissedSig: "" };
      saveState();
      closeModal();
      refresh();
      if (typeof showToast === "function") showToast("Perfil reiniciado.", "info");
    });
    sheet.appendChild(reset);
  }

  function renderNotReady(profile) {
    const sheet = document.getElementById("discoverSheet");
    sheet.dataset.theme = "cian";
    sheet.textContent = "";
    const close = el("button", "discover-close", "×");
    close.type = "button";
    close.addEventListener("click", closeModal);
    sheet.appendChild(close);
    const box = el("div", "discover-empty");
    box.appendChild(el("div", "discover-emoji", "🧭"));
    box.appendChild(el("h2", "discover-title", "Aún te estoy conociendo"));
    box.appendChild(el("p", "discover-desc",
      "Explora el catálogo con calma: marca con ♥ los libros que te interesen o quédate un momento mirando los que te llamen la atención. Con eso armo tu perfil sin que tengas que preguntarme nada."));
    const bar = el("div", "interest-bar");
    const fill = el("div", "interest-fill");
    fill.style.width = `${Math.min(100, Math.round((profile.signal / THRESHOLD) * 100))}%`;
    bar.appendChild(fill);
    box.appendChild(bar);
    box.appendChild(el("p", "discover-status", `Progreso: ${Math.min(100, Math.round((profile.signal / THRESHOLD) * 100))}%`));
    sheet.appendChild(box);
  }

  function openModal() {
    if (books().length === 0) {
      if (typeof showToast === "function") showToast("Primero carga el catálogo (🔄 Recargar).", "info");
      return;
    }
    const profile = computeProfile();
    current = profile;
    const modal = document.getElementById("discoverModal");
    modal.hidden = false;
    state.dismissedSig = profile.sig;
    saveState();
    document.getElementById("discoverPill").hidden = true;

    if (profile.signal < THRESHOLD) { renderNotReady(profile); return; }

    const cached = readCache();
    if (cached.sig === profile.sig && cached.value) {
      renderSheet(profile, cached.value, "ai");
      return;
    }
    renderSheet(profile, null, "loading");
    const run = ++llmRun;
    ensureGenerated(profile)
      .then(ai => { if (run === llmRun && !modal.hidden) renderSheet(profile, ai, "ai"); })
      .catch(() => { if (run === llmRun && !modal.hidden) renderSheet(profile, null, "fallback"); });
  }

  // Una sola generación por perfil: la reutilizan el prefetch y la apertura de la vista.
  function ensureGenerated(profile) {
    if (inflight && inflight.sig === profile.sig) return inflight.promise;
    const promise = generateWithLLM(profile)
      .then(ai => { writeCache(profile.sig, ai); return ai; })
      .catch(err => {
        console.warn("[Fase 2] IA no disponible, se usa el perfil calculado:", err);
        failedSig = profile.sig;
        throw err;
      })
      .finally(() => { if (inflight && inflight.promise === promise) inflight = null; });
    inflight = { sig: profile.sig, promise };
    return promise;
  }

  // Cuando el perfil se vuelve "listo", la IA lo prepara en segundo plano.
  function prefetch(profile) {
    const cached = readCache();
    if (cached.sig === profile.sig || failedSig === profile.sig) return;
    ensureGenerated(profile).catch(() => { /* se reintentará al abrir la vista */ });
  }

  function closeModal() {
    llmRun++;
    document.getElementById("discoverModal").hidden = true;
  }

  function showInCatalog(book) {
    closeModal();
    const input = document.getElementById("searchInput");
    input.value = book.title;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* --------------------- observación pasiva en el catálogo ---------------- */
  function decorateCards() {
    document.querySelectorAll(".book-card[data-isbn]").forEach(card => {
      const isbn = card.dataset.isbn;
      const media = card.querySelector(".card-media");
      if (!media) return;
      let fav = media.querySelector(".fav-btn");
      if (!fav) {
        fav = el("button", "fav-btn", "♥");
        fav.type = "button";
        fav.dataset.isbn = isbn;
        media.appendChild(fav);
      }
      const isFav = state.fav.includes(isbn);
      fav.classList.toggle("active", isFav);
      fav.title = isFav ? "Quitar de favoritos" : "Me interesa";

      let tag = media.querySelector(".for-you-tag");
      const show = recIsbns.has(isbn) && !isFav;
      if (show && !tag) media.appendChild(el("span", "for-you-tag", "✨ Para ti"));
      if (!show && tag) tag.remove();
    });
  }

  function flushDwell(now) {
    if (!hoverCard) return;
    const ms = now - hoverStart;
    if (ms >= DWELL_MIN_MS) {
      const isbn = hoverCard.dataset.isbn;
      state.dwell[isbn] = Math.min((state.dwell[isbn] || 0) + ms / 1000, 30);
      saveState();
      refresh();
    }
    hoverCard = null;
  }

  function onGridOver(e) {
    const card = e.target.closest?.(".book-card[data-isbn]");
    if (card === hoverCard) return;
    flushDwell(performance.now());
    hoverCard = card || null;
    hoverStart = performance.now();
  }

  function onGridClick(e) {
    const btn = e.target.closest?.(".fav-btn");
    if (!btn) return;
    const isbn = btn.dataset.isbn;
    const i = state.fav.indexOf(isbn);
    if (i >= 0) state.fav.splice(i, 1); else state.fav.push(isbn);
    saveState();
    refresh();
    if (i < 0 && typeof showToast === "function") showToast("♥ Anotado. La IA está aprendiendo tus gustos.", "success");
  }

  function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      const term = norm(document.getElementById("searchInput").value);
      if (term.length < 3 || state.searches.includes(term)) return;
      state.searches.push(term);
      state.searches = state.searches.slice(-20);
      saveState();
      refresh();
    }, 1500);
  }

  // Recalcula el estado visible: botón, pill, etiquetas "Para ti".
  function refresh() {
    if (books().length === 0) return;
    const profile = computeProfile();
    current = profile;
    recIsbns = new Set(profile.signal >= THRESHOLD ? profile.picks.map(p => p.book.isbn) : []);

    const btn = document.getElementById("btnDiscover");
    const ready = profile.signal >= THRESHOLD;
    btn.classList.toggle("ready", ready);
    btn.textContent = ready ? "✨ Para ti" : `✨ Para ti · ${Math.min(100, Math.round((profile.signal / THRESHOLD) * 100))}%`;

    const pill = document.getElementById("discoverPill");
    const modalOpen = !document.getElementById("discoverModal").hidden;
    pill.hidden = !(ready && !modalOpen && state.dismissedSig !== profile.sig);

    decorateCards();
    if (ready) prefetch(profile);
  }

  function init() {
    const grid = document.getElementById("booksGrid");
    grid.addEventListener("mouseover", onGridOver);
    grid.addEventListener("mouseleave", () => { flushDwell(performance.now()); });
    grid.addEventListener("click", onGridClick);
    // El catálogo se vuelve a pintar en cada página/búsqueda/recarga.
    new MutationObserver(() => refresh()).observe(grid, { childList: true });

    document.getElementById("searchInput").addEventListener("input", onSearchInput);
    document.getElementById("btnDiscover").addEventListener("click", openModal);
    document.getElementById("discoverPill").addEventListener("click", openModal);
    document.getElementById("discoverModal").addEventListener("click", e => {
      if (e.target.id === "discoverModal") closeModal();
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
    refresh();
  }

  document.addEventListener("DOMContentLoaded", init);
})();

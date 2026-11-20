# ==============================================================================
# locustfile.py - Prueba de estres del microservicio de libros (apps/services/soap)
# ==============================================================================
# PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
# UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
#
# Escenario: 20 usuarios simultaneos contra http://34.51.2.102:5001
# (los valores por defecto viven en locust.conf, junto a este archivo).
#
# Se reparten en dos perfiles, como en el negocio real:
#
#   * LectorCatalogo (15 usuarios) - clientes que navegan el catalogo.
#     Solo usan GET, que es publico: /books en JSON y XML, detalle, busqueda,
#     temas, autores, catalogos, salud, WSDL y los alias /api/...
#
#   * EditorCatalogo (5 usuarios) - personal que administra el catalogo.
#     Usan las operaciones protegidas con JWT: POST/PUT/PATCH/DELETE de libros
#     (y sus alias /api/book/...) y las operaciones SOAP por POST /soap.
#
# El token JWT se obtiene UNA sola vez al iniciar la prueba (servicio login,
# puerto 5000) y lo comparten todos los editores. Si cada usuario hiciera su
# propio login, el limitador del login (20 peticiones/minuto por IP) cortaria
# la prueba antes de empezar.
#
# Variables de entorno opcionales:
#   LOGIN_URL        URL del servicio login (por defecto: mismo host, puerto 5000)
#   LOCUST_EMAIL     usuario para el login   (por defecto: usuario1@library.local)
#   LOCUST_PASSWORD  contrasena del usuario  (por defecto: la del usuario sembrado)
# ==============================================================================

import os
import random
import re
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

import requests
from gevent.lock import Semaphore
from locust import HttpUser, between, events, task

LOGIN_EMAIL = os.getenv("LOCUST_EMAIL", "usuario1@library.local")
LOGIN_PASSWORD = os.getenv("LOCUST_PASSWORD", "666")
TOKEN_MAX_AGE = 10 * 60   # el access token dura 15-20 min; se renueva antes
LOGIN_RETRY_AFTER = 30    # si el login falla, no reintentar hasta pasado este tiempo

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

# ------------------------------------------------------------------------------
# Datos compartidos por todos los usuarios virtuales
# ------------------------------------------------------------------------------
# Se llenan en test_start con datos REALES del servicio, para que las pruebas
# pidan ISBN y autores que existen (un 404 no mide el rendimiento real).
shared = {
    "host": None,
    "token": None,
    "token_at": 0.0,
    "token_failed_at": 0.0,
    "isbns": [],
    "author_ids": [],
    "format_ids": [],
    "category_ids": [],
    "genre_ids": [],
}
_token_lock = Semaphore()


def login_url_for(host):
    """Por defecto el login esta en el mismo host que libros, pero en el 5000."""
    explicit = os.getenv("LOGIN_URL")
    if explicit:
        return explicit.rstrip("/")
    parts = urlsplit(host)
    return urlunsplit((parts.scheme, "%s:5000" % parts.hostname, "", "", ""))


def solve_captcha(question):
    """El CAPTCHA del login es aritmetico: '¿Cuánto es 7 - 3?'."""
    m = re.search(r"(\d+)\s*([+-])\s*(\d+)", question)
    if not m:
        raise ValueError("CAPTCHA no reconocido: %r" % question)
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    return a + b if op == "+" else a - b


def fetch_token(host):
    """Login completo: GET /captcha -> resolver -> POST /login -> access_token."""
    base = login_url_for(host)
    cap = requests.get(base + "/captcha", params={"format": "json"}, timeout=10).json()["data"]
    body = {
        "email": LOGIN_EMAIL,
        "password": LOGIN_PASSWORD,
        "captcha_id": cap["captcha_id"],
        "captcha_answer": solve_captcha(cap["question"]),
    }
    resp = requests.post(base + "/login", params={"format": "json"}, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()["data"]["session"]["access_token"]


def current_token():
    """Token compartido; se renueva una sola vez aunque lo pidan 5 usuarios a la vez."""
    with _token_lock:
        now = time.time()
        if shared["token"] and now - shared["token_at"] < TOKEN_MAX_AGE:
            return shared["token"]
        # Sin esta espera, un login caido se reintentaria en CADA peticion de
        # los editores y el limitador del login respondería 429 a todo.
        if now - shared["token_failed_at"] < LOGIN_RETRY_AFTER:
            return None
        try:
            shared["token"] = fetch_token(shared["host"])
            shared["token_at"] = now
        except Exception as exc:
            print("[locust] No se pudo obtener el JWT: %s" % exc)
            shared["token"] = None
            shared["token_failed_at"] = now
        return shared["token"]


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    """Se ejecuta al pulsar START en la GUI: carga datos reales y hace login."""
    host = (environment.host or "").rstrip("/")
    shared["host"] = host

    try:
        books = requests.get(host + "/books", params={"format": "json"}, timeout=15).json()
        shared["isbns"] = [b["isbn"] for b in books.get("books", []) if b.get("isbn")]
        cats = requests.get(host + "/catalogs", timeout=15).json()
        shared["author_ids"] = [a["id"] for a in cats.get("authors", [])]
        shared["format_ids"] = [f["id"] for f in cats.get("formats", [])]
        shared["category_ids"] = [c["id"] for c in cats.get("categories", [])]
        shared["genre_ids"] = [g["id"] for g in cats.get("genres", [])]
    except Exception as exc:
        print("[locust] No se pudieron cargar los datos iniciales de %s: %s" % (host, exc))

    shared["token"] = None
    shared["token_failed_at"] = 0.0
    token = current_token()
    print("[locust] %d libros, %d autores. JWT: %s" % (
        len(shared["isbns"]), len(shared["author_ids"]), "OK" if token else "NO DISPONIBLE"))


def any_isbn():
    return random.choice(shared["isbns"]) if shared["isbns"] else "978-0131103627"


def any_author():
    return random.choice(shared["author_ids"]) if shared["author_ids"] else 1


def expect(resp, *codes, content=None):
    """Marca la peticion como fallo si el codigo o el tipo de contenido no cuadran."""
    if resp.status_code not in codes:
        resp.failure("HTTP %s (esperado %s): %s" % (resp.status_code, codes, resp.text[:150]))
    elif content and content not in (resp.headers.get("Content-Type") or ""):
        resp.failure("Content-Type %r (esperado %s)" % (resp.headers.get("Content-Type"), content))
    else:
        resp.success()


# ==============================================================================
# PERFIL 1: clientes que navegan el catalogo (solo lectura, publico)
# ==============================================================================
class LectorCatalogo(HttpUser):
    weight = 3
    wait_time = between(1, 3)

    # --- Los tres endpoints que pide el enunciado (los de mayor peso) --------
    @task(5)
    def books_default(self):
        with self.client.get("/books", name="/books", catch_response=True) as r:
            expect(r, 200, content="json")

    @task(5)
    def books_json(self):
        with self.client.get("/books?format=json", name="/books?format=json", catch_response=True) as r:
            expect(r, 200, content="json")

    @task(5)
    def books_xml(self):
        with self.client.get("/books?format=xml", name="/books?format=xml", catch_response=True) as r:
            expect(r, 200, content="xml")

    # --- Resto de lecturas del microservicio ----------------------------------
    @task(1)
    def root(self):
        with self.client.get("/", name="/", catch_response=True) as r:
            expect(r, 200)

    @task(1)
    def health(self):
        with self.client.get("/health", name="/health", catch_response=True) as r:
            expect(r, 200)

    @task(1)
    def catalogs(self):
        with self.client.get("/catalogs", name="/catalogs", catch_response=True) as r:
            expect(r, 200, content="json")

    @task(1)
    def books_filter_isbn(self):
        with self.client.get("/books?isbn=%s" % any_isbn(), name="/books?isbn=[isbn]",
                             catch_response=True) as r:
            expect(r, 200)

    @task(3)
    def book_detail_json(self):
        with self.client.get("/books/%s" % any_isbn(), name="/books/[isbn]", catch_response=True) as r:
            expect(r, 200, content="json")

    @task(2)
    def book_detail_xml(self):
        with self.client.get("/books/%s?format=xml" % any_isbn(), name="/books/[isbn]?format=xml",
                             catch_response=True) as r:
            expect(r, 200, content="xml")

    @task(2)
    def books_by_author(self):
        with self.client.get("/books/author/%s" % any_author(), name="/books/author/[id]",
                             catch_response=True) as r:
            expect(r, 200, 404)   # 404 = autor sin libros, es una respuesta valida

    @task(1)
    def book_topics(self):
        with self.client.get("/books/%s/temas" % any_isbn(), name="/books/[isbn]/temas",
                             catch_response=True) as r:
            expect(r, 200, 404)

    @task(1)
    def book_topics_en(self):
        with self.client.get("/books/%s/topics?format=xml" % any_isbn(),
                             name="/books/[isbn]/topics?format=xml", catch_response=True) as r:
            expect(r, 200, 404)

    @task(1)
    def all_topics(self):
        with self.client.get("/books/temas", name="/books/temas", catch_response=True) as r:
            expect(r, 200)

    @task(1)
    def all_topics_en(self):
        with self.client.get("/books/topics?format=xml", name="/books/topics?format=xml",
                             catch_response=True) as r:
            expect(r, 200)

    @task(3)
    def search(self):
        params = random.choice([
            "q=a", "q=python", "min_price=100&max_price=600", "year=2020",
            "genre=Ficcion", "author=a&format=xml",
        ])
        with self.client.get("/books/search?%s" % params, name="/books/search?[filtros]",
                             catch_response=True) as r:
            expect(r, 200, 404)

    @task(1)
    def wsdl(self):
        with self.client.get("/wsdl", name="/wsdl", catch_response=True) as r:
            expect(r, 200, content="xml")

    @task(1)
    def soap_wsdl(self):
        with self.client.get("/soap?wsdl", name="/soap?wsdl", catch_response=True) as r:
            expect(r, 200, content="xml")

    # --- Alias heredados /api/... (mismo codigo, otra ruta) -------------------
    @task(1)
    def api_books(self):
        with self.client.get("/api/books", name="/api/books", catch_response=True) as r:
            expect(r, 200)

    @task(1)
    def api_book(self):
        with self.client.get("/api/book/%s" % any_isbn(), name="/api/book/[isbn]",
                             catch_response=True) as r:
            expect(r, 200)

    @task(1)
    def api_book_author(self):
        with self.client.get("/api/book/author/%s" % any_author(), name="/api/book/author/[id]",
                             catch_response=True) as r:
            expect(r, 200, 404)

    @task(1)
    def api_catalogs(self):
        with self.client.get("/api/catalogs", name="/api/catalogs", catch_response=True) as r:
            expect(r, 200)


# ==============================================================================
# PERFIL 2: personal que administra el catalogo (escrituras con JWT + SOAP)
# ==============================================================================
def soap_envelope(operation, **fields):
    inner = "".join("<%s>%s</%s>" % (k, v, k) for k, v in fields.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="%s"><soap:Body>'
        "<%s>%s</%s>"
        "</soap:Body></soap:Envelope>" % (SOAP_NS, operation, inner, operation)
    )


class EditorCatalogo(HttpUser):
    weight = 1
    wait_time = between(2, 5)

    def auth_headers(self, extra=None):
        token = current_token()
        headers = {"Authorization": "Bearer %s" % token} if token else {}
        headers.update(extra or {})
        return headers

    def new_book(self):
        """Libro desechable con ISBN unico: cada usuario crea y borra el suyo."""
        isbn = "LC-%s" % uuid.uuid4().hex[:14]   # books.isbn es VARCHAR(20)
        return {
            "isbn": isbn,
            "title": "Libro de prueba Locust %s" % isbn[-6:],
            "publication_year": random.randint(1990, 2026),
            "price": round(random.uniform(99, 899), 2),
            "stock": random.randint(1, 50),
            "format_id": random.choice(shared["format_ids"] or [1]),
            "category_id": random.choice(shared["category_ids"] or [1]),
            "author_ids": random.sample(shared["author_ids"], 1) if shared["author_ids"] else [],
            "genre_ids": random.sample(shared["genre_ids"], 1) if shared["genre_ids"] else [],
        }

    # --- CRUD REST: POST -> GET -> PUT -> PATCH -> DELETE ---------------------
    @task(3)
    def crud_rest(self):
        book = self.new_book()
        isbn = book["isbn"]
        h = self.auth_headers()

        with self.client.post("/books", json=book, headers=h, name="POST /books",
                              catch_response=True) as r:
            expect(r, 200, 201)
            if r.status_code not in (200, 201):
                return

        with self.client.get("/books/%s" % isbn, name="/books/[isbn]", catch_response=True) as r:
            expect(r, 200)

        full = {k: book[k] for k in ("title", "publication_year", "price", "stock",
                                     "format_id", "category_id")}
        full["title"] += " (PUT)"
        with self.client.put("/books/%s" % isbn, json=full, headers=h, name="PUT /books/[isbn]",
                             catch_response=True) as r:
            expect(r, 200)

        with self.client.patch("/books/%s" % isbn, json={"stock": random.randint(0, 99)},
                               headers=h, name="PATCH /books/[isbn]", catch_response=True) as r:
            expect(r, 200)

        with self.client.delete("/books/%s" % isbn, headers=h, name="DELETE /books/[isbn]",
                                catch_response=True) as r:
            expect(r, 200, 204)

    # --- El mismo CRUD por los alias heredados /api/book/... ------------------
    @task(1)
    def crud_api_alias(self):
        book = self.new_book()
        isbn = book["isbn"]
        h = self.auth_headers()

        with self.client.post("/api/book/insert", json=book, headers=h,
                              name="POST /api/book/insert", catch_response=True) as r:
            expect(r, 200, 201)
            if r.status_code not in (200, 201):
                return

        # El alias por POST acepta actualizacion parcial (por PUT exige el libro completo).
        with self.client.post("/api/book/update/%s" % isbn, json={"price": 199.0}, headers=h,
                              name="POST /api/book/update/[isbn]", catch_response=True) as r:
            expect(r, 200)

        with self.client.patch("/api/book/patch/%s" % isbn, json={"stock": 7}, headers=h,
                               name="PATCH /api/book/patch/[isbn]", catch_response=True) as r:
            expect(r, 200)

        with self.client.post("/api/book/delete/%s" % isbn, headers=h,
                              name="POST /api/book/delete/[isbn]", catch_response=True) as r:
            expect(r, 200, 204)

    # --- Escrituras SIN token: el servicio debe rechazarlas con 401 -----------
    @task(1)
    def write_without_token(self):
        with self.client.post("/books", json=self.new_book(), name="POST /books (sin token -> 401)",
                              catch_response=True) as r:
            expect(r, 401)

    # --- Operaciones SOAP (POST /soap) ----------------------------------------
    def soap(self, operation, **fields):
        h = self.auth_headers({"Content-Type": "text/xml; charset=utf-8",
                               "SOAPAction": operation})
        with self.client.post("/soap", data=soap_envelope(operation, **fields), headers=h,
                              name="POST /soap %s" % operation, catch_response=True) as r:
            expect(r, 200, content="xml")

    @task(2)
    def soap_conceptos_pendientes(self):
        self.soap("ObtenerConceptosPendientes")

    @task(2)
    def soap_estadisticas(self):
        self.soap("ObtenerEstadisticasPorModelo")

    @task(1)
    def soap_progreso(self):
        self.soap("ObtenerProgresoUsuario", correo="locust@library.local")

    @task(1)
    def soap_registrar(self):
        self.soap("RegistrarClasificacion",
                  nombre="Locust", apellidos="Carga", correo="locust@library.local",
                  isbn=any_isbn(), texto_evaluado="Prueba de estres con Locust",
                  modelo_cloud=random.choice(["IaaS", "PaaS", "SaaS", "FaaS"]))

"""
==============================================================================
PROYECTO: INTEGRACION03 - MICROSERVICIO DE AUTORES
TECNOLOGIAS: Python 3, Flask, Psycopg v3, PostgreSQL, Flasgger (OpenAPI)
AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
PUERTO: 5003

QUE ADMINISTRA
--------------
Autores y su relación con los libros (tabla puente `book_authors`).

A diferencia del servicio de usuarios, aquí las LECTURAS SÍ son públicas: un
autor y su bibliografía son metadatos de catálogo, no datos personales. Eso es
justo lo que pide el enunciado: "las lecturas GET pueden mantenerse públicas si
solo consultan información; las lecturas administrativas deberían exigir JWT".

DECISIONES DE DISEÑO
--------------------
1. LA AUTORIZACIÓN SIGUE DECIDIÉNDOSE POR MÉTODO, NO POR ENDPOINT.
   `GET`/`HEAD`/`OPTIONS` pasan sin token (son lecturas de catálogo); cualquier
   otro método exige JWT **y** rol Administrador. Al decidir por método, añadir
   mañana `POST /autores/<id>/fotos` queda protegido sin tocar el guardián.

2. LA RELACIÓN CON LIBROS ES UN RECURSO PROPIO.
   `POST /autores/<id>/libros` y `DELETE /autores/<id>/libros/<book_id>` manejan
   la tabla puente. Se modela así, y no como un campo `books: [...]` dentro del
   autor, porque la relación tiene identidad propia y así el endpoint dice
   exactamente qué se está creando o destruyendo.

3. CACHÉ EN REDIS CON INVALIDACIÓN POR MÉTODO.
   `GET /autores` y `GET /autores/<id>` se cachean con TTL corto. Cualquier
   escritura exitosa invalida TODO el caché del recurso en `after_request`; de
   ese modo no hay forma de olvidar invalidar una clave concreta. El caché es
   opcional por diseño: si Redis no responde, se va a PostgreSQL y la lectura
   sigue funcionando (fail-open). Lo que NO se degrada es la autorización.

4. NO SE PUEDE BORRAR UN AUTOR CON LIBROS.
   La FK de `book_authors` lo impediría de todos modos, pero se comprueba antes
   para poder responder 409 con un mensaje útil en vez de un error de integridad.
==============================================================================
"""

import os
import sys

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import ForeignKeyViolation
from dotenv import load_dotenv
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flasgger import Swagger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt_auth     # noqa: E402
import redis_layer  # noqa: E402

# ==============================================================================
# 1. CONFIGURACIÓN
# ==============================================================================

load_dotenv()

SERVICE_NAME = "autores-microservice"
APP_VERSION = "1.0.0"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "library_user"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "library"),
}

JWT_SECRET         = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM      = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER         = os.getenv("JWT_ISSUER", "library-login")
JWT_AUDIENCE       = os.getenv("JWT_AUDIENCE", "library-api")
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", "5"))
LOGIN_BASE_URL     = os.getenv("LOGIN_BASE_URL", "http://localhost:5000").rstrip("/")
ADMIN_ROLE_ID      = int(os.getenv("ADMIN_ROLE_ID", "1"))

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,http://34.51.29.27:3000"
)
CORS_ORIGINS = [o.strip() for o in
                os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()]

PAGE_SIZE_MAX = int(os.getenv("PAGE_SIZE_MAX", "100"))

if not JWT_SECRET:
    print("[AVISO] JWT_SECRET no está definido: las escrituras responderán 401.")

PUBLIC_PATHS = {"/", "/health", "/docs", "/apispec.json"}

# Lecturas de catálogo: públicas por ser información, no datos personales.
PUBLIC_GET_PREFIXES = ("/autores",)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

app = Flask(__name__)
app.json.sort_keys = False
CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}}, expose_headers=["WWW-Authenticate"])

swagger_config = {
    "headers": [],
    "specs": [{
        "endpoint": "apispec",
        "route": "/apispec.json",
        "rule_filter": lambda rule: True,
        "model_filter": lambda tag: True,
    }],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs",
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Microservicio de Autores — Library",
        "description": (
            "Administración de autores y de su relación con los libros.\n\n"
            "**Seguridad:** las lecturas (`GET`) son públicas porque consultan "
            "metadatos de catálogo. Las escrituras exigen "
            "`Authorization: Bearer <JWT>` con rol Administrador, y el token se "
            "comprueba contra la lista de revocación en Redis."
        ),
        "version": APP_VERSION,
    },
    "securityDefinitions": {
        "Bearer": {"type": "apiKey", "name": "Authorization", "in": "header",
                   "description": "Escribe: Bearer <access_token>"}
    },
    "security": [{"Bearer": []}],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# ==============================================================================
# 2. BASE DE DATOS
# ==============================================================================

def get_db_connection():
    return psycopg.connect(**DB_CONFIG, row_factory=dict_row)


def fetch_all(sql, params=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def fetch_one(sql, params=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def execute(sql, params=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


# ==============================================================================
# 3. RESPUESTAS
# ==============================================================================

def ok(data=None, message=None, status=200, extra=None):
    payload = {"status": "ok"}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if extra:
        payload.update(extra)
    return jsonify(payload), status


def fail(code, message, status=400, hint=None):
    payload = {"status": "error", "code": code, "error": message, "status_code": status}
    if hint:
        payload["hint"] = hint
    return jsonify(payload), status


def unauthorized(code, message, status=401):
    """`fail()` devuelve una tupla: hay que reponer `status_code` al desenvolverla."""
    resp, _ = fail(code, message, status,
                   hint="Envía 'Authorization: Bearer <access_token>'.")
    resp.status_code = status
    resp.headers["WWW-Authenticate"] = (
        'Bearer realm="library-autores", error="%s", error_description="%s"'
        % (code, message.replace('"', "'"))
    )
    return resp


def bearer_token():
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    legacy = request.headers.get("X-Session-Token")
    return legacy.strip() if legacy else None


# ==============================================================================
# 4. GUARDIÁN DE AUTORIZACIÓN
# ==============================================================================

def is_public_read(method, path):
    if method not in SAFE_METHODS:
        return False
    return any(path.startswith(p) for p in PUBLIC_GET_PREFIXES)


@app.before_request
def enforce_auth():
    if request.method == "OPTIONS":
        return None

    path = request.path.rstrip("/") or "/"
    if path in PUBLIC_PATHS or path.startswith("/flasgger_static"):
        return None
    if is_public_read(request.method, path):
        return None

    token = bearer_token()
    if not token:
        return unauthorized(
            "TOKEN_REQUIRED",
            "Esta operación modifica el catálogo de autores y requiere autenticación.",
        )

    try:
        claims = jwt_auth.decode_jwt(
            token, JWT_SECRET, algorithms=(JWT_ALGORITHM,),
            issuer=JWT_ISSUER, audience=JWT_AUDIENCE, leeway=JWT_LEEWAY_SECONDS,
        )
    except jwt_auth.JWTError as exc:
        return unauthorized(exc.code, exc.message, exc.status)

    try:
        if redis_layer.is_revoked(claims.get("jti")):
            return unauthorized("TOKEN_REVOKED",
                                "El token fue revocado (sesión cerrada).")
    except redis_layer.RedisUnavailable as exc:
        resp, _ = fail(exc.code, str(exc), exc.status)
        resp.status_code = exc.status
        resp.headers["Retry-After"] = "5"
        return resp

    g.claims = claims

    # Toda escritura exige rol Administrador.
    if claims.get("role_id") != ADMIN_ROLE_ID:
        return unauthorized("FORBIDDEN_ROLE",
                            "Esta operación exige rol Administrador.", 403)
    return None


# ==============================================================================
# 5. SERIALIZACIÓN
# ==============================================================================

AUTHOR_FIELDS = "a.id, a.name, a.biography, a.country"


def serialize_author(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "biography": row["biography"],
        "country": row["country"],
    }


# ==============================================================================
# 6. ENDPOINTS
# ==============================================================================

@app.route("/", methods=["GET"])
def index():
    """Información del servicio e hipermedia."""
    return ok({
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "description": "Administración de autores y su relación con los libros.",
        "auth": "Escrituras: Authorization: Bearer <access_token> (JWT HS256, rol Administrador)",
        "_links": {
            "self":    {"href": "/",         "method": "GET"},
            "health":  {"href": "/health",   "method": "GET"},
            "autores": {"href": "/autores",  "method": "GET"},
            "docs":    {"href": "/docs",     "method": "GET"},
            "login":   {"href": LOGIN_BASE_URL + "/login", "method": "POST"},
        },
    })


@app.route("/health", methods=["GET"])
def health():
    """Sonda de estado: base de datos, JWT y Redis."""
    try:
        row = fetch_one("SELECT version() AS version, CURRENT_TIMESTAMP AS server_time")
        return ok({
            "status": "healthy",
            "service": SERVICE_NAME,
            "database": "connected",
            "postgres_version": (row["version"] or "").split(" on ")[0],
            "server_time": row["server_time"].isoformat(),
            "jwt": {
                "enabled": bool(JWT_SECRET),
                "algorithm": JWT_ALGORITHM,
                "issuer": JWT_ISSUER,
                "audience": JWT_AUDIENCE,
                "admin_role_id": ADMIN_ROLE_ID,
            },
            "public_reads": list(PUBLIC_GET_PREFIXES),
            "cors_origins": CORS_ORIGINS,
            "redis": redis_layer.health(),
        })
    except Exception as exc:
        return fail("DATABASE_UNAVAILABLE", "No fue posible conectar con PostgreSQL: %s" % exc, 503)


@app.route("/autores", methods=["GET"])
def list_autores():
    """Lista autores con filtros y paginación. Lectura pública (caché en Redis).
    ---
    tags: [Autores]
    parameters:
      - {name: name, in: query, type: string, required: false, description: "Coincidencia parcial"}
      - {name: country, in: query, type: string, required: false}
      - {name: limit, in: query, type: integer, required: false, default: 50}
      - {name: offset, in: query, type: integer, required: false, default: 0}
    responses:
      200: {description: Lista de autores.}
    """
    name = request.args.get("name")
    country = request.args.get("country")
    limit = min(max(int(request.args.get("limit", 50)), 1), PAGE_SIZE_MAX)
    offset = max(int(request.args.get("offset", 0)), 0)

    cache_key = redis_layer.resource_list_key(
        "autores", {"name": name, "country": country, "limit": limit, "offset": offset})
    cached = redis_layer.cache_get(cache_key)
    if cached is not None:
        return ok(cached, extra={"count": len(cached), "cache": "hit"})

    where, params = [], []
    if name:
        where.append("a.name ILIKE %s")
        params.append("%" + name.strip() + "%")
    if country:
        where.append("a.country ILIKE %s")
        params.append("%" + country.strip() + "%")

    sql = ("SELECT " + AUTHOR_FIELDS +
           ", (SELECT count(*) FROM book_authors ba WHERE ba.author_id = a.id) AS books_count"
           " FROM authors a")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.name ASC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = fetch_all(sql, tuple(params))
    data = [dict(serialize_author(r), books_count=r["books_count"]) for r in rows]
    redis_layer.cache_set(cache_key, data)
    return ok(data, extra={"count": len(data), "cache": "miss"})


@app.route("/autores/<int:author_id>", methods=["GET"])
def get_autor(author_id):
    """Detalle de un autor, con la lista de sus libros. Lectura pública."""
    cache_key = redis_layer.resource_key("autores", author_id)
    cached = redis_layer.cache_get(cache_key)
    if cached is not None:
        return ok(cached, extra={"cache": "hit"})

    row = fetch_one("SELECT " + AUTHOR_FIELDS + " FROM authors a WHERE a.id = %s", (author_id,))
    if not row:
        return fail("AUTHOR_NOT_FOUND", "No existe un autor con id %s." % author_id, 404)

    books = fetch_all(
        """SELECT b.id, b.isbn, b.title, b.publication_year, b.price
             FROM book_authors ba JOIN books b ON b.id = ba.book_id
            WHERE ba.author_id = %s ORDER BY b.title ASC""",
        (author_id,))
    data = dict(serialize_author(row),
                books=[dict(b, publication_year=b["publication_year"]) for b in books],
                books_count=len(books))
    redis_layer.cache_set(cache_key, data)
    return ok(data, extra={"cache": "miss"})


@app.route("/autores/<int:author_id>/libros", methods=["GET"])
def get_autor_books(author_id):
    """Libros de un autor. Lectura pública."""
    if not fetch_one("SELECT 1 FROM authors WHERE id = %s", (author_id,)):
        return fail("AUTHOR_NOT_FOUND", "No existe un autor con id %s." % author_id, 404)
    rows = fetch_all(
        """SELECT b.id, b.isbn, b.title, b.publication_year, b.price
             FROM book_authors ba JOIN books b ON b.id = ba.book_id
            WHERE ba.author_id = %s ORDER BY b.title ASC""",
        (author_id,))
    return ok([dict(r) for r in rows], extra={"count": len(rows)})


@app.route("/autores", methods=["POST"])
def create_autor():
    """Crea un autor. Exige rol Administrador.
    ---
    tags: [Autores]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [name]
          properties:
            name: {type: string}
            biography: {type: string}
            country: {type: string}
    responses:
      201: {description: Autor creado.}
      400: {description: Validación.}
    """
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return fail("VALIDATION_ERROR", "El campo 'name' es obligatorio.", 400)

    row = fetch_one(
        """INSERT INTO authors (name, biography, country)
           VALUES (%s, %s, %s) RETURNING id, name, biography, country""",
        (name, (body.get("biography") or "").strip() or None,
         (body.get("country") or "").strip() or None))
    return ok(serialize_author(row), message="Autor creado.", status=201)


@app.route("/autores/<int:author_id>", methods=["PUT"])
def replace_autor(author_id):
    """Reemplazo completo del autor (400 si falta un campo editable)."""
    body = request.get_json(silent=True) or {}
    missing = [f for f in ("name", "biography", "country") if f not in body]
    if missing:
        return fail("VALIDATION_ERROR",
                    "PUT reemplaza el recurso completo. Faltan: %s." % ", ".join(missing), 400)
    name = (body.get("name") or "").strip()
    if not name:
        return fail("VALIDATION_ERROR", "El campo 'name' no puede quedar vacío.", 400)

    updated = execute(
        "UPDATE authors SET name=%s, biography=%s, country=%s WHERE id=%s",
        (name, (body.get("biography") or "").strip() or None,
         (body.get("country") or "").strip() or None, author_id))
    if not updated:
        return fail("AUTHOR_NOT_FOUND", "No existe un autor con id %s." % author_id, 404)

    row = fetch_one("SELECT " + AUTHOR_FIELDS + " FROM authors a WHERE a.id = %s", (author_id,))
    return ok(serialize_author(row), message="Autor reemplazado.")


@app.route("/autores/<int:author_id>", methods=["PATCH"])
def patch_autor(author_id):
    """Modificación parcial: solo cambia los campos presentes."""
    body = request.get_json(silent=True) or {}
    sets, params = [], []
    for field in ("name", "biography", "country"):
        if field in body:
            value = (body.get(field) or "").strip() or None
            if field == "name" and not value:
                return fail("VALIDATION_ERROR", "El campo 'name' no puede quedar vacío.", 400)
            sets.append("%s = %%s" % field)
            params.append(value)

    if not sets:
        return fail("VALIDATION_ERROR", "No se envió ningún campo modificable.", 400)

    params.append(author_id)
    updated = execute("UPDATE authors SET " + ", ".join(sets) + " WHERE id = %s", tuple(params))
    if not updated:
        return fail("AUTHOR_NOT_FOUND", "No existe un autor con id %s." % author_id, 404)

    row = fetch_one("SELECT " + AUTHOR_FIELDS + " FROM authors a WHERE a.id = %s", (author_id,))
    return ok(serialize_author(row), message="Autor actualizado.")


@app.route("/autores/<int:author_id>", methods=["DELETE"])
def delete_autor(author_id):
    """Elimina un autor. Falla con 409 si todavía tiene libros asociados."""
    try:
        deleted = execute("DELETE FROM authors WHERE id = %s", (author_id,))
    except ForeignKeyViolation:
        return fail("AUTHOR_IN_USE",
                    "El autor tiene libros asociados. Quita la relación con "
                    "DELETE /autores/%d/libros/<book_id> antes de borrarlo." % author_id, 409)

    if not deleted:
        return fail("AUTHOR_NOT_FOUND", "No existe un autor con id %s." % author_id, 404)
    return ok({"id": author_id}, message="Autor eliminado.")


@app.route("/autores/<int:author_id>/libros", methods=["POST"])
def link_books(author_id):
    """Asocia uno o varios libros al autor (relación en `book_authors`).
    ---
    tags: [Autores]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [book_ids]
          properties:
            book_ids: {type: array, items: {type: integer}}
    responses:
      200: {description: Relaciones creadas.}
      404: {description: El autor o algún libro no existe.}
    """
    body = request.get_json(silent=True) or {}
    book_ids = body.get("book_ids") or ([body["book_id"]] if body.get("book_id") else [])
    if not isinstance(book_ids, list) or not book_ids:
        return fail("VALIDATION_ERROR",
                    "Se requiere 'book_ids' (lista de ids de libro) o 'book_id'.", 400)

    if not fetch_one("SELECT 1 FROM authors WHERE id = %s", (author_id,)):
        return fail("AUTHOR_NOT_FOUND", "No existe un autor con id %s." % author_id, 404)

    linked, already, missing = [], [], []
    for book_id in book_ids:
        if not fetch_one("SELECT 1 FROM books WHERE id = %s", (book_id,)):
            missing.append(book_id)
            continue
        # ON CONFLICT evita reventar si la relación ya existía: se informa aparte.
        inserted = execute(
            "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING", (book_id, author_id))
        (linked if inserted else already).append(book_id)

    if missing:
        return fail("BOOK_NOT_FOUND",
                    "No existen los libros: %s." % ", ".join(str(m) for m in missing), 404)

    return ok({"linked": linked, "already_linked": already},
              message="Relación con libros actualizada.")


@app.route("/autores/<int:author_id>/libros/<int:book_id>", methods=["DELETE"])
def unlink_book(author_id, book_id):
    """Quita la relación entre un autor y un libro (no borra el libro)."""
    deleted = execute("DELETE FROM book_authors WHERE author_id = %s AND book_id = %s",
                      (author_id, book_id))
    if not deleted:
        return fail("RELATION_NOT_FOUND",
                    "El autor %s no está relacionado con el libro %s." % (author_id, book_id), 404)
    return ok({"author_id": author_id, "book_id": book_id},
              message="Relación eliminada.")


# ==============================================================================
# 7. INVALIDACIÓN DEL CACHÉ
# ==============================================================================

@app.after_request
def invalidate_cache(response):
    """Toda escritura exitosa invalida el caché del recurso.

    Se decide por MÉTODO, no por ruta: así quedan cubiertas de una vez la
    creación, el reemplazo, el parche, el borrado y las dos rutas de relación
    (`/autores/<id>/libros`), sin enumerarlas ni poder olvidar una.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and response.status_code < 400:
        response.headers["X-Cache-Invalidated"] = str(redis_layer.invalidate_resource("autores"))
    return response


# ==============================================================================
# 8. ARRANQUE
# ==============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    print("%s escuchando en http://0.0.0.0:%d  (docs en /docs)" % (SERVICE_NAME, port))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "False").lower() == "true")

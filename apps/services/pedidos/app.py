"""
==============================================================================
PROYECTO: INTEGRACION03 - MICROSERVICIO DE PEDIDOS
TECNOLOGIAS: Python 3, Flask, Psycopg v3, PostgreSQL, Flasgger (OpenAPI)
AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
PUERTO: 5004

QUE ADMINISTRA
--------------
Pedidos, líneas de pedido, stock y estados.

DECISIONES DE DISEÑO
--------------------
1. TODAS LAS OPERACIONES EXIGEN JWT. Un pedido es un dato del usuario, no
   catálogo. Además, un usuario normal solo ve y crea SUS pedidos; el
   administrador ve todos. Se comprueba en cada endpoint, no en el guardián,
   porque la regla depende del recurso concreto.

2. EL STOCK NO SE LEE Y LUEGO SE ESCRIBE: SE DESCUENTA EN UN UPDATE CONDICIONAL.
       UPDATE books SET stock = stock - %s WHERE id = %s AND stock >= %s
   Si `rowcount` es 0, no había existencias y se aborta. Comprobar con un SELECT
   previo sería una condición de carrera: dos pedidos simultáneos podrían leer
   stock=1 y ambos venderlo. Con el UPDATE condicional la comprobación y la
   escritura son la MISMA operación atómica.

3. TODO EL PEDIDO VIVE EN UNA SOLA TRANSACCIÓN. Crear la cabecera, insertar las
   líneas y descontar el stock ocurren juntos o no ocurren. Si algo falla, el
   `with conn:` de psycopg hace ROLLBACK y no queda un pedido a medias con el
   stock ya descontado.

4. EL TOTAL LO CALCULA POSTGRESQL, NO PYTHON. Es NUMERIC(10,2) y sumar en la
   base evita los errores de redondeo de los flotantes.

5. LOS ESTADOS SON UNA MÁQUINA CERRADA. No se puede pasar de 'Pendiente' a
   'Entregado' sin confirmar y pagar. Las transiciones permitidas están en
   TRANSICIONES y se validan antes de escribir.

6. CANCELAR DEVUELVE EL STOCK. Es la operación inversa de crear, y por eso
   ocurre también en su propia transacción.
==============================================================================
"""

import os
import sys
from decimal import Decimal
from datetime import datetime, date

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

SERVICE_NAME = "pedidos-microservice"
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
    print("[AVISO] JWT_SECRET no está definido: TODA petición responderá 401.")

PUBLIC_PATHS = {"/", "/health", "/docs", "/apispec.json"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# --- Máquina de estados -------------------------------------------------------
ESTADOS = ("Pendiente", "Confirmado", "Pagado", "Enviado", "Entregado", "Cancelado")

TRANSICIONES = {
    "Pendiente":  {"Confirmado", "Cancelado"},
    "Confirmado": {"Pagado", "Cancelado"},
    "Pagado":     {"Enviado", "Cancelado"},
    "Enviado":    {"Entregado"},
    "Entregado":  set(),
    "Cancelado":  set(),
}

# Estados en los que el pedido ya salió de almacén: cancelar ya no devuelve stock.
ESTADOS_CON_STOCK_COMPROMETIDO = {"Pendiente", "Confirmado", "Pagado"}

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
        "title": "Microservicio de Pedidos — Library",
        "description": (
            "Creación y gestión de pedidos, líneas de pedido, stock y estados.\n\n"
            "**Seguridad:** todas las operaciones exigen "
            "`Authorization: Bearer <JWT>`. Un usuario ve y crea solo sus pedidos; "
            "el rol Administrador ve todos. El token se comprueba contra la lista "
            "de revocación en Redis.\n\n"
            "**Estados:** " + " -> ".join(ESTADOS)
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


# ==============================================================================
# 3. RESPUESTAS
# ==============================================================================

def jsonable(value):
    """Convierte Decimal y fechas a tipos que jsonify sabe serializar.

    El dinero viaja como número (float) para que el cliente Tk lo muestre sin
    tener que interpretar cadenas; la aritmética fina se hizo antes, en
    PostgreSQL con NUMERIC, así que aquí ya no hay riesgo de redondeo.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    return value


def ok(data=None, message=None, status=200, extra=None):
    payload = {"status": "ok"}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = jsonable(data)
    if extra:
        payload.update(jsonable(extra))
    return jsonify(payload), status


def fail(code, message, status=400, hint=None, extra=None):
    """Error uniforme. `extra` añade contexto útil (p. ej. el stock disponible)."""
    payload = {"status": "error", "code": code, "error": message, "status_code": status}
    if hint:
        payload["hint"] = hint
    if extra:
        payload.update(jsonable(extra))
    return jsonify(payload), status


def unauthorized(code, message, status=401):
    """`fail()` devuelve una tupla: hay que reponer `status_code` al desenvolverla."""
    resp, _ = fail(code, message, status,
                   hint="Envía 'Authorization: Bearer <access_token>'.")
    resp.status_code = status
    resp.headers["WWW-Authenticate"] = (
        'Bearer realm="library-pedidos", error="%s", error_description="%s"'
        % (code, message.replace('"', "'"))
    )
    return resp


def bearer_token():
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    legacy = request.headers.get("X-Session-Token")
    return legacy.strip() if legacy else None


class BusinessError(Exception):
    """Error de negocio dentro de una transacción: provoca ROLLBACK y se traduce a HTTP."""

    def __init__(self, code, message, status=400, extra=None):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra


# ==============================================================================
# 4. GUARDIÁN DE AUTORIZACIÓN
# ==============================================================================

@app.before_request
def enforce_auth():
    """Todo exige JWT: no hay lecturas públicas en este servicio."""
    if request.method == "OPTIONS":
        return None

    path = request.path.rstrip("/") or "/"
    if path in PUBLIC_PATHS or path.startswith("/flasgger_static"):
        return None

    token = bearer_token()
    if not token:
        return unauthorized(
            "TOKEN_REQUIRED",
            "Los pedidos son datos del usuario: se requiere autenticación.",
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
    return None


def current_user_id():
    return int(g.claims["sub"])


def is_admin():
    return g.claims.get("role_id") == ADMIN_ROLE_ID


# ==============================================================================
# 5. LECTURA DE PEDIDOS
# ==============================================================================

ORDER_FIELDS = ("p.id, p.user_id, p.estado, p.total, p.notas, "
                "p.created_at, p.updated_at")


def load_order(order_id, cur=None):
    sql = "SELECT " + ORDER_FIELDS + " FROM pedidos p WHERE p.id = %s"
    if cur is not None:
        cur.execute(sql, (order_id,))
        return cur.fetchone()
    return fetch_one(sql, (order_id,))


def load_lines(order_id):
    return fetch_all(
        """SELECT l.id, l.book_id, b.title, b.isbn, l.cantidad, l.precio_unitario,
                  (l.cantidad * l.precio_unitario) AS subtotal
             FROM pedido_lineas l JOIN books b ON b.id = l.book_id
            WHERE l.pedido_id = %s ORDER BY l.id ASC""",
        (order_id,))


def recalc_total(cur, order_id):
    """El total lo suma PostgreSQL sobre NUMERIC: sin redondeo de flotantes."""
    cur.execute("""UPDATE pedidos SET total = COALESCE(
                       (SELECT SUM(cantidad * precio_unitario) FROM pedido_lineas
                         WHERE pedido_id = %s), 0),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s RETURNING total""", (order_id, order_id))
    return cur.fetchone()["total"]


def assert_visible(order):
    """Un usuario normal solo accede a sus pedidos."""
    if not is_admin() and order["user_id"] != current_user_id():
        raise BusinessError("FORBIDDEN_ORDER",
                            "Este pedido pertenece a otro usuario.", 403)


# ==============================================================================
# 6. ENDPOINTS
# ==============================================================================

@app.route("/", methods=["GET"])
def index():
    """Información del servicio, estados válidos e hipermedia."""
    return ok({
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "description": "Pedidos, líneas de pedido, stock y estados.",
        "auth": "Todas las operaciones exigen Authorization: Bearer <access_token>",
        "estados": list(ESTADOS),
        "transiciones": {k: sorted(v) for k, v in TRANSICIONES.items()},
        "_links": {
            "self":    {"href": "/",        "method": "GET"},
            "health":  {"href": "/health",  "method": "GET"},
            "pedidos": {"href": "/pedidos", "method": "GET"},
            "docs":    {"href": "/docs",    "method": "GET"},
            "login":   {"href": LOGIN_BASE_URL + "/login", "method": "POST"},
        },
    })


@app.route("/health", methods=["GET"])
def health():
    """Sonda de estado: base de datos, esquema, JWT y Redis."""
    try:
        row = fetch_one("SELECT version() AS version, CURRENT_TIMESTAMP AS server_time")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT to_regclass('public.pedidos')       IS NOT NULL AS pedidos,
                                      to_regclass('public.pedido_lineas') IS NOT NULL AS lineas""")
                schema = cur.fetchone()
        ready = all(schema.values())
        return ok({
            "status": "healthy",
            "service": SERVICE_NAME,
            "database": "connected",
            "postgres_version": (row["version"] or "").split(" on ")[0],
            "schema": "ready" if ready else "migration_pending",
            "migration_hint": None if ready else (
                "Falta aplicar apps/services/pedidos/sql/01_migration_pedidos.sql."
            ),
            "server_time": row["server_time"].isoformat(),
            "estados": list(ESTADOS),
            "jwt": {
                "enabled": bool(JWT_SECRET),
                "algorithm": JWT_ALGORITHM,
                "issuer": JWT_ISSUER,
                "audience": JWT_AUDIENCE,
                "admin_role_id": ADMIN_ROLE_ID,
            },
            "cors_origins": CORS_ORIGINS,
            "redis": redis_layer.health(),
        })
    except Exception as exc:
        return fail("DATABASE_UNAVAILABLE", "No fue posible conectar con PostgreSQL: %s" % exc, 503)


@app.route("/pedidos", methods=["GET"])
def list_pedidos():
    """Lista pedidos. El administrador ve todos; el usuario, solo los suyos.
    ---
    tags: [Pedidos]
    parameters:
      - {name: estado, in: query, type: string, required: false, enum: [Pendiente, Confirmado, Pagado, Enviado, Entregado, Cancelado]}
      - {name: user_id, in: query, type: integer, required: false, description: "Solo el administrador puede filtrar por otro usuario"}
      - {name: limit, in: query, type: integer, required: false, default: 50}
      - {name: offset, in: query, type: integer, required: false, default: 0}
    responses:
      200: {description: Lista de pedidos.}
      401: {description: Token ausente, inválido o revocado.}
    """
    where, params = [], []

    # Aislamiento: el filtro por usuario se impone SIEMPRE que no sea admin.
    target_user = request.args.get("user_id")
    if is_admin():
        if target_user:
            where.append("p.user_id = %s")
            params.append(int(target_user))
    else:
        where.append("p.user_id = %s")
        params.append(current_user_id())

    estado = request.args.get("estado")
    if estado:
        if estado not in ESTADOS:
            return fail("INVALID_ESTADO", "Estado no válido: %s." % estado, 400)
        where.append("p.estado = %s")
        params.append(estado)

    limit = min(max(int(request.args.get("limit", 50)), 1), PAGE_SIZE_MAX)
    offset = max(int(request.args.get("offset", 0)), 0)

    sql = "SELECT " + ORDER_FIELDS + " FROM pedidos p"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = fetch_all(sql, tuple(params))
    return ok([dict(r) for r in rows], extra={"count": len(rows)})


@app.route("/pedidos/<int:order_id>", methods=["GET"])
def get_pedido(order_id):
    """Detalle de un pedido con sus líneas. Solo el dueño o un administrador."""
    order = load_order(order_id)
    if not order:
        return fail("ORDER_NOT_FOUND", "No existe un pedido con id %s." % order_id, 404)
    if not is_admin() and order["user_id"] != current_user_id():
        return unauthorized("FORBIDDEN_ORDER", "Este pedido pertenece a otro usuario.", 403)

    lines = load_lines(order_id)
    return ok(dict(order, lineas=[dict(l) for l in lines], lineas_count=len(lines)))


@app.route("/pedidos", methods=["POST"])
def create_pedido():
    """Crea un pedido con sus líneas y descuenta el stock, todo en una transacción.
    ---
    tags: [Pedidos]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [lineas]
          properties:
            user_id: {type: integer, description: "Solo el administrador puede crear para otro usuario"}
            notas: {type: string}
            lineas:
              type: array
              items:
                type: object
                required: [book_id, cantidad]
                properties:
                  book_id: {type: integer}
                  cantidad: {type: integer}
    responses:
      201: {description: Pedido creado.}
      409: {description: Stock insuficiente.}
    """
    body = request.get_json(silent=True) or {}
    lineas = body.get("lineas") or []
    if not isinstance(lineas, list) or not lineas:
        return fail("VALIDATION_ERROR", "Se requiere 'lineas' con al menos un renglón.", 400)

    # Solo el administrador puede crear un pedido a nombre de otro.
    user_id = current_user_id()
    if is_admin() and body.get("user_id"):
        user_id = int(body["user_id"])

    # Se agrupan cantidades repetidas del mismo libro para no chocar con el
    # UNIQUE (pedido_id, book_id) y para descontar el stock una sola vez.
    cantidades = {}
    for linea in lineas:
        book_id, cantidad = linea.get("book_id"), linea.get("cantidad")
        if not book_id or not isinstance(cantidad, int) or cantidad <= 0:
            return fail("VALIDATION_ERROR",
                        "Cada línea requiere 'book_id' y 'cantidad' (entero > 0).", 400)
        cantidades[int(book_id)] = cantidades.get(int(book_id), 0) + cantidad

    try:
        with get_db_connection() as conn:          # <- transacción: commit o ROLLBACK
            with conn.cursor() as cur:
                if not cur.execute("SELECT 1 FROM users WHERE id = %s", (user_id,)).fetchone():
                    raise BusinessError("USER_NOT_FOUND",
                                        "No existe el usuario %s." % user_id, 404)

                cur.execute("""INSERT INTO pedidos (user_id, estado, notas)
                               VALUES (%s, 'Pendiente', %s) RETURNING id""",
                            (user_id, (body.get("notas") or "").strip() or None))
                order_id = cur.fetchone()["id"]

                for book_id, cantidad in cantidades.items():
                    cur.execute("SELECT price FROM books WHERE id = %s FOR UPDATE", (book_id,))
                    book = cur.fetchone()
                    if not book:
                        raise BusinessError("BOOK_NOT_FOUND",
                                            "No existe el libro %s." % book_id, 404)

                    # Descuento CONDICIONAL: comprobar y escribir es una sola operación.
                    cur.execute("""UPDATE books SET stock = stock - %s
                                    WHERE id = %s AND stock >= %s""",
                                (cantidad, book_id, cantidad))
                    if cur.rowcount == 0:
                        cur.execute("SELECT stock FROM books WHERE id = %s", (book_id,))
                        raise BusinessError(
                            "INSUFFICIENT_STOCK",
                            "No hay existencias suficientes del libro %s." % book_id, 409,
                            extra={"book_id": book_id,
                                   "disponible": cur.fetchone()["stock"],
                                   "solicitado": cantidad})

                    # El precio se congela en la línea: el pedido es un documento
                    # histórico y no debe cambiar si mañana sube el precio.
                    cur.execute("""INSERT INTO pedido_lineas
                                       (pedido_id, book_id, cantidad, precio_unitario)
                                   VALUES (%s, %s, %s, %s)""",
                                (order_id, book_id, cantidad, book["price"]))

                recalc_total(cur, order_id)
                order = load_order(order_id, cur)
    except BusinessError as exc:
        return fail(exc.code, exc.message, exc.status, extra=exc.extra)

    return ok(dict(order, lineas=[dict(l) for l in load_lines(order_id)]),
              message="Pedido creado.", status=201)


@app.route("/pedidos/<int:order_id>/lineas", methods=["POST"])
def add_line(order_id):
    """Añade un libro al pedido o sube la cantidad si ya estaba.

    Solo se permite mientras el pedido está 'Pendiente': una vez confirmado, sus
    líneas son un compromiso con el cliente y no se tocan.
    """
    body = request.get_json(silent=True) or {}
    book_id, cantidad = body.get("book_id"), body.get("cantidad")
    if not book_id or not isinstance(cantidad, int) or cantidad <= 0:
        return fail("VALIDATION_ERROR", "'book_id' y 'cantidad' (entero > 0) son obligatorios.", 400)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                order = load_order(order_id, cur)
                if not order:
                    raise BusinessError("ORDER_NOT_FOUND",
                                        "No existe un pedido con id %s." % order_id, 404)
                if not is_admin() and order["user_id"] != current_user_id():
                    raise BusinessError("FORBIDDEN_ORDER", "Este pedido pertenece a otro usuario.", 403)
                if order["estado"] != "Pendiente":
                    raise BusinessError("ORDER_NOT_EDITABLE",
                                        "Solo se pueden modificar líneas de un pedido 'Pendiente' "
                                        "(estado actual: %s)." % order["estado"], 409)

                cur.execute("SELECT price FROM books WHERE id = %s FOR UPDATE", (book_id,))
                book = cur.fetchone()
                if not book:
                    raise BusinessError("BOOK_NOT_FOUND", "No existe el libro %s." % book_id, 404)

                cur.execute("""UPDATE books SET stock = stock - %s
                                WHERE id = %s AND stock >= %s""", (cantidad, book_id, cantidad))
                if cur.rowcount == 0:
                    cur.execute("SELECT stock FROM books WHERE id = %s", (book_id,))
                    raise BusinessError("INSUFFICIENT_STOCK",
                                        "No hay existencias suficientes del libro %s." % book_id, 409,
                                        extra={"book_id": book_id,
                                               "disponible": cur.fetchone()["stock"],
                                               "solicitado": cantidad})

                cur.execute("""INSERT INTO pedido_lineas
                                   (pedido_id, book_id, cantidad, precio_unitario)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (pedido_id, book_id)
                               DO UPDATE SET cantidad = pedido_lineas.cantidad + EXCLUDED.cantidad""",
                            (order_id, book_id, cantidad, book["price"]))

                recalc_total(cur, order_id)
    except BusinessError as exc:
        return fail(exc.code, exc.message, exc.status, extra=exc.extra)

    return ok(dict(load_order(order_id), lineas=[dict(l) for l in load_lines(order_id)]),
              message="Línea agregada.", status=201)


@app.route("/pedidos/<int:order_id>/lineas/<int:line_id>", methods=["DELETE"])
def remove_line(order_id, line_id):
    """Quita una línea del pedido y DEVUELVE su cantidad al stock."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                order = load_order(order_id, cur)
                if not order:
                    raise BusinessError("ORDER_NOT_FOUND",
                                        "No existe un pedido con id %s." % order_id, 404)
                if not is_admin() and order["user_id"] != current_user_id():
                    raise BusinessError("FORBIDDEN_ORDER", "Este pedido pertenece a otro usuario.", 403)
                if order["estado"] != "Pendiente":
                    raise BusinessError("ORDER_NOT_EDITABLE",
                                        "Solo se pueden modificar líneas de un pedido 'Pendiente' "
                                        "(estado actual: %s)." % order["estado"], 409)

                cur.execute("""DELETE FROM pedido_lineas
                                WHERE id = %s AND pedido_id = %s
                                RETURNING book_id, cantidad""", (line_id, order_id))
                removed = cur.fetchone()
                if not removed:
                    raise BusinessError("LINE_NOT_FOUND",
                                        "El pedido %s no tiene la línea %s." % (order_id, line_id), 404)

                # Operación inversa de la creación: el stock regresa.
                cur.execute("UPDATE books SET stock = stock + %s WHERE id = %s",
                            (removed["cantidad"], removed["book_id"]))
                recalc_total(cur, order_id)
    except BusinessError as exc:
        return fail(exc.code, exc.message, exc.status, extra=exc.extra)

    return ok(dict(load_order(order_id), lineas=[dict(l) for l in load_lines(order_id)]),
              message="Línea eliminada y stock restituido.")


@app.route("/pedidos/<int:order_id>/estado", methods=["PATCH"])
def change_state(order_id):
    """Cambia el estado del pedido respetando la máquina de transiciones.
    ---
    tags: [Pedidos]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [estado]
          properties:
            estado: {type: string, enum: [Pendiente, Confirmado, Pagado, Enviado, Entregado, Cancelado]}
    responses:
      200: {description: Estado actualizado.}
      409: {description: Transición no permitida.}
    """
    body = request.get_json(silent=True) or {}
    nuevo = (body.get("estado") or "").strip()
    if nuevo not in ESTADOS:
        return fail("INVALID_ESTADO",
                    "Estado no válido: '%s'. Válidos: %s." % (nuevo, ", ".join(ESTADOS)), 400)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                order = load_order(order_id, cur)
                if not order:
                    raise BusinessError("ORDER_NOT_FOUND",
                                        "No existe un pedido con id %s." % order_id, 404)
                # Cancelar el pedido propio sí puede hacerlo un usuario normal;
                # cualquier otro cambio de estado es administrativo.
                if nuevo == "Cancelado":
                    if not is_admin() and order["user_id"] != current_user_id():
                        raise BusinessError("FORBIDDEN_ORDER",
                                            "Este pedido pertenece a otro usuario.", 403)
                elif not is_admin():
                    raise BusinessError("FORBIDDEN_ROLE",
                                        "Solo un administrador puede cambiar el estado a '%s'." % nuevo, 403)

                actual = order["estado"]
                if nuevo == actual:
                    raise BusinessError("SAME_ESTADO", "El pedido ya está en '%s'." % nuevo, 409)
                if nuevo not in TRANSICIONES[actual]:
                    raise BusinessError(
                        "INVALID_TRANSITION",
                        "No se puede pasar de '%s' a '%s'. Desde '%s' solo se puede ir a: %s."
                        % (actual, nuevo, actual,
                           ", ".join(sorted(TRANSICIONES[actual])) or "(ninguno)"), 409)

                # Cancelar devuelve el stock, pero solo si aún no se había enviado.
                if nuevo == "Cancelado" and actual in ESTADOS_CON_STOCK_COMPROMETIDO:
                    cur.execute("""UPDATE books b SET stock = b.stock + l.cantidad
                                     FROM pedido_lineas l
                                    WHERE l.pedido_id = %s AND b.id = l.book_id""", (order_id,))

                cur.execute("""UPDATE pedidos SET estado = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s""", (nuevo, order_id))
                order = load_order(order_id, cur)
    except BusinessError as exc:
        return fail(exc.code, exc.message, exc.status, extra=exc.extra)

    return ok(dict(order, lineas=[dict(l) for l in load_lines(order_id)]),
              message="Estado actualizado a '%s'." % nuevo)


@app.route("/pedidos/<int:order_id>", methods=["DELETE"])
def cancel_pedido(order_id):
    """Cancela el pedido (no lo borra: deja el histórico) y devuelve el stock.

    Se eligió cancelar en vez de borrar porque un pedido es un documento
    contable: la fila debe sobrevivir para poder auditar qué pasó.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                order = load_order(order_id, cur)
                if not order:
                    raise BusinessError("ORDER_NOT_FOUND",
                                        "No existe un pedido con id %s." % order_id, 404)
                if not is_admin() and order["user_id"] != current_user_id():
                    raise BusinessError("FORBIDDEN_ORDER", "Este pedido pertenece a otro usuario.", 403)

                actual = order["estado"]
                if actual == "Cancelado":
                    raise BusinessError("SAME_ESTADO", "El pedido ya estaba cancelado.", 409)
                if "Cancelado" not in TRANSICIONES[actual]:
                    raise BusinessError(
                        "INVALID_TRANSITION",
                        "Un pedido en estado '%s' ya no se puede cancelar." % actual, 409)

                if actual in ESTADOS_CON_STOCK_COMPROMETIDO:
                    cur.execute("""UPDATE books b SET stock = b.stock + l.cantidad
                                     FROM pedido_lineas l
                                    WHERE l.pedido_id = %s AND b.id = l.book_id""", (order_id,))

                cur.execute("""UPDATE pedidos SET estado = 'Cancelado',
                                                   updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s""", (order_id,))
                order = load_order(order_id, cur)
    except BusinessError as exc:
        return fail(exc.code, exc.message, exc.status, extra=exc.extra)

    return ok(dict(order), message="Pedido cancelado y stock restituido.")


# ==============================================================================
# 7. ARRANQUE
# ==============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5004"))
    print("%s escuchando en http://0.0.0.0:%d  (docs en /docs)" % (SERVICE_NAME, port))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "False").lower() == "true")

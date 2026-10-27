"""
==============================================================================
PROYECTO: INTEGRACION03 - MICROSERVICIO DE PAGOS
TECNOLOGIAS: Python 3, Flask, Psycopg v3, PostgreSQL, Flasgger (OpenAPI)
AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
PUERTO: 5005

QUE ADMINISTRA
--------------
Registra pagos y actualiza el estado de los pedidos.

DECISIONES DE DISEÑO
--------------------
1. EL PAGO Y EL CAMBIO DE ESTADO DEL PEDIDO OCURREN EN LA MISMA TRANSACCIÓN.
   El enunciado dice que este servicio "registra pagos y actualiza el estado de
   los pedidos". La tentación es que llame por HTTP al servicio de pedidos y le
   pida el cambio de estado; NO se hace así, y la razón es la atomicidad:

       si se registrara el pago y luego fallara la llamada al otro servicio,
       quedaría un cobro sin pedido pagado (o al revés) y nadie podría
       reconciliarlo sin intervención manual.

   Al compartir la base `library`, las dos escrituras caben en una transacción
   y PostgreSQL garantiza que ocurren juntas o no ocurren. El desacoplamiento
   se mantiene donde importa: el código, el despliegue y el contrato HTTP son
   independientes; lo que se comparte es la base de datos, que ya era el punto
   de verdad único del sistema.

2. UN PEDIDO PUEDE TENER VARIOS PAGOS.
   Un intento rechazado y luego uno aprobado, o un pago dividido. Por eso el
   historial completo se conserva y no se sobrescribe.

3. NO SE PUEDE COBRAR UN PEDIDO CANCELADO NI UNO YA PAGADO.
   Se comprueba el estado antes de insertar; si no, se podría cobrar dos veces.

4. LA MÁQUINA DE ESTADOS DEL PEDIDO SE RESPETA AQUÍ TAMBIÉN.
   Este servicio no puede saltarse las transiciones que valida el de pedidos:
   reutiliza la misma tabla de transiciones válidas.
==============================================================================
"""

import os
import sys
from decimal import Decimal
from datetime import datetime, date

import psycopg
from psycopg.rows import dict_row
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

SERVICE_NAME = "pagos-microservice"
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

METODOS_PAGO = ("Tarjeta", "Transferencia", "Efectivo", "PayPal")
ESTADOS_PAGO = ("Pendiente", "Aprobado", "Rechazado", "Reembolsado")

# Misma máquina de estados que el servicio de pedidos: este servicio no puede
# saltarse las transiciones que allí se validan.
TRANSICIONES_PEDIDO = {
    "Pendiente":  {"Confirmado", "Cancelado"},
    "Confirmado": {"Pagado", "Cancelado"},
    "Pagado":     {"Enviado", "Cancelado"},
    "Enviado":    {"Entregado"},
    "Entregado":  set(),
    "Cancelado":  set(),
}

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
        "title": "Microservicio de Pagos — Library",
        "description": (
            "Registro de pagos y actualización del estado de los pedidos.\n\n"
            "**Seguridad:** todas las operaciones exigen "
            "`Authorization: Bearer <JWT>`. Un usuario solo ve los pagos de sus "
            "propios pedidos; el rol Administrador ve todos. El token se "
            "comprueba contra la lista de revocación en Redis.\n\n"
            "**Atomicidad:** registrar el pago y marcar el pedido como `Pagado` "
            "ocurren en una sola transacción."
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
    """Convierte Decimal y fechas a tipos serializables por jsonify."""
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
        'Bearer realm="library-pagos", error="%s", error_description="%s"'
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
    """Error de negocio: provoca ROLLBACK y se traduce a una respuesta HTTP."""

    def __init__(self, code, message, status=400, extra=None):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra


# ==============================================================================
# 4. GUARDIÁN DE AUTORIZACIÓN
# ==============================================================================

@app.before_request
def enforce_auth():
    if request.method == "OPTIONS":
        return None

    path = request.path.rstrip("/") or "/"
    if path in PUBLIC_PATHS or path.startswith("/flasgger_static"):
        return None

    token = bearer_token()
    if not token:
        return unauthorized(
            "TOKEN_REQUIRED",
            "Los pagos son datos del usuario: se requiere autenticación.",
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
# 5. CONSULTAS
# ==============================================================================

PAYMENT_FIELDS = ("pg.id, pg.pedido_id, pg.monto, pg.metodo, pg.estado, "
                  "pg.referencia, pg.created_at")


def load_payment(payment_id, cur=None):
    sql = "SELECT " + PAYMENT_FIELDS + " FROM pagos pg WHERE pg.id = %s"
    if cur is not None:
        cur.execute(sql, (payment_id,))
        return cur.fetchone()
    return fetch_one(sql, (payment_id,))


def load_order(order_id, cur=None):
    sql = """SELECT p.id, p.user_id, p.estado, p.total, p.notas,
                    p.created_at, p.updated_at
               FROM pedidos p WHERE p.id = %s"""
    if cur is not None:
        cur.execute(sql, (order_id,))
        return cur.fetchone()
    return fetch_one(sql, (order_id,))


def assert_order_visible(order):
    if not is_admin() and order["user_id"] != current_user_id():
        raise BusinessError("FORBIDDEN_ORDER", "Este pedido pertenece a otro usuario.", 403)


# ==============================================================================
# 6. ENDPOINTS
# ==============================================================================

@app.route("/", methods=["GET"])
def index():
    """Información del servicio e hipermedia."""
    return ok({
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "description": "Registro de pagos y actualización del estado de los pedidos.",
        "auth": "Todas las operaciones exigen Authorization: Bearer <access_token>",
        "metodos_pago": list(METODOS_PAGO),
        "estados_pago": list(ESTADOS_PAGO),
        "_links": {
            "self":    {"href": "/",        "method": "GET"},
            "health":  {"href": "/health",  "method": "GET"},
            "pagos":   {"href": "/pagos",   "method": "GET"},
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
                cur.execute("""SELECT to_regclass('public.pagos')   IS NOT NULL AS pagos,
                                      to_regclass('public.pedidos') IS NOT NULL AS pedidos""")
                schema = cur.fetchone()
        ready = all(schema.values())
        return ok({
            "status": "healthy",
            "service": SERVICE_NAME,
            "database": "connected",
            "postgres_version": (row["version"] or "").split(" on ")[0],
            "schema": "ready" if ready else "migration_pending",
            "migration_hint": None if ready else (
                "Falta aplicar apps/services/pagos/sql/01_migration_pagos.sql "
                "(requiere que exista `pedidos`)."
            ),
            "server_time": row["server_time"].isoformat(),
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


@app.route("/pagos", methods=["GET"])
def list_pagos():
    """Lista pagos. El administrador ve todos; el usuario, solo los de sus pedidos.
    ---
    tags: [Pagos]
    parameters:
      - {name: pedido_id, in: query, type: integer, required: false}
      - {name: estado, in: query, type: string, required: false, enum: [Pendiente, Aprobado, Rechazado, Reembolsado]}
      - {name: limit, in: query, type: integer, required: false, default: 50}
      - {name: offset, in: query, type: integer, required: false, default: 0}
    responses:
      200: {description: Lista de pagos.}
      401: {description: Token ausente, inválido o revocado.}
    """
    where, params = [], []

    pedido_id = request.args.get("pedido_id")
    if pedido_id:
        where.append("pg.pedido_id = %s")
        params.append(int(pedido_id))

    estado = request.args.get("estado")
    if estado:
        if estado not in ESTADOS_PAGO:
            return fail("INVALID_ESTADO", "Estado de pago no válido: %s." % estado, 400)
        where.append("pg.estado = %s")
        params.append(estado)

    # Aislamiento: un usuario solo ve los pagos de pedidos suyos.
    if not is_admin():
        where.append("p.user_id = %s")
        params.append(current_user_id())

    limit = min(max(int(request.args.get("limit", 50)), 1), PAGE_SIZE_MAX)
    offset = max(int(request.args.get("offset", 0)), 0)

    sql = ("SELECT " + PAYMENT_FIELDS + ", p.estado AS pedido_estado, p.total AS pedido_total "
           "FROM pagos pg JOIN pedidos p ON p.id = pg.pedido_id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY pg.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = fetch_all(sql, tuple(params))
    return ok([dict(r) for r in rows], extra={"count": len(rows)})


@app.route("/pagos/<int:payment_id>", methods=["GET"])
def get_pago(payment_id):
    """Detalle de un pago. Solo el dueño del pedido o un administrador."""
    payment = load_payment(payment_id)
    if not payment:
        return fail("PAYMENT_NOT_FOUND", "No existe un pago con id %s." % payment_id, 404)

    order = load_order(payment["pedido_id"])
    if not order:
        return fail("ORDER_NOT_FOUND",
                    "El pago apunta a un pedido que ya no existe.", 404)
    if not is_admin() and order["user_id"] != current_user_id():
        return unauthorized("FORBIDDEN_PAYMENT", "Este pago pertenece a otro usuario.", 403)

    return ok(dict(payment, pedido_estado=order["estado"], pedido_total=order["total"]))


@app.route("/pedidos/<int:order_id>/pagos", methods=["GET"])
def payments_of_order(order_id):
    """Historial de pagos de un pedido (incluye intentos rechazados)."""
    order = load_order(order_id)
    if not order:
        return fail("ORDER_NOT_FOUND", "No existe un pedido con id %s." % order_id, 404)
    if not is_admin() and order["user_id"] != current_user_id():
        return unauthorized("FORBIDDEN_ORDER", "Este pedido pertenece a otro usuario.", 403)

    rows = fetch_all("SELECT " + PAYMENT_FIELDS + " FROM pagos pg "
                     "WHERE pg.pedido_id = %s ORDER BY pg.id DESC", (order_id,))
    return ok([dict(r) for r in rows],
              extra={"count": len(rows), "pedido_estado": order["estado"],
                     "pedido_total": jsonable(order["total"])})


@app.route("/pagos", methods=["POST"])
def create_pago():
    """Registra un pago y, si queda Aprobado, marca el pedido como Pagado.

    Las dos escrituras van en la MISMA transacción: o se cobra y el pedido queda
    pagado, o no pasa ninguna de las dos.
    ---
    tags: [Pagos]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [pedido_id, metodo]
          properties:
            pedido_id: {type: integer}
            monto: {type: number, description: "Si se omite, se usa el total del pedido"}
            metodo: {type: string, enum: [Tarjeta, Transferencia, Efectivo, PayPal]}
            estado: {type: string, enum: [Pendiente, Aprobado, Rechazado], default: Aprobado}
            referencia: {type: string, description: "Folio o número de autorización"}
    responses:
      201: {description: Pago registrado.}
      409: {description: El pedido no admite pago en su estado actual.}
    """
    body = request.get_json(silent=True) or {}
    pedido_id = body.get("pedido_id")
    metodo = (body.get("metodo") or "").strip()
    estado = (body.get("estado") or "Aprobado").strip()

    if not pedido_id:
        return fail("VALIDATION_ERROR", "El campo 'pedido_id' es obligatorio.", 400)
    if metodo not in METODOS_PAGO:
        return fail("INVALID_METHOD",
                    "Método de pago no válido: '%s'. Válidos: %s." % (metodo, ", ".join(METODOS_PAGO)), 400)
    if estado not in ESTADOS_PAGO:
        return fail("INVALID_ESTADO",
                    "Estado de pago no válido: '%s'. Válidos: %s." % (estado, ", ".join(ESTADOS_PAGO)), 400)

    try:
        with get_db_connection() as conn:      # <- transacción: commit o ROLLBACK
            with conn.cursor() as cur:
                order = load_order(pedido_id, cur)
                if not order:
                    raise BusinessError("ORDER_NOT_FOUND",
                                        "No existe un pedido con id %s." % pedido_id, 404)
                assert_order_visible(order)

                # No se puede cobrar lo que ya está cancelado ni lo que ya se pagó.
                if order["estado"] in ("Cancelado", "Pagado", "Enviado", "Entregado"):
                    raise BusinessError(
                        "ORDER_NOT_PAYABLE",
                        "Un pedido en estado '%s' no admite un pago nuevo." % order["estado"], 409)

                # El monto, si no viene, es el total del pedido.
                monto = body.get("monto")
                monto = Decimal(str(monto)) if monto not in (None, "") else order["total"]
                if monto is None or monto <= 0:
                    raise BusinessError("INVALID_AMOUNT",
                                        "El monto debe ser mayor que cero.", 400)

                cur.execute("""INSERT INTO pagos (pedido_id, monto, metodo, estado, referencia)
                               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                            (pedido_id, monto, metodo, estado,
                             (body.get("referencia") or "").strip() or None))
                payment_id = cur.fetchone()["id"]

                # --- Actualización del estado del pedido, en la misma transacción ---
                pedido_actualizado = None
                if estado == "Aprobado":
                    actual = order["estado"]
                    # Si el pedido está 'Pendiente' se confirma primero: así el
                    # usuario no tiene que hacer dos llamadas para pagar.
                    if actual == "Pendiente":
                        cur.execute("""UPDATE pedidos SET estado='Confirmado',
                                                           updated_at=CURRENT_TIMESTAMP
                                        WHERE id=%s""", (pedido_id,))
                        actual = "Confirmado"
                    if "Pagado" in TRANSICIONES_PEDIDO.get(actual, set()):
                        cur.execute("""UPDATE pedidos SET estado='Pagado',
                                                           updated_at=CURRENT_TIMESTAMP
                                        WHERE id=%s""", (pedido_id,))
                        pedido_actualizado = "Pagado"
                    else:
                        raise BusinessError(
                            "INVALID_TRANSITION",
                            "No se puede marcar como 'Pagado' un pedido en estado '%s'." % actual, 409)

                payment = load_payment(payment_id, cur)
                final_order = load_order(pedido_id, cur)
    except BusinessError as exc:
        return fail(exc.code, exc.message, exc.status, extra=exc.extra)

    return ok(dict(payment, pedido_estado=final_order["estado"],
                   pedido_actualizado_a=pedido_actualizado),
              message="Pago registrado.", status=201)


@app.route("/pagos/<int:payment_id>/estado", methods=["PATCH"])
def change_payment_state(payment_id):
    """Cambia el estado de un pago. Exige rol Administrador.

    Reembolsar aquí solo marca el pago; NO revierte el pedido a 'Confirmado'.
    Un reembolso no implica automáticamente devolver la mercancía, así que esa
    decisión se toma aparte con el endpoint de estado del servicio de pedidos.
    """
    body = request.get_json(silent=True) or {}
    nuevo = (body.get("estado") or "").strip()
    if nuevo not in ESTADOS_PAGO:
        return fail("INVALID_ESTADO",
                    "Estado de pago no válido: '%s'. Válidos: %s." % (nuevo, ", ".join(ESTADOS_PAGO)), 400)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                payment = load_payment(payment_id, cur)
                if not payment:
                    raise BusinessError("PAYMENT_NOT_FOUND",
                                        "No existe un pago con id %s." % payment_id, 404)
                if payment["estado"] == nuevo:
                    raise BusinessError("SAME_ESTADO",
                                        "El pago ya está en '%s'." % nuevo, 409)

                cur.execute("UPDATE pagos SET estado = %s WHERE id = %s", (nuevo, payment_id))
                payment = load_payment(payment_id, cur)
    except BusinessError as exc:
        return fail(exc.code, exc.message, exc.status, extra=exc.extra)

    return ok(dict(payment), message="Estado del pago actualizado a '%s'." % nuevo)


# ==============================================================================
# 7. ARRANQUE
# ==============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5005"))
    print("%s escuchando en http://0.0.0.0:%d  (docs en /docs)" % (SERVICE_NAME, port))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "False").lower() == "true")

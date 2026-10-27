"""
==============================================================================
PROYECTO: INTEGRACION03 - MICROSERVICIO DE USUARIOS
TECNOLOGIAS: Python 3, Flask, Psycopg v3, PostgreSQL, Flasgger (OpenAPI), bcrypt
AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
PUERTO: 5002

QUE ADMINISTRA
--------------
Usuarios, roles, correos y contraseñas. Es el servicio que completa lo que el
microservicio de login solo puede hacer a medias: allí el usuario se registra y
se autentica, aquí se administra (crear cuentas, cambiar roles, activar y
desactivar, corregir correos y resetear contraseñas).

DECISIONES DE DISEÑO
--------------------
1. AUTORIZACION POR METODO + POR RUTA, no por endpoint suelto.
   - Las lecturas de catálogo serían públicas, pero aquí NO hay catálogo: todo
     lo que devuelve este servicio son datos personales. Por eso la regla es:
        * `GET /health` y `/docs`  -> públicos
        * todo lo demás            -> exige JWT
   - Además, las LECTURAS ADMINISTRATIVAS (listar usuarios, listar roles) exigen
     rol Administrador, como pide el enunciado. Un usuario normal solo puede
     leer SU propio registro.
   - La decisión vive en un único `before_request`, así que cualquier ruta nueva
     queda protegida por defecto. Proteger por omisión es lo correcto: si se
     olvida una ruta, el fallo es "deniega", no "expone".

2. REVOCACION EN REDIS (jwt:revoked:<jti>).
   El access token es sin estado, así que este servicio no sabe si el usuario
   cerró sesión. Consulta la lista de revocación compartida ANTES de aceptar.
   Si Redis no responde, la petición se rechaza con 503 (fail-closed): no se
   puede demostrar que el token sigue vivo, así que no se autoriza.

3. LA CONTRASEÑA NUNCA SALE NI SE LOGUEA.
   Se guarda solo el hash bcrypt y `password_hash` no aparece en ninguna
   respuesta ni en ningún mensaje de error.

4. `role` (texto) y `role_id` (catálogo) SE MANTIENEN SINCRONIZADOS.
   `role_id` es la referencia normalizada que viaja en el JWT; `role` se
   conserva porque el monolito y el login ya lo usan. Al escribir, el texto se
   deriva del catálogo, nunca se acepta del cliente.

5. RESPUESTAS SOLO EN JSON.
   El XML de los otros servicios respondía al requerimiento SOAP del catálogo,
   que no aplica aquí. Mantener un solo formato reduce superficie de error.

SEGURIDAD
---------
   * JWT verificado con el MISMO secreto compartido (JWT_SECRET), algoritmo
     fijado en el servidor (HS256) y validación de exp/nbf/iat/iss/aud/sub.
   * 401 para token ausente o inválido; 403 para rol insuficiente; 503 si Redis
     no permite comprobar la revocación.
   * CORS restringido por variable de entorno a los orígenes de las aplicaciones
     cliente (nunca "*").
==============================================================================
"""

import os
import re
import sys
from datetime import datetime, timezone

import bcrypt
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, ForeignKeyViolation
from dotenv import load_dotenv
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flasgger import Swagger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt_auth    # noqa: E402  (verificador propio, copia deliberada)
import redis_layer  # noqa: E402  (capa compartida: revocación de JWT)

# ==============================================================================
# 1. CONFIGURACIÓN
# ==============================================================================

load_dotenv()

SERVICE_NAME = "users-microservice"
APP_VERSION = "1.0.0"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "library_user"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "library"),
}

# --- JWT: SOLO verificación. Este servicio nunca emite tokens. ----------------
JWT_SECRET         = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM      = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER         = os.getenv("JWT_ISSUER", "library-login")
JWT_AUDIENCE       = os.getenv("JWT_AUDIENCE", "library-api")
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", "5"))
LOGIN_BASE_URL     = os.getenv("LOGIN_BASE_URL", "http://localhost:5000").rstrip("/")

# --- Roles -------------------------------------------------------------------
# El id del catálogo `roles` que se considera administrador. Se usa el ID y no
# el texto a propósito: renombrar el rol en la base no debe romper la
# autorización.
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "1"))

# --- CORS --------------------------------------------------------------------
# Lista explícita de orígenes de las aplicaciones cliente. NUNCA "*": el
# enunciado pide limitarlo a los orígenes de producción.
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"      # monolito web en local
    "http://34.51.29.27:3000"                            # monolito en la VM
)
CORS_ORIGINS = [o.strip() for o in
                os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()]

BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))
PAGE_SIZE_MAX = int(os.getenv("PAGE_SIZE_MAX", "100"))

if not JWT_SECRET:
    print("[AVISO] JWT_SECRET no está definido: TODA petición responderá 401.")
    print("        Debe coincidir EXACTAMENTE con el de los demás microservicios.")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Rutas que NO exigen token. Todo lo que no esté aquí queda protegido.
PUBLIC_PATHS = {"/", "/health", "/docs", "/apispec.json", "/flasgger_static"}

# Lecturas que, siendo GET, son administrativas y exigen rol Administrador.
ADMIN_ONLY_PATHS = {"/users", "/roles"}

# Métodos que no modifican estado.
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

app = Flask(__name__)
app.json.sort_keys = False
CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}}, expose_headers=["WWW-Authenticate"])

# ==============================================================================
# 2. SWAGGER
# ==============================================================================

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
        "title": "Microservicio de Usuarios — Library",
        "description": (
            "Administración de usuarios, roles, correos y contraseñas.\n\n"
            "**Seguridad:** todas las operaciones exigen `Authorization: Bearer <JWT>` "
            "emitido por el microservicio de login (HS256, 20 min). Las lecturas "
            "administrativas y todas las escrituras exigen además rol Administrador. "
            "El token se comprueba contra la lista de revocación en Redis."
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
# 3. BASE DE DATOS
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
    """Ejecuta una escritura y devuelve las filas afectadas."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


# ==============================================================================
# 4. RESPUESTAS Y ERRORES
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
    """Error uniforme. `code` es estable y legible por máquina."""
    payload = {"status": "error", "code": code, "error": message, "status_code": status}
    if hint:
        payload["hint"] = hint
    return jsonify(payload), status


def unauthorized(code, message, status=401):
    """401/403 con WWW-Authenticate y la pista de dónde conseguir un token.

    OJO: `fail()` devuelve una TUPLA (respuesta, código). Al desenvolverla hay
    que volver a fijar `resp.status_code`, porque el código viajaba en el
    segundo elemento de la tupla y si no se devolvía 200 en lugar de 401.
    """
    resp, _ = fail(code, message, status,
                   hint="Envía 'Authorization: Bearer <access_token>'.")
    resp.status_code = status
    resp.headers["WWW-Authenticate"] = (
        'Bearer realm="library-users", error="%s", error_description="%s"'
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
# 5. GUARDIÁN DE AUTORIZACIÓN
# ==============================================================================

@app.before_request
def enforce_auth():
    """Protege TODO por omisión y exige rol Administrador donde corresponde.

    Se decide por método y por ruta, igual que en el servicio de libros: así una
    ruta nueva queda protegida sin que nadie tenga que acordarse de añadirla.
    """
    if request.method == "OPTIONS":
        return None

    path = request.path.rstrip("/") or "/"
    if path in PUBLIC_PATHS or path.startswith("/flasgger_static"):
        return None

    # --- 1. Token presente y válido ------------------------------------------
    token = bearer_token()
    if not token:
        return unauthorized(
            "TOKEN_REQUIRED",
            "Este servicio administra datos personales: exige autenticación. "
            "Falta el encabezado 'Authorization: Bearer <access_token>'.",
        )

    try:
        claims = jwt_auth.decode_jwt(
            token, JWT_SECRET, algorithms=(JWT_ALGORITHM,),
            issuer=JWT_ISSUER, audience=JWT_AUDIENCE, leeway=JWT_LEEWAY_SECONDS,
        )
    except jwt_auth.JWTError as exc:
        return unauthorized(exc.code, exc.message, exc.status)

    # --- 2. Revocación compartida (fail-closed) ------------------------------
    try:
        if redis_layer.is_revoked(claims.get("jti")):
            return unauthorized(
                "TOKEN_REVOKED",
                "El token fue revocado (sesión cerrada). Inicia sesión de nuevo.",
            )
    except redis_layer.RedisUnavailable as exc:
        resp, _ = fail(exc.code, str(exc), exc.status)
        resp.status_code = exc.status   # `fail` devuelve tupla: hay que reponerlo
        resp.headers["Retry-After"] = "5"
        return resp

    g.claims = claims

    # --- 3. Rol suficiente ----------------------------------------------------
    # Escritura (cualquier método no seguro) o lectura administrativa.
    needs_admin = (request.method not in SAFE_METHODS) or (path in ADMIN_ONLY_PATHS)
    if needs_admin and claims.get("role_id") != ADMIN_ROLE_ID:
        return unauthorized(
            "FORBIDDEN_ROLE",
            "Esta operación exige rol Administrador.",
            403,
        )
    return None


def current_user_id():
    """`user_id` del token (el claim `sub`). Es el `user_id` que pide el enunciado."""
    return int(g.claims["sub"]) if g.get("claims") else None


def is_admin():
    return g.get("claims", {}).get("role_id") == ADMIN_ROLE_ID


def can_touch_user(user_id):
    """Un administrador toca a cualquiera; un usuario, solo a sí mismo."""
    return is_admin() or current_user_id() == int(user_id)


# ==============================================================================
# 6. CONTRASEÑAS
# ==============================================================================

def hash_password(plain):
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def validate_password(password):
    """Misma política que el servicio de login, para no aceptar aquí lo que allí se rechaza."""
    if not password or len(password) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return "La contraseña debe incluir al menos una letra mayúscula."
    if not re.search(r"[a-z]", password):
        return "La contraseña debe incluir al menos una letra minúscula."
    if not re.search(r"\d", password):
        return "La contraseña debe incluir al menos un dígito."
    if not re.search(r"[^A-Za-z0-9]", password):
        return "La contraseña debe incluir al menos un símbolo."
    return None


# ==============================================================================
# 7. SERIALIZACIÓN (nunca expone password_hash)
# ==============================================================================

USER_FIELDS = ("u.id, u.username, u.nombre, u.apellido_paterno, u.apellido_materno, "
               "u.email, u.role, u.role_id, u.is_active, u.created_at, u.last_login")


def serialize_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "nombre": row["nombre"],
        "apellido_paterno": row["apellido_paterno"],
        "apellido_materno": row["apellido_materno"],
        "email": row["email"],
        "role": row["role"],
        "role_id": row["role_id"],
        "is_active": row["is_active"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "last_login": row["last_login"].isoformat() if row["last_login"] else None,
    }


def role_name(role_id):
    row = fetch_one("SELECT name FROM roles WHERE id = %s", (role_id,))
    return row["name"] if row else None


# ==============================================================================
# 8. ENDPOINTS
# ==============================================================================

@app.route("/", methods=["GET"])
def index():
    """Información del servicio e hipermedia (Nivel 3 de Richardson)."""
    return ok({
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "description": "Administración de usuarios, roles, correos y contraseñas.",
        "auth": "Authorization: Bearer <access_token> (JWT HS256, 20 min)",
        "roles": {"Administrador": ADMIN_ROLE_ID},
        "_links": {
            "self":    {"href": "/",        "method": "GET"},
            "health":  {"href": "/health",  "method": "GET"},
            "users":   {"href": "/users",   "method": "GET"},
            "roles":   {"href": "/roles",   "method": "GET"},
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
                cur.execute("""SELECT to_regclass('public.roles')      IS NOT NULL AS roles,
                                      to_regclass('public.user_sessions') IS NOT NULL AS sessions,
                                      EXISTS (SELECT 1 FROM information_schema.columns
                                               WHERE table_name='users'
                                                 AND column_name='role_id')      AS role_id""")
                schema = cur.fetchone()
        ready = all(schema.values())
        return ok({
            "status": "healthy",
            "service": SERVICE_NAME,
            "database": "connected",
            "postgres_version": (row["version"] or "").split(" on ")[0],
            "schema": "ready" if ready else "migration_pending",
            "migration_hint": None if ready else (
                "Falta aplicar apps/services/login/sql/04_migration_roles.sql "
                "(crea `roles` y `users.role_id`)."
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


@app.route("/roles", methods=["GET"])
def list_roles():
    """Catálogo de roles. Lectura administrativa: exige rol Administrador."""
    rows = fetch_all("SELECT id, name, description FROM roles ORDER BY id")
    return ok([dict(r) for r in rows], extra={"count": len(rows)})


@app.route("/users", methods=["GET"])
def list_users():
    """Lista usuarios con filtros y paginación. Lectura administrativa.

    Nunca devuelve `password_hash`.
    ---
    tags: [Users]
    parameters:
      - {name: role_id, in: query, type: integer, required: false}
      - {name: is_active, in: query, type: boolean, required: false}
      - {name: email, in: query, type: string, required: false, description: "Coincidencia parcial"}
      - {name: limit, in: query, type: integer, required: false, default: 50}
      - {name: offset, in: query, type: integer, required: false, default: 0}
    responses:
      200: {description: Lista de usuarios.}
      401: {description: Token ausente o inválido.}
      403: {description: Rol insuficiente.}
    """
    where, params = [], []

    role_id = request.args.get("role_id")
    if role_id:
        where.append("u.role_id = %s")
        params.append(int(role_id))

    is_active = request.args.get("is_active")
    if is_active is not None and is_active != "":
        where.append("u.is_active = %s")
        params.append(is_active.lower() in ("true", "1", "yes"))

    email = request.args.get("email")
    if email:
        where.append("u.email ILIKE %s")
        params.append("%" + email.strip() + "%")

    sql = "SELECT " + USER_FIELDS + " FROM users u"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY u.id ASC LIMIT %s OFFSET %s"

    limit = min(max(int(request.args.get("limit", 50)), 1), PAGE_SIZE_MAX)
    offset = max(int(request.args.get("offset", 0)), 0)
    params.extend([limit, offset])

    rows = fetch_all(sql, tuple(params))
    return ok([serialize_user(r) for r in rows], extra={"count": len(rows)})


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Detalle de un usuario. Un usuario normal solo puede leer su propio registro."""
    if not can_touch_user(user_id):
        return unauthorized("FORBIDDEN_ROLE",
                            "Solo puedes consultar tu propio usuario.", 403)
    row = fetch_one("SELECT " + USER_FIELDS + " FROM users u WHERE u.id = %s", (user_id,))
    if not row:
        return fail("USER_NOT_FOUND", "No existe un usuario con id %s." % user_id, 404)
    return ok(serialize_user(row))


@app.route("/users", methods=["POST"])
def create_user():
    """Crea un usuario. Exige rol Administrador.
    ---
    tags: [Users]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [email, password]
          properties:
            nombre: {type: string}
            apellido_paterno: {type: string}
            apellido_materno: {type: string}
            email: {type: string}
            password: {type: string, description: "Solo en la petición; nunca se devuelve."}
            role_id: {type: integer, default: 2}
            is_active: {type: boolean, default: true}
    responses:
      201: {description: Usuario creado.}
      400: {description: Validación.}
      409: {description: El correo ya existe.}
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role_id = body.get("role_id", 2)

    if not email or not EMAIL_RE.match(email):
        return fail("INVALID_EMAIL", "El correo electrónico no es válido.", 400)

    policy_error = validate_password(password)
    if policy_error:
        return fail("WEAK_PASSWORD", policy_error, 400)

    name = role_name(role_id)
    if not name:
        return fail("INVALID_ROLE", "No existe el rol con id %s." % role_id, 400)

    try:
        row = fetch_one(
            """INSERT INTO users (nombre, apellido_paterno, apellido_materno, email,
                                  password_hash, role, role_id, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            ((body.get("nombre") or "").strip() or None,
             (body.get("apellido_paterno") or "").strip() or None,
             (body.get("apellido_materno") or "").strip() or None,
             email, hash_password(password), name, role_id,
             bool(body.get("is_active", True))),
        )
    except UniqueViolation:
        return fail("EMAIL_ALREADY_EXISTS", "El correo ya está registrado.", 409)
    except ForeignKeyViolation:
        return fail("INVALID_ROLE", "El rol indicado no existe.", 400)

    created = fetch_one("SELECT " + USER_FIELDS + " FROM users u WHERE u.id = %s", (row["id"],))
    return ok(serialize_user(created), message="Usuario creado.", status=201)


@app.route("/users/<int:user_id>", methods=["PUT"])
def replace_user(user_id):
    """Reemplazo COMPLETO: si falta un campo editable, responde 400.

    La misma semántica que el servicio de libros, para que un PUT signifique lo
    mismo en todo el sistema.
    """
    body = request.get_json(silent=True) or {}
    required = ["nombre", "apellido_paterno", "apellido_materno", "email", "role_id", "is_active"]
    missing = [f for f in required if f not in body]
    if missing:
        return fail("VALIDATION_ERROR",
                    "PUT reemplaza el recurso completo. Faltan: %s." % ", ".join(missing), 400)

    email = (body.get("email") or "").strip().lower()
    if not email or not EMAIL_RE.match(email):
        return fail("INVALID_EMAIL", "El correo electrónico no es válido.", 400)

    name = role_name(body.get("role_id"))
    if not name:
        return fail("INVALID_ROLE", "No existe el rol con id %s." % body.get("role_id"), 400)

    try:
        updated = execute(
            """UPDATE users SET nombre=%s, apellido_paterno=%s, apellido_materno=%s,
                                email=%s, role=%s, role_id=%s, is_active=%s
                WHERE id=%s""",
            ((body.get("nombre") or "").strip() or None,
             (body.get("apellido_paterno") or "").strip() or None,
             (body.get("apellido_materno") or "").strip() or None,
             email, name, body.get("role_id"), bool(body.get("is_active")), user_id),
        )
    except UniqueViolation:
        return fail("EMAIL_ALREADY_EXISTS", "El correo ya pertenece a otro usuario.", 409)

    if not updated:
        return fail("USER_NOT_FOUND", "No existe un usuario con id %s." % user_id, 404)

    row = fetch_one("SELECT " + USER_FIELDS + " FROM users u WHERE u.id = %s", (user_id,))
    return ok(serialize_user(row), message="Usuario reemplazado.")


@app.route("/users/<int:user_id>", methods=["PATCH"])
def patch_user(user_id):
    """Modificación PARCIAL: solo cambia los campos presentes.

    `password` se trata aparte porque no es un campo de la tabla, sino una
    operación (volver a hashear). Se acepta aquí para poder resetear desde el
    mismo endpoint, pero se hashea antes de tocar la base.
    """
    body = request.get_json(silent=True) or {}
    if not body:
        return fail("VALIDATION_ERROR", "No se envió ningún campo para modificar.", 400)

    sets, params = [], []

    for field, column in (("nombre", "nombre"),
                          ("apellido_paterno", "apellido_paterno"),
                          ("apellido_materno", "apellido_materno")):
        if field in body:
            sets.append("%s = %%s" % column)
            params.append((body.get(field) or "").strip() or None)

    if "email" in body:
        email = (body.get("email") or "").strip().lower()
        if not email or not EMAIL_RE.match(email):
            return fail("INVALID_EMAIL", "El correo electrónico no es válido.", 400)
        sets.append("email = %s")
        params.append(email)

    if "role_id" in body:
        name = role_name(body.get("role_id"))
        if not name:
            return fail("INVALID_ROLE", "No existe el rol con id %s." % body.get("role_id"), 400)
        # El texto del rol se deriva del catálogo: nunca se acepta del cliente.
        sets.append("role = %s")
        params.append(name)
        sets.append("role_id = %s")
        params.append(body.get("role_id"))

    if "is_active" in body:
        sets.append("is_active = %s")
        params.append(bool(body.get("is_active")))

    if "password" in body:
        policy_error = validate_password(body.get("password") or "")
        if policy_error:
            return fail("WEAK_PASSWORD", policy_error, 400)
        sets.append("password_hash = %s")
        params.append(hash_password(body["password"]))

    if not sets:
        return fail("VALIDATION_ERROR", "Ninguno de los campos enviados es modificable.", 400)

    params.append(user_id)
    try:
        updated = execute("UPDATE users SET " + ", ".join(sets) + " WHERE id = %s", tuple(params))
    except UniqueViolation:
        return fail("EMAIL_ALREADY_EXISTS", "El correo ya pertenece a otro usuario.", 409)

    if not updated:
        return fail("USER_NOT_FOUND", "No existe un usuario con id %s." % user_id, 404)

    row = fetch_one("SELECT " + USER_FIELDS + " FROM users u WHERE u.id = %s", (user_id,))
    return ok(serialize_user(row), message="Usuario actualizado.")


@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Elimina un usuario. Exige rol Administrador.

    Un administrador no puede borrarse a sí mismo: dejaría el sistema sin acceso
    administrativo si es el único. Para eso está desactivar la cuenta.
    """
    if user_id == current_user_id():
        return fail("CANNOT_DELETE_SELF",
                    "No puedes eliminar tu propia cuenta. Desactívala con PATCH is_active=false.", 400)

    try:
        deleted = execute("DELETE FROM users WHERE id = %s", (user_id,))
    except ForeignKeyViolation:
        # El usuario tiene sesiones o pedidos: se conserva la integridad.
        return fail("USER_IN_USE",
                    "El usuario tiene registros asociados (sesiones o pedidos). "
                    "Desactívalo con PATCH is_active=false en lugar de borrarlo.", 409)

    if not deleted:
        return fail("USER_NOT_FOUND", "No existe un usuario con id %s." % user_id, 404)
    return ok({"id": user_id}, message="Usuario eliminado.")


# ==============================================================================
# 9. ARRANQUE
# ==============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5002"))
    print("%s escuchando en http://0.0.0.0:%d  (docs en /docs)" % (SERVICE_NAME, port))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "False").lower() == "true")

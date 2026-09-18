"""
==============================================================================
PROYECTO: INTEGRACION03 - MICROSERVICIO DE AUTENTICACIÓN Y GESTIÓN DE USUARIOS
TECNOLOGÍAS: Python 3, Flask, Psycopg v3, PostgreSQL, Flasgger (OpenAPI), bcrypt
AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
PUERTO: 5000

DISEÑO:
  - Sesión del lado de Flask SIN cookies -> token opaco en el header X-Session-Token.
  - Salida dual: XML por defecto, JSON con ?format=json o Accept: application/json.
  - Nivel 3 del Modelo de Madurez de Richardson: hipermedia (_links / <links>).
  - CAPTCHA sin GUI: desafío aritmético firmado con HMAC (stateless).
  - Contraseñas: solo hash bcrypt en users.password_hash.
==============================================================================
"""

import os
import re
import json
import time
import hmac
import base64
import hashlib
import secrets
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

import bcrypt
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation
from dotenv import load_dotenv
from flask import Flask, request, Response
from flask_cors import CORS
from flasgger import Swagger

# ==============================================================================
# 1. CONFIGURACIÓN
# ==============================================================================

load_dotenv()

SERVICE_NAME = "login-microservice"
APP_VERSION = "1.0.0"

SESSION_MINUTES     = int(os.getenv("SESSION_MINUTES", "30"))
CAPTCHA_TTL_SECONDS = int(os.getenv("CAPTCHA_TTL_SECONDS", "300"))
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_MINUTES     = int(os.getenv("LOCKOUT_MINUTES", "15"))
BCRYPT_ROUNDS       = int(os.getenv("BCRYPT_ROUNDS", "12"))
RATE_LIMIT_MAX      = int(os.getenv("RATE_LIMIT_MAX", "20"))
RATE_LIMIT_WINDOW   = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

SECRET_KEY     = os.getenv("SECRET_KEY", "dev-secret-cambia-esto")
SESSION_HEADER = "X-Session-Token"

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=SESSION_MINUTES)
app.json.sort_keys = False

# CORS: al no usar cookies no hay credenciales de navegador que proteger.
CORS(app, resources={r"/*": {"origins": "*"}})

# ==============================================================================
# 2. SWAGGER / OPENAPI
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
        "title": "Authentication & User Management Microservice API",
        "description": (
            "Microservicio independiente de autenticación y gestión básica de usuarios para la "
            "plataforma de librería. Sesión del lado de Flask sin cookies, respuestas en XML "
            "(predeterminado) y JSON, e hipermedia de Nivel 3 (HATEOAS)."
        ),
        "version": APP_VERSION,
        "contact": {
            "name": "Fabián Azaed Orta Singlaterry",
            "email": "azaedorta@hotmail.com",
            "institution": "Universidad de Monterrey (UDEM)",
        },
    },
    "tags": [
        {"name": "Auth",     "description": "Registro, inicio y cierre de sesión"},
        {"name": "Session",  "description": "Consulta de la sesión autenticada"},
        {"name": "Users",    "description": "Recursos de usuario"},
        {"name": "System",   "description": "Estado del servicio y CAPTCHA"},
    ],
    "schemes": ["http", "https"],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# ==============================================================================
# 3. SERIALIZACIÓN DUAL (XML / JSON) Y NEGOCIACIÓN DE CONTENIDO
# ==============================================================================

def wants_json():
    """
    Decide el formato de salida.
    Prioridad: ?format= > Accept: application/json > XML (predeterminado).
    Un 'Accept: */*' (valor por defecto de Postman y curl) NO cambia el formato.
    """
    fmt = request.args.get("format")
    if fmt:
        return fmt.strip().lower() in ("json", "application/json")
    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept


def _xml_node(parent, key, value):
    """Convierte recursivamente un valor Python en elementos XML."""
    if isinstance(value, dict):
        node = ET.SubElement(parent, key)
        for k, v in value.items():
            _xml_node(node, k, v)
    elif isinstance(value, list):
        for item in value:
            _xml_node(parent, key, item)
    else:
        node = ET.SubElement(parent, key)
        node.text = "" if value is None else str(value)


def build_xml(payload):
    """Serializa el sobre de respuesta a XML, incluyendo el bloque de hipermedia."""
    root = ET.Element("response")
    for key, value in payload.items():
        if key == "_links":
            links_el = ET.SubElement(root, "links")
            for rel, spec in value.items():
                attrib = {"rel": rel}
                if isinstance(spec, dict):
                    if spec.get("href"):
                        attrib["href"] = str(spec["href"])
                    if spec.get("method"):
                        attrib["method"] = str(spec["method"])
                else:
                    attrib["href"] = str(spec)
                ET.SubElement(links_el, "link", attrib=attrib)
        else:
            _xml_node(root, key, value)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def respond(payload, http_code=200, extra_headers=None):
    """Devuelve el sobre de respuesta en XML o JSON según la negociación."""
    headers = dict(extra_headers or {})
    if wants_json():
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        response = Response(body, status=http_code, mimetype="application/json")
    else:
        body = build_xml(payload)
        response = Response(body, status=http_code, mimetype="application/xml")
    for k, v in headers.items():
        response.headers[k] = v
    return response


def ok(message=None, data=None, links=None, http_code=200, extra_headers=None):
    payload = {"status": "success"}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if links:
        payload["_links"] = links
    return respond(payload, http_code, extra_headers)


def fail(code, message, http_code=400, links=None):
    payload = {"status": "error", "error": {"code": code, "message": message}}
    if links:
        payload["_links"] = links
    return respond(payload, http_code)


# ==============================================================================
# 4. HIPERMEDIA (HATEOAS - Nivel 3 de Richardson)
# ==============================================================================

def link(href, method="GET"):
    return {"href": href, "method": method}


ROOT_LINKS = {
    "register": link("/register", "POST"),
    "login":    link("/login", "POST"),
    "logout":   link("/logout", "POST"),
    "session":  link("/session"),
    "health":   link("/health"),
    "captcha":  link("/captcha"),
    "docs":     link("/docs"),
}


def auth_links(user_id):
    """Enlaces disponibles para un usuario ya autenticado."""
    return {
        "self":    link("/session"),
        "logout":  link("/logout", "POST"),
        "user":    link("/users/%s" % user_id),
        "captcha": link("/captcha"),
    }


ANON_LINKS = {
    "login":    link("/login", "POST"),
    "register": link("/register", "POST"),
    "captcha":  link("/captcha"),
}


# ==============================================================================
# 5. ACCESO A DATOS (Psycopg v3)
# ==============================================================================

def get_db_connection():
    """Conexión a PostgreSQL con mapeo directo a diccionarios."""
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "library_user"),
        password=os.getenv("DB_PASSWORD", "666"),
        dbname=os.getenv("DB_NAME", "library"),
        row_factory=dict_row,
    )


def fetch_one(sql, params=()):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def execute(sql, params=()):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


PUBLIC_USER_FIELDS = (
    "id, nombre, apellido_paterno, apellido_materno, email, role, is_active, created_at, last_login"
)


def public_user(row):
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "apellido_paterno": row["apellido_paterno"],
        "apellido_materno": row["apellido_materno"],
        "email": row["email"],
        "role": row["role"],
    }


def audit(endpoint, fmt, ip):
    """Registra métricas de uso reutilizando la tabla existente clientes_servidos."""
    tipo = "Auth API %s" % ("JSON" if fmt == "JSON" else "XML")
    try:
        updated = execute(
            """UPDATE clientes_servidos
                  SET peticiones_servidas = peticiones_servidas + 1,
                      ultima_peticion = CURRENT_TIMESTAMP
                WHERE tipo_cliente = %s AND endpoint_consultado = %s AND ip_origen = %s""",
            (tipo, endpoint, ip),
        )
        if not updated:
            execute(
                """INSERT INTO clientes_servidos
                       (tipo_cliente, endpoint_consultado, formato_solicitado, peticiones_servidas, ip_origen)
                   VALUES (%s, %s, %s, 1, %s)""",
                (tipo, endpoint, fmt, ip),
            )
    except Exception:
        pass  # la auditoría nunca debe tumbar la petición del usuario


def client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


# ==============================================================================
# 6. RATE LIMITING (en memoria)
# ==============================================================================

_rate_hits = defaultdict(deque)
_rate_lock = threading.Lock()


def rate_limited(bucket):
    """
    Ventana deslizante simple por IP + endpoint.
    NOTA: en producción se reemplaza por Redis o un API Gateway.
    """
    key = "%s|%s" % (client_ip(), bucket)
    now = time.time()
    with _rate_lock:
        hits = _rate_hits[key]
        while hits and now - hits[0] > RATE_LIMIT_WINDOW:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_MAX:
            return True
        hits.append(now)
    return False


# ==============================================================================
# 7. CAPTCHA SIN GUI (desafío aritmético firmado con HMAC, stateless)
# ==============================================================================

_used_captchas = {}
_captcha_lock = threading.Lock()


def _sign(encoded_payload):
    return hmac.new(SECRET_KEY.encode(), encoded_payload.encode(), hashlib.sha256).hexdigest()[:32]


def generate_captcha():
    """Genera un desafío aritmético cuya respuesta viaja firmada, no almacenada."""
    a = secrets.randbelow(9) + 1
    b = secrets.randbelow(9) + 1
    op = secrets.choice(["+", "-"])
    if op == "-" and b > a:
        a, b = b, a

    payload = {
        "a": a, "b": b, "op": op,
        "exp": int(time.time()) + CAPTCHA_TTL_SECONDS,
        "n": secrets.token_hex(8),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    encoded = base64.urlsafe_b64encode(raw.encode()).decode()
    captcha_id = "%s.%s" % (encoded, _sign(encoded))
    return captcha_id, "¿Cuánto es %d %s %d?" % (a, op, b)


def verify_captcha(captcha_id, answer):
    """Verifica firma, vigencia, un solo uso y respuesta correcta."""
    if not captcha_id or answer in (None, ""):
        return False, "INVALID_CAPTCHA", "El desafío CAPTCHA es obligatorio."

    try:
        encoded, signature = captcha_id.split(".", 1)
    except ValueError:
        return False, "INVALID_CAPTCHA", "El desafío CAPTCHA está mal formado."

    # Firma HMAC: impide que el cliente fabrique su propio desafío
    if not hmac.compare_digest(_sign(encoded), signature):
        return False, "INVALID_CAPTCHA", "La firma del desafío CAPTCHA no es válida."

    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode()).decode())
    except Exception:
        return False, "INVALID_CAPTCHA", "El desafío CAPTCHA está corrupto."

    if int(time.time()) > int(payload.get("exp", 0)):
        return False, "CAPTCHA_EXPIRED", "El desafío CAPTCHA expiró. Solicita uno nuevo."

    # Un solo uso: evita el replay del mismo desafío
    nonce = payload.get("n")
    now = time.time()
    with _captcha_lock:
        for key, exp in list(_used_captchas.items()):
            if exp < now:
                del _used_captchas[key]
        if nonce in _used_captchas:
            return False, "CAPTCHA_ALREADY_USED", "El desafío CAPTCHA ya fue utilizado."

    expected = payload["a"] + payload["b"] if payload["op"] == "+" else payload["a"] - payload["b"]
    try:
        if int(str(answer).strip()) != expected:
            return False, "INVALID_CAPTCHA", "La respuesta del CAPTCHA es incorrecta."
    except ValueError:
        return False, "INVALID_CAPTCHA", "La respuesta del CAPTCHA debe ser numérica."

    with _captcha_lock:
        _used_captchas[nonce] = payload["exp"]
    return True, None, None


# ==============================================================================
# 8. CONTRASEÑAS (bcrypt) Y SESIONES
# ==============================================================================

def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def check_password(plain_password, password_hash):
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password(password):
    """Política mínima: 8 caracteres, mayúscula, minúscula, dígito y símbolo."""
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


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id):
    """Crea la sesión server-side. Solo se persiste el SHA-256 del token."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=SESSION_MINUTES)
    execute(
        """INSERT INTO user_sessions (token_hash, user_id, expires_at, ip_origen, user_agent)
           VALUES (%s, %s, %s, %s, %s)""",
        (token_hash(token), user_id, expires_at, client_ip(),
         (request.headers.get("User-Agent") or "")[:255]),
    )
    return token, expires_at


def read_token():
    """Lee el token de sesión del header (nunca de una cookie)."""
    token = request.headers.get(SESSION_HEADER)
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    return token.strip() if token else None


def current_session():
    """Devuelve (fila, error). La fila une sesión y usuario."""
    token = read_token()
    if not token:
        return None, ("SESSION_REQUIRED", "Se requiere el encabezado %s." % SESSION_HEADER, 401)

    row = fetch_one(
        """SELECT s.id AS session_id, s.expires_at, s.revoked_at,
                  u.id, u.nombre, u.apellido_paterno, u.apellido_materno,
                  u.email, u.role, u.is_active, u.created_at, u.last_login
             FROM user_sessions s
             JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s""",
        (token_hash(token),),
    )
    if not row:
        return None, ("SESSION_INVALID", "La sesión no existe o fue revocada.", 401)
    if row["revoked_at"] is not None:
        return None, ("SESSION_INVALID", "La sesión fue cerrada.", 401)
    if row["expires_at"] <= datetime.now(timezone.utc):
        return None, ("SESSION_EXPIRED", "La sesión expiró.", 401)
    if not row["is_active"]:
        return None, ("ACCOUNT_DISABLED", "La cuenta está deshabilitada.", 403)

    execute("UPDATE user_sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE id = %s", (row["session_id"],))
    return row, None


def request_body():
    """Acepta cuerpo JSON (principal), formulario o XML."""
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    if request.form:
        return request.form.to_dict()
    raw = request.get_data(as_text=True)
    if raw and raw.strip().startswith("<"):
        try:
            root = ET.fromstring(raw)
            return {child.tag: (child.text or "").strip() for child in root}
        except ET.ParseError:
            pass
    return {}


# ==============================================================================
# 9. ENDPOINTS
# ==============================================================================

@app.route("/", methods=["GET"])
def api_root():
    """Raíz del API: punto de entrada HATEOAS (Nivel 3 de Richardson).
    ---
    tags: [System]
    produces: ["application/xml", "application/json"]
    responses:
      200:
        description: Índice de recursos disponibles con sus enlaces.
    """
    return ok(
        message="Microservicio de autenticación y gestión de usuarios.",
        data={"service": SERVICE_NAME, "version": APP_VERSION},
        links=ROOT_LINKS,
    )


@app.route("/health", methods=["GET"])
def health():
    """Estado del microservicio y de PostgreSQL.
    ---
    tags: [System]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Servicio y base de datos operativos.}
      503: {description: No fue posible conectar con PostgreSQL.}
    """
    started = time.time()
    try:
        row = fetch_one("SELECT version() AS version, CURRENT_TIMESTAMP AS server_time")
        return ok(
            message="Servicio operativo.",
            data={
                "service": SERVICE_NAME,
                "version": APP_VERSION,
                "database": "connected",
                "postgres_version": (row["version"] or "").split(" on ")[0],
                "server_time": row["server_time"].isoformat(),
                "uptime_seconds": round(time.time() - started, 3),
            },
            links={"self": link("/health"), "docs": link("/docs"), "captcha": link("/captcha")},
        )
    except Exception as exc:
        return fail("DATABASE_UNAVAILABLE", "No fue posible conectar con PostgreSQL: %s" % exc, 503)


@app.route("/captcha", methods=["GET"])
def captcha():
    """Obtiene un desafío CAPTCHA resoluble sin interfaz gráfica.
    ---
    tags: [System]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Desafío aritmético firmado con HMAC.}
    """
    captcha_id, question = generate_captcha()
    return ok(
        message="Resuelve el desafío y envíalo junto con captcha_id.",
        data={"captcha_id": captcha_id, "question": question, "expires_in": CAPTCHA_TTL_SECONDS},
        links={"login": link("/login", "POST"), "register": link("/register", "POST")},
    )


@app.route("/register", methods=["POST"])
def register():
    """Registra un nuevo usuario.
    ---
    tags: [Auth]
    consumes: ["application/json", "application/x-www-form-urlencoded"]
    produces: ["application/xml", "application/json"]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [nombre, apellido_paterno, apellido_materno, email, password]
          properties:
            nombre: {type: string}
            apellido_paterno: {type: string}
            apellido_materno: {type: string}
            email: {type: string}
            password: {type: string}
            captcha_id: {type: string}
            captcha_answer: {type: integer}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      201: {description: Usuario registrado.}
      400: {description: Error de validación.}
      409: {description: El correo ya está registrado.}
      429: {description: Demasiadas peticiones.}
    """
    if rate_limited("register"):
        return fail("TOO_MANY_REQUESTS", "Demasiadas solicitudes. Intenta más tarde.", 429, links=ANON_LINKS)

    body = request_body()
    nombre = (body.get("nombre") or "").strip()
    apellido_paterno = (body.get("apellido_paterno") or "").strip()
    apellido_materno = (body.get("apellido_materno") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    missing = [f for f, v in (
        ("nombre", nombre), ("apellido_paterno", apellido_paterno),
        ("apellido_materno", apellido_materno), ("email", email), ("password", password),
    ) if not v]
    if missing:
        return fail("VALIDATION_ERROR", "Faltan campos obligatorios: %s." % ", ".join(missing), 400, links=ANON_LINKS)

    if not EMAIL_RE.match(email):
        return fail("INVALID_EMAIL", "El formato del correo electrónico no es válido.", 400, links=ANON_LINKS)

    policy_error = validate_password(password)
    if policy_error:
        return fail("WEAK_PASSWORD", policy_error, 400, links=ANON_LINKS)

    valid, code, message = verify_captcha(body.get("captcha_id"), body.get("captcha_answer"))
    if not valid:
        return fail(code, message, 400, links=ANON_LINKS)

    try:
        row = fetch_one(
            "INSERT INTO users (nombre, apellido_paterno, apellido_materno, email, password_hash, role) "
            "VALUES (%s, %s, %s, %s, %s, 'Usuario') RETURNING " + PUBLIC_USER_FIELDS,
            (nombre, apellido_paterno, apellido_materno, email, hash_password(password)),
        )
    except UniqueViolation:
        return fail("EMAIL_ALREADY_EXISTS", "El correo ya está registrado.", 409, links=ANON_LINKS)

    audit("/register", "JSON" if wants_json() else "XML", client_ip())
    return ok(
        message="Usuario registrado correctamente.",
        data={"user": public_user(row)},
        links={"login": link("/login", "POST"), "user": link("/users/%s" % row["id"]), "self": link("/users/%s" % row["id"])},
        http_code=201,
        extra_headers={"Location": "/users/%s" % row["id"]},
    )


@app.route("/login", methods=["POST"])
def login():
    """Autentica al usuario e inicia la sesión.
    ---
    tags: [Auth]
    consumes: ["application/json", "application/x-www-form-urlencoded"]
    produces: ["application/xml", "application/json"]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [email, password]
          properties:
            email: {type: string}
            password: {type: string}
            captcha_id: {type: string}
            captcha_answer: {type: integer}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Sesión iniciada; devuelve el token.}
      401: {description: Credenciales inválidas.}
      403: {description: Cuenta bloqueada o deshabilitada.}
      429: {description: Demasiadas peticiones.}
    """
    if rate_limited("login"):
        return fail("TOO_MANY_REQUESTS", "Demasiadas solicitudes. Intenta más tarde.", 429, links=ANON_LINKS)

    body = request_body()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return fail("VALIDATION_ERROR", "El correo y la contraseña son obligatorios.", 400, links=ANON_LINKS)

    valid, code, message = verify_captcha(body.get("captcha_id"), body.get("captcha_answer"))
    if not valid:
        return fail(code, message, 400, links=ANON_LINKS)

    row = fetch_one("SELECT * FROM users WHERE LOWER(email) = %s", (email,))

    # Mensaje genérico: nunca se revela si el correo existe (anti-enumeración).
    generic = ("INVALID_CREDENTIALS", "El correo o la contraseña son incorrectos.", 401)

    if not row:
        bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=4))  # iguala el tiempo de respuesta
        return fail(generic[0], generic[1], generic[2], links=ANON_LINKS)

    if row["locked_until"] and row["locked_until"] > datetime.now(timezone.utc):
        return fail("ACCOUNT_LOCKED", "La cuenta está bloqueada temporalmente por intentos fallidos.", 403, links=ANON_LINKS)

    if not row["is_active"]:
        return fail("ACCOUNT_DISABLED", "La cuenta está deshabilitada.", 403, links=ANON_LINKS)

    if not check_password(password, row["password_hash"]):
        attempts = (row["failed_attempts"] or 0) + 1
        if attempts >= MAX_FAILED_ATTEMPTS:
            execute(
                """UPDATE users SET failed_attempts = %s,
                          locked_until = CURRENT_TIMESTAMP + (%s || ' minutes')::interval
                    WHERE id = %s""",
                (attempts, LOCKOUT_MINUTES, row["id"]),
            )
            return fail("ACCOUNT_LOCKED", "La cuenta fue bloqueada por %d minutos." % LOCKOUT_MINUTES, 403, links=ANON_LINKS)
        execute("UPDATE users SET failed_attempts = %s WHERE id = %s", (attempts, row["id"]))
        return fail(generic[0], generic[1], generic[2], links=ANON_LINKS)

    execute("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = CURRENT_TIMESTAMP WHERE id = %s",
            (row["id"],))

    token, expires_at = create_session(row["id"])
    audit("/login", "JSON" if wants_json() else "XML", client_ip())

    return ok(
        message="Autenticación exitosa.",
        data={
            "user": public_user(row),
            "session": {
                "token": token,
                "token_type": "header",
                "header": SESSION_HEADER,
                "expires_at": expires_at.isoformat(),
                "expires_in": SESSION_MINUTES * 60,
            },
        },
        links=auth_links(row["id"]),
    )


@app.route("/logout", methods=["POST"])
def logout():
    """Cierra la sesión revocándola de inmediato.
    ---
    tags: [Auth]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: X-Session-Token, in: header, type: string, required: true}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Sesión cerrada.}
      401: {description: Sesión ausente o inválida.}
    """
    row, error = current_session()
    if error:
        return fail(error[0], error[1], error[2], links=ANON_LINKS)

    execute("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE id = %s", (row["session_id"],))
    audit("/logout", "JSON" if wants_json() else "XML", client_ip())

    return ok(
        message="Sesión cerrada correctamente.",
        data={"revoked": True},
        links=ANON_LINKS,
    )


@app.route("/session", methods=["GET"])
def session_status():
    """Consulta si existe una sesión autenticada.
    ---
    tags: [Session]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: X-Session-Token, in: header, type: string, required: true}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Sesión activa.}
      401: {description: Sesión ausente, expirada o revocada.}
    """
    row, error = current_session()
    if error:
        return fail(error[0], error[1], error[2], links=ANON_LINKS)

    remaining = int((row["expires_at"] - datetime.now(timezone.utc)).total_seconds())
    return ok(
        message="Sesión activa.",
        data={
            "authenticated": True,
            "user": public_user(row),
            "session": {
                "expires_at": row["expires_at"].isoformat(),
                "remaining_seconds": max(remaining, 0),
                "duration_minutes": SESSION_MINUTES,
            },
        },
        links=auth_links(row["id"]),
    )


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Obtiene los datos públicos de un usuario (recurso REST real).
    ---
    tags: [Users]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: user_id, in: path, type: integer, required: true}
      - {name: X-Session-Token, in: header, type: string, required: true}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Usuario encontrado.}
      401: {description: Sesión requerida.}
      404: {description: Usuario no encontrado.}
    """
    row, error = current_session()
    if error:
        return fail(error[0], error[1], error[2], links=ANON_LINKS)

    target = fetch_one("SELECT " + PUBLIC_USER_FIELDS + " FROM users WHERE id = %s", (user_id,))
    if not target:
        return fail("USER_NOT_FOUND", "No existe un usuario con ese identificador.", 404, links=auth_links(row["id"]))

    return ok(
        message="Usuario encontrado.",
        data={"user": public_user(target)},
        links={
            "self":    link("/users/%s" % user_id),
            "session": link("/session"),
            "logout":  link("/logout", "POST"),
        },
    )


# ==============================================================================
# 10. MANEJADORES DE ERROR GLOBALES (siempre en el formato negociado)
# ==============================================================================

@app.errorhandler(404)
def handle_404(_e):
    return fail("NOT_FOUND", "El recurso solicitado no existe.", 404, links=ROOT_LINKS)


@app.errorhandler(405)
def handle_405(_e):
    return fail("METHOD_NOT_ALLOWED", "El método HTTP no está permitido para este recurso.", 405, links=ROOT_LINKS)


@app.errorhandler(500)
def handle_500(_e):
    return fail("INTERNAL_ERROR", "Error interno del servidor.", 500, links=ROOT_LINKS)


# ==============================================================================
# 11. ARRANQUE
# ==============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print("=" * 70)
    print(" %s v%s  ->  http://localhost:%d" % (SERVICE_NAME, APP_VERSION, port))
    print(" Swagger UI: http://localhost:%d/docs" % port)
    print(" Formato predeterminado: XML  |  JSON con ?format=json")
    print("=" * 70)
    app.run(host="0.0.0.0", port=port, debug=True)

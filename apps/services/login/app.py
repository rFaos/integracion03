"""
==============================================================================
PROYECTO: INTEGRACION03 - MICROSERVICIO DE AUTENTICACIÓN Y GESTIÓN DE USUARIOS
TECNOLOGÍAS: Python 3, Flask, Psycopg v3, PostgreSQL, Flasgger (OpenAPI), bcrypt
AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
PUERTO: 5000

DISEÑO:
  - Autenticación con JWT (RFC 7519, HS256) SIN COOKIES.
      * ACCESS TOKEN  = JWT firmado, autocontenido y SIN ESTADO (15 min).
        Cualquier microservicio con el mismo secreto lo valida sin tocar la
        base de datos: es lo que permite que el servicio de libros proteja sus
        escrituras sin conocer a este servicio.
      * REFRESH TOKEN = token opaco aleatorio, guardado en user_sessions SOLO
        como SHA-256 (7 días). Se rota en cada uso y detecta reuso.
  - Compatibilidad: se sigue aceptando el header heredado X-Session-Token y el
    token opaco anterior, de modo que ningún cliente existente se rompe.
  - Salida dual: XML por defecto, JSON con ?format=json o Accept: application/json.
  - Nivel 3 del Modelo de Madurez de Richardson: hipermedia (_links / <links>).
  - CAPTCHA sin GUI: desafío aritmético firmado con HMAC (stateless).
  - Contraseñas: solo hash bcrypt en users.password_hash.
==============================================================================
"""

import os
import re
import sys
import json
import time
import hmac
import base64
import hashlib
import secrets
import threading
import uuid
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

# Permite arrancar el servicio desde cualquier directorio (por ejemplo con
# gunicorn desde la raíz del monorepo) sin perder de vista los módulos locales.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt_utils  # noqa: E402  (implementación propia de RFC 7519)

# ==============================================================================
# 1. CONFIGURACIÓN
# ==============================================================================

load_dotenv()

SERVICE_NAME = "login-microservice"
APP_VERSION = "1.1.0"

SESSION_MINUTES     = int(os.getenv("SESSION_MINUTES", "30"))
CAPTCHA_TTL_SECONDS = int(os.getenv("CAPTCHA_TTL_SECONDS", "300"))
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_MINUTES     = int(os.getenv("LOCKOUT_MINUTES", "15"))
BCRYPT_ROUNDS       = int(os.getenv("BCRYPT_ROUNDS", "12"))
RATE_LIMIT_MAX      = int(os.getenv("RATE_LIMIT_MAX", "20"))
RATE_LIMIT_WINDOW   = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

SECRET_KEY     = os.getenv("SECRET_KEY", "dev-secret-cambia-esto")
SESSION_HEADER = "X-Session-Token"

# --- JWT (nuevo requerimiento) ------------------------------------------------
# El secreto se comparte con el microservicio de libros para que pueda verificar
# la firma SIN llamar a este servicio. En producción se inyecta por variable de
# entorno (o Secret Manager) y NUNCA se versiona.
JWT_SECRET        = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM     = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER        = os.getenv("JWT_ISSUER", "library-login")
JWT_AUDIENCE      = os.getenv("JWT_AUDIENCE", "library-api")
JWT_ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "15"))
JWT_REFRESH_DAYS   = int(os.getenv("JWT_REFRESH_DAYS", "7"))
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", "5"))

# Comprobación opcional de revocación contra user_sessions en los endpoints de
# este servicio. El access token es sin estado; esto es defensa en profundidad
# para que /logout tenga efecto inmediato aquí (el servicio de libros, que sí es
# puramente sin estado, tolera como máximo JWT_ACCESS_MINUTES de desfase).
JWT_CHECK_SESSION = os.getenv("JWT_CHECK_SESSION", "true").lower() in ("true", "1", "yes")

if not JWT_SECRET:
    # No se aborta el arranque para no romper el entorno de práctica, pero se
    # avisa en consola: sin secreto no se pueden emitir tokens válidos.
    print("[AVISO] JWT_SECRET no está definido en el entorno; los tokens JWT no podrán emitirse.")
    print("        Copia .env.example a .env y define JWT_SECRET (mismo valor en ambos microservicios).")


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
            "plataforma de librería. Emite **JWT (RFC 7519, HS256)** como access token "
            "autocontenido y sin estado, más un refresh token opaco rotativo. Sesión sin cookies, "
            "respuestas en XML (predeterminado) y JSON, e hipermedia de Nivel 3 (HATEOAS)."
        ),
        "version": APP_VERSION,
        "contact": {
            "name": "Fabián Azaed Orta Singlaterry",
            "email": "azaedorta@hotmail.com",
            "institution": "Universidad de Monterrey (UDEM)",
        },
    },
    "tags": [
        {"name": "Auth",     "description": "Registro, inicio de sesión y emisión de JWT"},
        {"name": "Session",  "description": "Consulta, extensión, refresco y cierre de sesión"},
        {"name": "Users",    "description": "Recursos de usuario"},
        {"name": "System",   "description": "Estado del servicio, CAPTCHA y verificación de tokens"},
    ],
    "schemes": ["http", "https"],
    # Definición de seguridad: Swagger muestra el candado y el botón "Authorize"
    # para enviar 'Authorization: Bearer <access_token>'.
    "securityDefinitions": {
        "BearerJWT": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Escribe: Bearer <access_token>  (el JWT que devuelve POST /login)",
        }
    },
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
    "refresh":  link("/refresh", "POST"),
    "logout":   link("/logout", "POST"),
    "session":  link("/session"),
    "extend":   link("/session/extend", "POST"),
    "verify":   link("/verify", "POST"),
    "profile":  link("/profile", "PATCH"),
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
        "profile": link("/profile", "PATCH"),
        "extend":  link("/session/extend", "POST"),
        "refresh": link("/refresh", "POST"),
        "verify":  link("/verify", "POST"),
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


# ==============================================================================
# 8.b JWT: EMISIÓN DEL ACCESS TOKEN (SIN ESTADO) Y DEL REFRESH TOKEN
# ==============================================================================

def issue_access_token(user_row, session_id, jti):
    """Construye y firma el access token (JWT) de un usuario.

    El token es AUTOCONTENIDO: lleva quién es el usuario y hasta cuándo vale,
    todo firmado. Por eso el microservicio de libros puede autorizar una
    escritura verificando solo la firma, sin consultar la base de datos ni
    llamar a este servicio.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=JWT_ACCESS_MINUTES)
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(user_row["id"]),
        "jti": str(jti),
        "typ": "access",
        "email": user_row.get("email"),
        "role": user_row.get("role"),
        "name": " ".join(filter(None, [user_row.get("nombre"), user_row.get("apellido_paterno")])),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    # `sid` liga el token con su sesión renovable. Solo se omite cuando el
    # servicio se configura explícitamente como 100 % sin estado
    # (JWT_CHECK_SESSION=false), donde no existe ninguna fila que referenciar.
    if session_id is not None:
        payload["sid"] = int(session_id)

    return jwt_utils.encode_jwt(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expires_at, payload


def create_session(user_id, jti):
    """Crea la sesión renovable y devuelve (refresh_token, session_id, expires_at).

    Solo se persiste el SHA-256 del refresh token: si la base se filtra, los
    valores guardados no sirven para autenticarse (mismo principio que bcrypt).
    """
    refresh_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_DAYS)
    row = fetch_one(
        """INSERT INTO user_sessions
               (token_hash, user_id, expires_at, ip_origen, user_agent, jti, token_type)
           VALUES (%s, %s, %s, %s, %s, %s, 'refresh')
        RETURNING id, expires_at""",
        (token_hash(refresh_token), user_id, expires_at, client_ip(),
         (request.headers.get("User-Agent") or "")[:255], str(jti)),
    )
    return refresh_token, row["id"], row["expires_at"]


def session_payload(user_row, access_token, access_expires_at,
                    refresh_token, refresh_expires_at):
    """Bloque `session` de la respuesta: las dos credenciales y sus vigencias.

    Se conserva la clave `token` apuntando al access token para no romper a los
    clientes escritos antes del requerimiento de JWT.
    """
    now = datetime.now(timezone.utc)
    return {
        "access_token": access_token,
        "token": access_token,                    # compatibilidad hacia atrás
        "token_type": "Bearer",
        "header": "Authorization",
        "algorithm": JWT_ALGORITHM,
        # Las vigencias se expresan con las constantes de configuración (no con
        # la resta de fechas) para que el valor sea exacto: 900, no 899.
        "expires_in": JWT_ACCESS_MINUTES * 60,
        "expires_at": access_expires_at.isoformat(),
        "refresh_token": refresh_token,
        "refresh_expires_in": JWT_REFRESH_DAYS * 86400,
        "refresh_expires_at": refresh_expires_at.isoformat(),
        "refresh_endpoint": "/refresh",
        "issuer": JWT_ISSUER,
        "audience": JWT_AUDIENCE,
    }


def read_credentials():
    """Devuelve (tipo, valor) de la credencial presentada, o (None, None).

    Se aceptan las dos formas para no romper a ningún cliente:
      Authorization: Bearer <JWT>     -> estándar (lo que exige el servicio de libros)
      X-Session-Token: <JWT u opaco>  -> clientes anteriores al requerimiento
    """
    raw = request.headers.get(SESSION_HEADER)
    if not raw:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            raw = auth[7:]
    raw = (raw or "").strip()
    if not raw:
        return None, None
    return ("jwt" if jwt_utils.looks_like_jwt(raw) else "opaque"), raw


def read_token():
    """Compatibilidad: devuelve el valor crudo de la credencial."""
    return read_credentials()[1]


SESSION_ROW_FIELDS = """s.id AS session_id, s.expires_at AS session_expires_at, s.revoked_at, s.jti,
                        u.id, u.nombre, u.apellido_paterno, u.apellido_materno,
                        u.email, u.role, u.is_active, u.created_at, u.last_login"""


def session_row(session_id):
    """Fila de sesión + usuario por identificador de sesión (PK)."""
    return fetch_one(
        "SELECT " + SESSION_ROW_FIELDS +
        " FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.id = %s",
        (session_id,),
    )


def verify_access_token(token, verify_exp=True):
    """Verifica un access token. Devuelve (claims, error)."""
    try:
        claims = jwt_utils.decode_jwt(
            token, JWT_SECRET, algorithms=(JWT_ALGORITHM,),
            issuer=JWT_ISSUER, audience=JWT_AUDIENCE,
            leeway=JWT_LEEWAY_SECONDS, verify_exp=verify_exp,
        )
    except jwt_utils.JWTError as exc:
        return None, (exc.code, exc.message, exc.status)
    return claims, None


def current_session():
    """Devuelve (fila, error). Acepta JWT (nuevo) o token opaco (heredado).

    Para el JWT el camino normal es SIN ESTADO: firma y reclamaciones, sin tocar
    la base de datos. La consulta a user_sessions solo ocurre si
    JWT_CHECK_SESSION está activo, para que /logout tenga efecto inmediato en
    este servicio; el de libros no puede hacer eso sin romper el desacoplamiento,
    y por eso su access token vive poco (JWT_ACCESS_MINUTES).
    """
    kind, token = read_credentials()
    if not token:
        return None, ("SESSION_REQUIRED",
                      "Se requiere 'Authorization: Bearer <access_token>'.", 401)

    if kind == "jwt":
        claims, error = verify_access_token(token)
        if error:
            return None, error

        session_id = claims.get("sid")
        if JWT_CHECK_SESSION and session_id:
            row = session_row(int(session_id))
            if not row:
                return None, ("SESSION_INVALID", "La sesión no existe o fue revocada.", 401)
            if row["revoked_at"] is not None:
                return None, ("SESSION_INVALID", "La sesión fue cerrada.", 401)
            if not row["is_active"]:
                return None, ("ACCOUNT_DISABLED", "La cuenta está deshabilitada.", 403)
            execute("UPDATE user_sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (row["session_id"],))
            row["jwt_claims"] = claims
            return row, None

        # Camino puramente sin estado: se confía en el token y se carga el usuario.
        row = fetch_one("SELECT " + PUBLIC_USER_FIELDS + " FROM users WHERE id = %s",
                        (int(claims["sub"]),))
        if not row:
            return None, ("SESSION_INVALID", "El usuario del token ya no existe.", 401)
        if not row["is_active"]:
            return None, ("ACCOUNT_DISABLED", "La cuenta está deshabilitada.", 403)
        row["session_id"] = None
        row["session_expires_at"] = None
        row["revoked_at"] = None
        row["jti"] = claims.get("jti")
        row["jwt_claims"] = claims
        return row, None

    # --- Token opaco heredado (prompt 05) -------------------------------------
    row = fetch_one(
        "SELECT " + SESSION_ROW_FIELDS +
        " FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = %s",
        (token_hash(token),),
    )
    if not row:
        return None, ("SESSION_INVALID", "La sesión no existe o fue revocada.", 401)
    if row["revoked_at"] is not None:
        return None, ("SESSION_INVALID", "La sesión fue cerrada.", 401)
    if row["session_expires_at"] <= datetime.now(timezone.utc):
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
        data={
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "authentication": {
                "type": "JWT",
                "algorithm": JWT_ALGORITHM,
                "access_token_ttl_minutes": JWT_ACCESS_MINUTES,
                "refresh_token_ttl_days": JWT_REFRESH_DAYS,
                "usage": "Authorization: Bearer <access_token>",
                "issuer": JWT_ISSUER,
                "audience": JWT_AUDIENCE,
            },
        },
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

        # Verifica que la migración 01_migration_auth.sql ya se aplicó.
        # Sin ella, /login y /register fallan con 500 porque las columnas
        # de identidad y la tabla de sesiones todavía no existen.
        schema = fetch_one(
            """SELECT
                 (SELECT COUNT(*) FROM information_schema.columns
                   WHERE table_schema = current_schema() AND table_name = 'users'
                     AND column_name IN ('nombre', 'apellido_paterno',
                                         'apellido_materno', 'email')) AS user_columns,
                 (SELECT COUNT(*) FROM information_schema.tables
                   WHERE table_schema = current_schema()
                     AND table_name = 'user_sessions') AS sessions_table,
                 (SELECT COUNT(*) FROM information_schema.columns
                   WHERE table_schema = current_schema() AND table_name = 'user_sessions'
                     AND column_name IN ('jti', 'token_type')) AS jwt_columns"""
        )
        migrated = (schema["user_columns"] == 4 and schema["sessions_table"] == 1
                    and schema["jwt_columns"] == 2)

        data = {
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "database": "connected",
            "postgres_version": (row["version"] or "").split(" on ")[0],
            "schema": "ready" if migrated else "migration_pending",
            "server_time": row["server_time"].isoformat(),
            "uptime_seconds": round(time.time() - started, 3),
            # Bloque JWT: permite comprobar de un vistazo que los dos
            # microservicios comparten el mismo contrato (algoritmo, emisor,
            # audiencia). El secreto NUNCA se expone, solo su huella.
            "jwt": {
                "enabled": bool(JWT_SECRET),
                "algorithm": JWT_ALGORITHM,
                "issuer": JWT_ISSUER,
                "audience": JWT_AUDIENCE,
                "access_ttl_minutes": JWT_ACCESS_MINUTES,
                "refresh_ttl_days": JWT_REFRESH_DAYS,
                "session_check": JWT_CHECK_SESSION,
                "secret_fingerprint": (hashlib.sha256(JWT_SECRET.encode()).hexdigest()[:12]
                                       if JWT_SECRET else None),
            },
        }
        if not migrated:
            data["migration_hint"] = (
                "Faltan migraciones sobre la base de datos library. Comandos: "
                "psql -U library_user -d library -f sql/01_migration_auth.sql && "
                "psql -U library_user -d library -f sql/03_migration_jwt.sql"
            )

        return ok(
            message="Servicio operativo." if migrated else "Servicio operativo, pero falta aplicar la migración.",
            data=data,
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
      200: {description: "Sesión iniciada; devuelve access_token (JWT) y refresh_token."}
      400: {description: Error de validación o CAPTCHA inválido.}
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

    # --- Emisión del JWT (access token) + refresh token -----------------------
    # El `jti` (JWT ID, RFC 7519) identifica esta emisión concreta: queda ligado
    # a la sesión en la base de datos, de modo que el token es rastreable.
    if not JWT_SECRET:
        return fail("JWT_NOT_CONFIGURED",
                    "El servicio no tiene configurado JWT_SECRET: no puede emitir tokens.",
                    500, links=ANON_LINKS)

    jti = uuid.uuid4()
    refresh_token, session_id, refresh_expires_at = create_session(row["id"], jti)
    access_token, access_expires_at, _claims = issue_access_token(row, session_id, jti)

    audit("/login", "JSON" if wants_json() else "XML", client_ip())

    return ok(
        message="Autenticación exitosa. Usa 'Authorization: Bearer <access_token>'.",
        data={
            "user": public_user(row),
            "session": session_payload(row, access_token, access_expires_at,
                                       refresh_token, refresh_expires_at),
        },
        links=auth_links(row["id"]),
    )


@app.route("/logout", methods=["POST"])
def logout():
    """Cierra la sesión revocando el refresh token y la sesión asociada.
    ---
    tags: [Auth]
    consumes: ["application/json", "application/x-www-form-urlencoded"]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: Authorization, in: header, type: string, required: false,
         description: "Bearer <access_token>. También se acepta el heredado X-Session-Token."}
      - name: body
        in: body
        required: false
        description: "Opcional: refresh_token para revocarlo explícitamente."
        schema:
          type: object
          properties:
            refresh_token: {type: string}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Sesión cerrada.}
      401: {description: Sesión ausente o inválida.}
    """
    body = request_body()
    refresh_token = (body.get("refresh_token") or "").strip() or None
    kind, token = read_credentials()

    session_id = None

    # 1. Localizar la sesión del access token. Se verifica la firma SIN exigir
    #    'exp': si el usuario pulsa "cerrar sesión" con el token ya expirado, la
    #    intención sigue siendo válida y la sesión debe quedar revocada.
    if kind == "jwt":
        claims, _error = verify_access_token(token, verify_exp=False)
        if claims and claims.get("sid"):
            session_id = int(claims["sid"])
    elif kind == "opaque":
        legacy = fetch_one("SELECT id FROM user_sessions WHERE token_hash = %s",
                           (token_hash(token),))
        if legacy:
            session_id = legacy["id"]

    if session_id is None and not refresh_token:
        return fail("SESSION_REQUIRED",
                    "Se requiere 'Authorization: Bearer <access_token>' o un 'refresh_token'.",
                    401, links=ANON_LINKS)

    revoked = 0
    if session_id is not None:
        revoked += execute(
            "UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP "
            " WHERE id = %s AND revoked_at IS NULL", (session_id,))

    # 2. Revocar también el refresh token si el cliente lo envía: así se puede
    #    cerrar sesión desde un dispositivo que ya perdió el access token.
    if refresh_token:
        revoked += execute(
            "UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP "
            " WHERE token_hash = %s AND revoked_at IS NULL", (token_hash(refresh_token),))

    audit("/logout", "JSON" if wants_json() else "XML", client_ip())

    return ok(
        message="Sesión cerrada correctamente.",
        data={
            "revoked": True,
            "sessions_revoked": revoked,
            "note": ("El access token es un JWT sin estado: este servicio lo rechaza de "
                     "inmediato (revocación en user_sessions), mientras que el servicio de "
                     "libros lo aceptará como máximo hasta su expiración natural "
                     "(JWT_ACCESS_MINUTES). Es el precio de no compartir estado."),
        },
        links=ANON_LINKS,
    )


@app.route("/session", methods=["GET"])
def session_status():
    """Consulta si existe una sesión autenticada (valida el JWT sin estado).
    ---
    tags: [Session]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: Authorization, in: header, type: string, required: true,
         description: "Bearer <access_token>. También se acepta el heredado X-Session-Token."}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Sesión activa.}
      401: {description: Sesión ausente, expirada, con firma inválida o revocada.}
    """
    row, error = current_session()
    if error:
        return fail(error[0], error[1], error[2], links=ANON_LINKS)

    claims = row.get("jwt_claims") or {}
    session_expires_at = row.get("session_expires_at")
    remaining = None
    if session_expires_at is not None:
        remaining = max(int((session_expires_at - datetime.now(timezone.utc)).total_seconds()), 0)

    jwt_block = None
    if claims:
        jwt_block = {
            "sub": claims.get("sub"),
            "sid": claims.get("sid"),
            "jti": claims.get("jti"),
            "iss": claims.get("iss"),
            "aud": claims.get("aud"),
            "role": claims.get("role"),
            "exp": datetime.fromtimestamp(claims["exp"], timezone.utc).isoformat(),
            "remaining_seconds": max(int(claims["exp"] - time.time()), 0),
        }

    return ok(
        message="Sesión activa.",
        data={
            "authenticated": True,
            "user": public_user(row),
            "session": {
                "credential": "jwt" if claims else "opaque",
                "expires_at": session_expires_at.isoformat() if session_expires_at else None,
                "remaining_seconds": remaining,
                "duration_minutes": SESSION_MINUTES,
            },
            "jwt": jwt_block,
        },
        links=auth_links(row["id"]),
    )


@app.route("/session/extend", methods=["POST"])
def extend_session():
    """Emite un access token nuevo y renueva la ventana del refresh token.
    ---
    tags: [Session]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: Authorization, in: header, type: string, required: true,
         description: "Bearer <access_token>"}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Sesión extendida; devuelve un access_token nuevo.}
      401: {description: Sesión ausente, expirada o revocada.}
    """
    row, error = current_session()
    if error:
        return fail(error[0], error[1], error[2], links=ANON_LINKS)

    claims = row.get("jwt_claims") or {}
    session_id = row.get("session_id")
    jti = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # La nueva vigencia se calcula desde AHORA, no desde el vencimiento previo:
    # así el cliente no acumula tiempo indefinidamente encadenando llamadas.
    refresh_expires_at = now + timedelta(days=JWT_REFRESH_DAYS)
    if session_id is not None:
        execute(
            "UPDATE user_sessions SET expires_at = %s, last_seen_at = CURRENT_TIMESTAMP, jti = %s "
            " WHERE id = %s",
            (refresh_expires_at, str(jti), session_id),
        )
    else:
        # Configuración 100 % sin estado: no hay fila que renovar.
        refresh_expires_at = None

    access_token, access_expires_at, _payload = issue_access_token(
        row, session_id if session_id is not None else claims.get("sid"), jti)

    audit("/session/extend", "JSON" if wants_json() else "XML", client_ip())

    return ok(
        message="Sesión extendida: se emitió un access_token nuevo.",
        data={
            "access_token": access_token,
            "token": access_token,                 # compatibilidad
            "token_type": "Bearer",
            "expires_in": int((access_expires_at - now).total_seconds()),
            "expires_at": access_expires_at.isoformat(),
            "refresh_expires_at": (refresh_expires_at.isoformat()
                                   if refresh_expires_at else None),
            "note": "Usa el access_token nuevo; el anterior sigue siendo válido hasta su 'exp'.",
        },
        links=auth_links(row["id"]),
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    """Canjea un refresh token por un access token (JWT) nuevo, con rotación.
    ---
    tags: [Session]
    consumes: ["application/json", "application/x-www-form-urlencoded"]
    produces: ["application/xml", "application/json"]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [refresh_token]
          properties:
            refresh_token: {type: string}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Par de tokens nuevo (rotación aplicada).}
      401: {description: Refresh token ausente, inválido, expirado o reutilizado.}
    """
    if rate_limited("refresh"):
        return fail("TOO_MANY_REQUESTS", "Demasiadas solicitudes. Intenta más tarde.", 429, links=ANON_LINKS)

    body = request_body()
    presented = (body.get("refresh_token") or "").strip()
    if not presented:
        return fail("REFRESH_REQUIRED",
                    "Se requiere el campo 'refresh_token' en el cuerpo.", 400, links=ANON_LINKS)

    row = fetch_one(
        """SELECT s.id, s.user_id, s.expires_at, s.revoked_at, s.rotated_at,
                  u.id AS uid, u.nombre, u.apellido_paterno, u.apellido_materno,
                  u.email, u.role, u.is_active
             FROM user_sessions s
             JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s""",
        (token_hash(presented),),
    )
    if not row:
        return fail("REFRESH_INVALID", "El refresh token no existe o no fue emitido por este servicio.",
                    401, links=ANON_LINKS)

    # Detección de reuso: si el token YA fue rotado o revocado y alguien lo
    # vuelve a presentar, hay dos portadores del mismo token (posible robo).
    # Se revoca todo lo del usuario y se obliga a un login limpio.
    if row["revoked_at"] is not None or row["rotated_at"] is not None:
        execute("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP "
                " WHERE user_id = %s AND revoked_at IS NULL", (row["user_id"],))
        audit("/refresh", "JSON" if wants_json() else "XML", client_ip())
        return fail("REFRESH_REUSED",
                    "El refresh token ya había sido usado. Por seguridad se revocaron "
                    "todas las sesiones de la cuenta: vuelve a iniciar sesión.",
                    401, links=ANON_LINKS)

    if row["expires_at"] <= datetime.now(timezone.utc):
        return fail("REFRESH_EXPIRED", "El refresh token expiró. Inicia sesión de nuevo.",
                    401, links=ANON_LINKS)

    if not row["is_active"]:
        return fail("ACCOUNT_DISABLED", "La cuenta está deshabilitada.", 403, links=ANON_LINKS)

    # --- Rotación: el token viejo muere aquí y nace un par nuevo --------------
    jti = uuid.uuid4()
    new_refresh, new_session_id, refresh_expires_at = create_session(row["user_id"], jti)
    execute("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP, "
            "       rotated_at = CURRENT_TIMESTAMP, replaced_by_hash = %s "
            " WHERE id = %s", (token_hash(new_refresh), row["id"]))

    user_row = {"id": row["user_id"], "nombre": row["nombre"],
                "apellido_paterno": row["apellido_paterno"],
                "apellido_materno": row["apellido_materno"],
                "email": row["email"], "role": row["role"]}
    access_token, access_expires_at, _claims = issue_access_token(user_row, new_session_id, jti)

    audit("/refresh", "JSON" if wants_json() else "XML", client_ip())

    return ok(
        message="Tokens renovados. El refresh token anterior quedó revocado (rotación).",
        data={
            "user": public_user(row),
            "session": session_payload(user_row, access_token, access_expires_at,
                                       new_refresh, refresh_expires_at),
        },
        links=auth_links(row["user_id"]),
    )


@app.route("/verify", methods=["POST", "GET"])
def verify_token():
    """Verifica un JWT sin estado y devuelve sus reclamaciones.
    ---
    tags: [System]
    consumes: ["application/json", "application/x-www-form-urlencoded"]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: Authorization, in: header, type: string, required: false,
         description: "Bearer <access_token>"}
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            token: {type: string}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: "Token válido: devuelve {valid: true, claims: {...}}."}
      401: {description: "Token inválido: devuelve el motivo exacto."}
    """
    body = request_body()
    token = (body.get("token") or "").strip() or read_credentials()[1]

    claims, error = verify_access_token(token) if token else (None, ("MISSING_TOKEN", "No se envió ningún token.", 401))
    if error:
        return fail(error[0], error[1], error[2], links=ANON_LINKS)

    return ok(
        message="Token válido.",
        data={
            "valid": True,
            "claims": claims,
            "expires_at": datetime.fromtimestamp(claims["exp"], timezone.utc).isoformat(),
            "remaining_seconds": max(int(claims["exp"] - time.time()), 0),
        },
        links={"login": link("/login", "POST"), "refresh": link("/refresh", "POST")},
    )


@app.route("/profile", methods=["PATCH"])
def update_profile():
    """Actualiza parcialmente los datos de la cuenta autenticada.
    ---
    tags: [Users]
    consumes: ["application/json", "application/x-www-form-urlencoded"]
    produces: ["application/xml", "application/json"]
    parameters:
      - {name: X-Session-Token, in: header, type: string, required: true}
      - name: body
        in: body
        required: true
        description: Solo los campos a modificar. Los ausentes no se tocan.
        schema:
          type: object
          properties:
            nombre: {type: string}
            apellido_paterno: {type: string}
            apellido_materno: {type: string}
            email: {type: string}
            password: {type: string}
            current_password: {type: string}
      - {name: format, in: query, type: string, enum: [xml, json], required: false}
    responses:
      200: {description: Perfil actualizado.}
      400: {description: Error de validación.}
      401: {description: Sesión ausente o inválida.}
      403: {description: La contraseña actual no es correcta.}
      409: {description: El correo ya está registrado por otra cuenta.}
    """
    row, error = current_session()
    if error:
        return fail(error[0], error[1], error[2], links=ANON_LINKS)

    body = request_body()
    assignments = []
    values = []
    changed = []

    # Solo se toca lo que viene en el cuerpo: es la diferencia con un PUT.
    for field in ("nombre", "apellido_paterno", "apellido_materno"):
        if field in body and body[field] is not None:
            value = str(body[field]).strip()
            if not value:
                return fail("VALIDATION_ERROR", "El campo %s no puede quedar vacío." % field,
                            400, links=auth_links(row["id"]))
            assignments.append("%s = %%s" % field)
            values.append(value)
            changed.append(field)

    if body.get("email") is not None and str(body.get("email")).strip():
        email = str(body["email"]).strip().lower()
        if not EMAIL_RE.match(email):
            return fail("INVALID_EMAIL", "El formato del correo electrónico no es válido.",
                        400, links=auth_links(row["id"]))
        assignments.append("email = %s")
        values.append(email)
        changed.append("email")

    if body.get("password"):
        current = body.get("current_password") or ""
        stored = fetch_one("SELECT password_hash FROM users WHERE id = %s", (row["id"],))
        if not stored or not check_password(current, stored["password_hash"]):
            return fail("INVALID_CURRENT_PASSWORD",
                        "La contraseña actual no es correcta; se requiere para cambiarla.",
                        403, links=auth_links(row["id"]))
        policy_error = validate_password(body["password"])
        if policy_error:
            return fail("WEAK_PASSWORD", policy_error, 400, links=auth_links(row["id"]))
        assignments.append("password_hash = %s")
        values.append(hash_password(body["password"]))
        changed.append("password")

    if not changed:
        return fail("VALIDATION_ERROR",
                    "No se envió ningún campo modificable: nombre, apellido_paterno, "
                    "apellido_materno, email o password.",
                    400, links=auth_links(row["id"]))

    values.append(row["id"])
    try:
        execute("UPDATE users SET %s WHERE id = %%s" % ", ".join(assignments), tuple(values))
    except UniqueViolation:
        return fail("EMAIL_ALREADY_EXISTS", "El correo ya está registrado por otra cuenta.",
                    409, links=auth_links(row["id"]))

    updated = fetch_one("SELECT " + PUBLIC_USER_FIELDS + " FROM users WHERE id = %s", (row["id"],))
    audit("/profile", "JSON" if wants_json() else "XML", client_ip())

    return ok(
        message="Perfil actualizado correctamente.",
        data={"user": public_user(updated), "updated_fields": changed},
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
    print(" Autenticación: JWT %s (%s)  |  access %d min  |  refresh %d días"
          % (JWT_ALGORITHM, JWT_ISSUER, JWT_ACCESS_MINUTES, JWT_REFRESH_DAYS))
    print(" Uso: Authorization: Bearer <access_token>")
    print("=" * 70)
    app.run(host="0.0.0.0", port=port, debug=True)

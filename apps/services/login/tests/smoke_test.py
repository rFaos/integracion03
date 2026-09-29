"""
==============================================================================
PRUEBA DE HUMO DEL FLUJO DE AUTENTICACIÓN CON JWT (sin PostgreSQL)
------------------------------------------------------------------------------
Reemplaza la capa de acceso a datos por un doble en memoria para poder
verificar el flujo completo:

    captcha -> register -> login (access + refresh) -> session
            -> refresh (rotación) -> logout -> revocación

Además comprueba los casos de seguridad del JWT: alg=none, firma manipulada,
token expirado, emisor/audiencia ajenos y detección de reuso del refresh token.

Ejecutar:
    ./venv/Scripts/python.exe tests/smoke_test.py
==============================================================================
"""

import base64
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as A
import jwt_utils
from psycopg.errors import UniqueViolation

# ------------------------------------------------------------------------------
# Doble en memoria de la capa de datos
# ------------------------------------------------------------------------------
USERS = []
SESSIONS = []
_seq = [1]


def _norm(sql):
    return " ".join(sql.split())


def _sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _session_row(session, id_is_session=False):
    """Fila fusionada sesión + usuario (superset de lo que pide cada consulta).

    `id_is_session` distingue las dos formas de consultar:
      - la consulta de /refresh pide `s.id, s.user_id`  -> id = id de SESIÓN
      - la consulta heredada pide `s.id AS session_id`  -> id = id de USUARIO
    """
    user = next(u for u in USERS if u["id"] == session["user_id"])
    row = dict(user)
    row.update({
        "session_id": session["id"],
        "session_expires_at": session["expires_at"],
        "expires_at": session["expires_at"],
        "revoked_at": session["revoked_at"],
        "rotated_at": session.get("rotated_at"),
        "replaced_by_hash": session.get("replaced_by_hash"),
        "jti": session.get("jti"),
        "token_type": "refresh",
        "user_id": session["user_id"],
        "uid": user["id"],
        "token_hash": session["token_hash"],
    })
    if id_is_session:
        row["id"] = session["id"]
    return row


def fake_fetch_one(sql, params=()):
    s = _norm(sql)

    if s.startswith("SELECT version()"):
        return {"version": "PostgreSQL 17.4 (fake)", "server_time": datetime.now(timezone.utc)}

    if "information_schema" in s:
        # Simula las migraciones 01 y 03 ya aplicadas.
        return {"user_columns": 4, "sessions_table": 1, "jwt_columns": 2}

    if s.startswith("INSERT INTO users"):
        if any(u["email"] == params[3] for u in USERS):
            raise UniqueViolation("duplicate key value violates unique constraint")
        row = {
            "id": _seq[0], "nombre": params[0], "apellido_paterno": params[1],
            "apellido_materno": params[2], "email": params[3],
            "password_hash": params[4], "role": "Usuario", "is_active": True,
            "created_at": datetime.now(timezone.utc), "last_login": None,
            "failed_attempts": 0, "locked_until": None,
        }
        _seq[0] += 1
        USERS.append(row)
        return row

    if s.startswith("INSERT INTO user_sessions"):
        # create_session: (token_hash, user_id, expires_at, ip, ua, jti)
        session = {
            "id": len(SESSIONS) + 1, "token_hash": params[0], "user_id": params[1],
            "expires_at": params[2], "revoked_at": None, "rotated_at": None,
            "replaced_by_hash": None, "jti": params[5] if len(params) > 5 else None,
        }
        SESSIONS.append(session)
        return {"id": session["id"], "expires_at": session["expires_at"]}

    if "FROM user_sessions s" in s and "WHERE s.id = %s" in s:
        for se in SESSIONS:
            if se["id"] == params[0]:
                return _session_row(se)
        return None

    if "FROM user_sessions s" in s and "WHERE s.token_hash = %s" in s:
        for se in SESSIONS:
            if se["token_hash"] == params[0]:
                # La consulta de /refresh selecciona `s.id, s.user_id`.
                return _session_row(se, id_is_session=("s.id, s.user_id" in s))
        return None

    if "FROM users WHERE LOWER(email)" in s:
        for u in USERS:
            if u["email"] == params[0]:
                return dict(u)
        return None

    if "FROM users WHERE id" in s:
        for u in USERS:
            if u["id"] == params[0]:
                return dict(u)
        return None

    return None


def fake_execute(sql, params=()):
    s = _norm(sql)

    if s.startswith("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP, rotated_at"):
        # Rotación: replaced_by_hash, id
        for se in SESSIONS:
            if se["id"] == params[1]:
                se["revoked_at"] = datetime.now(timezone.utc)
                se["rotated_at"] = datetime.now(timezone.utc)
                se["replaced_by_hash"] = params[0]
        return 1

    if s.startswith("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE user_id"):
        changed = 0
        for se in SESSIONS:
            if se["user_id"] == params[0] and se["revoked_at"] is None:
                se["revoked_at"] = datetime.now(timezone.utc)
                changed += 1
        return changed

    if s.startswith("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE id"):
        for se in SESSIONS:
            if se["id"] == params[0] and se["revoked_at"] is None:
                se["revoked_at"] = datetime.now(timezone.utc)
                return 1
        return 0

    if s.startswith("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE token_hash"):
        for se in SESSIONS:
            if se["token_hash"] == params[0] and se["revoked_at"] is None:
                se["revoked_at"] = datetime.now(timezone.utc)
                return 1
        return 0

    if s.startswith("UPDATE user_sessions SET expires_at"):
        # extend: expires_at, jti, id
        for se in SESSIONS:
            if se["id"] == params[-1]:
                se["expires_at"] = params[0]
                se["jti"] = params[1]
        return 1

    if s.startswith("UPDATE user_sessions SET last_seen_at"):
        return 1

    if s.startswith("UPDATE users SET failed_attempts"):
        for u in USERS:
            if u["id"] == params[-1]:
                if len(params) >= 2 and isinstance(params[0], int):
                    u["failed_attempts"] = params[0]
                else:
                    u["failed_attempts"] = 0
                u["locked_until"] = None
        return 1

    if s.startswith("UPDATE clientes_servidos"):
        return 0
    if s.startswith("INSERT INTO clientes_servidos"):
        return 1
    return 0


A.fetch_one = fake_fetch_one
A.execute = fake_execute

client = A.app.test_client()

# ------------------------------------------------------------------------------
# Utilidades de prueba
# ------------------------------------------------------------------------------
PASSED, FAILED = [], []


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        print("  [OK]   %s" % label)
    else:
        FAILED.append(label)
        print("  [FAIL] %s  %s" % (label, detail))


def new_captcha(fmt="json"):
    """Pide un desafío y devuelve (captcha_id, respuesta). El CAPTCHA es de un solo uso."""
    r = client.get("/captcha?format=%s" % fmt)
    data = r.get_json()["data"]
    expr = re.search(r"\d+\s*[+\-]\s*\d+", data["question"]).group(0)
    return data["captcha_id"], int(eval(expr))


def login(email, password):
    cid, ans = new_captcha()
    return client.post("/login?format=json", json={
        "email": email, "password": password, "captcha_id": cid, "captcha_answer": ans})


EMAIL = "usuario.demo@library.local"
PASSWORD = "S3gura!2026"

print("\n=== 1. FORMATO DUAL (XML predeterminado / JSON) ===")
r = client.get("/health?format=json")
check("?format=json responde JSON", r.headers["Content-Type"].startswith("application/json"),
      r.headers.get("Content-Type"))

r = client.get("/health", headers={"Accept": "*/*"})
check("Accept: */* responde XML (predeterminado)",
      r.headers["Content-Type"].startswith("application/xml"), r.headers.get("Content-Type"))

r = client.get("/health", headers={"Accept": "application/json"})
check("Accept: application/json responde JSON",
      r.headers["Content-Type"].startswith("application/json"), r.headers.get("Content-Type"))

r = client.get("/")
check("XML contiene <links> (hipermedia)", "<links>" in r.get_data(as_text=True))

print("\n=== 2. HATEOAS (Nivel 3 de Richardson) ===")
r = client.get("/?format=json")
links = r.get_json()["_links"]
check("GET / publica los enlaces del API",
      all(k in links for k in ("register", "login", "logout", "session", "health",
                               "captcha", "docs", "refresh", "verify")), list(links))
check("GET / anuncia el esquema de autenticación JWT",
      r.get_json()["data"]["authentication"]["type"] == "JWT")

print("\n=== 3. REGISTRO ===")
cid, ans = new_captcha()
r = client.post("/register?format=json", json={
    "nombre": "Fabián", "apellido_paterno": "Azaed", "apellido_materno": "Orta",
    "email": EMAIL, "password": PASSWORD, "captcha_id": cid, "captcha_answer": ans,
})
check("201 Created", r.status_code == 201, r.status_code)
body = r.get_json()
check("Devuelve encabezado Location", "Location" in r.headers, dict(r.headers))
check("No expone password_hash", "password_hash" not in str(body))
check("La contraseña quedó hasheada con bcrypt",
      USERS[0]["password_hash"].startswith("$2b$") or USERS[0]["password_hash"].startswith("$2a$"),
      USERS[0]["password_hash"][:12])
check("La contraseña NO se guarda en texto plano", PASSWORD not in USERS[0]["password_hash"])

cid, ans = new_captcha()
r = client.post("/register?format=json", json={
    "nombre": "Fabián", "apellido_paterno": "Azaed", "apellido_materno": "Orta",
    "email": EMAIL, "password": PASSWORD, "captcha_id": cid, "captcha_answer": ans,
})
check("409 al repetir el correo", r.status_code == 409, r.status_code)
check("Código EMAIL_ALREADY_EXISTS", r.get_json()["error"]["code"] == "EMAIL_ALREADY_EXISTS")

r = client.post("/register?format=json", json={
    "nombre": "X", "apellido_paterno": "Y", "apellido_materno": "Z",
    "email": "no-es-correo", "password": PASSWORD, "captcha_id": "x", "captcha_answer": 0,
})
check("400 con correo inválido", r.status_code == 400 and r.get_json()["error"]["code"] == "INVALID_EMAIL")

r = client.post("/register?format=json", json={
    "nombre": "X", "apellido_paterno": "Y", "apellido_materno": "Z",
    "email": "otro@library.local", "password": "123", "captcha_id": "x", "captcha_answer": 0,
})
check("400 con contraseña débil", r.status_code == 400 and r.get_json()["error"]["code"] == "WEAK_PASSWORD")

print("\n=== 4. CAPTCHA (firma HMAC, un solo uso) ===")
cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid, "captcha_answer": ans})
check("200 con CAPTCHA correcto", r.status_code == 200, r.get_json())

r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid, "captcha_answer": ans})
check("400 al reutilizar el mismo CAPTCHA (un solo uso)",
      r.status_code == 400 and r.get_json()["error"]["code"] == "CAPTCHA_ALREADY_USED",
      r.get_json().get("error", {}).get("code"))

cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid, "captcha_answer": ans + 999})
check("400 con respuesta incorrecta", r.status_code == 400 and r.get_json()["error"]["code"] == "INVALID_CAPTCHA")

cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid[:-4] + "0000", "captcha_answer": ans})
check("400 con firma HMAC manipulada",
      r.status_code == 400 and r.get_json()["error"]["code"] == "INVALID_CAPTCHA")

print("\n=== 5. LOGIN Y SESIÓN CON JWT (sin cookies) ===")
r = login(EMAIL, PASSWORD)
body = r.get_json()
check("200 login correcto", r.status_code == 200, r.status_code)
check("No emite Set-Cookie (sin cookies)", "Set-Cookie" not in r.headers, dict(r.headers))

session = body["data"]["session"]
access_token = session["access_token"]
refresh_token = session["refresh_token"]

check("Devuelve access_token", isinstance(access_token, str) and access_token.count(".") == 2,
      access_token[:30])
check("token_type = Bearer", session["token_type"] == "Bearer")
check("header = Authorization", session["header"] == "Authorization")
check("algorithm = HS256", session["algorithm"] == "HS256")
check("expires_in = 900 segundos (15 min)", session["expires_in"] == 900, session["expires_in"])
check("Devuelve refresh_token distinto del access token",
      isinstance(refresh_token, str) and refresh_token != access_token)
check("Indica el endpoint de refresco", session["refresh_endpoint"] == "/refresh")
check("Incluye _links con logout", "logout" in body["_links"])

# El access token es SIN ESTADO: no debe existir en la base de datos.
check("El access token NO se almacena en la BD (sin estado)",
      all(access_token != s["token_hash"] for s in SESSIONS))
check("El refresh token se guarda SOLO como SHA-256",
      len(SESSIONS[-1]["token_hash"]) == 64 and SESSIONS[-1]["token_hash"] == _sha256(refresh_token),
      SESSIONS[-1]["token_hash"][:16])
check("El refresh token en claro NO está en la BD",
      all(refresh_token != s["token_hash"] for s in SESSIONS))

h = {"Authorization": "Bearer %s" % access_token}
r = client.get("/session?format=json", headers=h)
check("200 en /session con Bearer", r.status_code == 200, r.status_code)
check("authenticated = true", r.get_json()["data"]["authenticated"] is True)
check("credential = jwt", r.get_json()["data"]["session"]["credential"] == "jwt")
check("El JWT viaja con sus reclamaciones (iss/aud/jti)",
      r.get_json()["data"]["jwt"]["iss"] == "library-login"
      and r.get_json()["data"]["jwt"]["aud"] == "library-api"
      and bool(r.get_json()["data"]["jwt"]["jti"]))

r = client.get("/session?format=json")
check("401 sin token", r.status_code == 401 and r.get_json()["error"]["code"] == "SESSION_REQUIRED")

r = client.get("/session?format=json", headers={"Authorization": "Bearer token-inventado"})
check("401 con token opaco inventado",
      r.status_code == 401 and r.get_json()["error"]["code"] == "SESSION_INVALID")

r = client.get("/users/%d?format=json" % USERS[0]["id"], headers=h)
check("200 en /users/<id> (recurso REST)", r.status_code == 200, r.status_code)
check("/users nunca expone password_hash", "password_hash" not in str(r.get_json()))

print("\n=== 6. LOGIN FALLIDO (anti-enumeración) ===")
cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": "incorrecta",
                                            "captcha_id": cid, "captcha_answer": ans})
check("401 con contraseña incorrecta",
      r.status_code == 401 and r.get_json()["error"]["code"] == "INVALID_CREDENTIALS")

cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": "no.existe@library.local", "password": "x",
                                            "captcha_id": cid, "captcha_answer": ans})
check("401 idéntico con correo inexistente (no revela si existe)",
      r.status_code == 401 and r.get_json()["error"]["code"] == "INVALID_CREDENTIALS")
check("El mensaje no confirma ni niega la existencia del correo",
      "no existe" not in r.get_json()["error"]["message"].lower())

print("\n=== 7. SEGURIDAD DEL JWT (manipulación del token) ===")
# 7.1 alg = none (token sin firma)
header_none = base64.urlsafe_b64encode(
    json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
payload_seg = access_token.split(".")[1]
r = client.get("/session?format=json",
               headers={"Authorization": "Bearer %s.%s." % (header_none, payload_seg)})
check("alg=none rechazado (ALGORITHM_NONE_REJECTED)",
      r.status_code == 401 and r.get_json()["error"]["code"] == "ALGORITHM_NONE_REJECTED",
      r.get_json().get("error", {}).get("code"))

# 7.2 firma manipulada
r = client.get("/session?format=json",
               headers={"Authorization": "Bearer %s" % (access_token[:-4] + "AAAA")})
check("firma manipulada rechazada (INVALID_SIGNATURE)",
      r.status_code == 401 and r.get_json()["error"]["code"] == "INVALID_SIGNATURE",
      r.get_json().get("error", {}).get("code"))

# 7.3 token expirado (se firma con el mismo secreto del servicio)
expired = jwt_utils.encode_jwt({
    "iss": A.JWT_ISSUER, "aud": A.JWT_AUDIENCE, "sub": str(USERS[0]["id"]),
    "jti": "expirado", "exp": int(time.time()) - 30, "nbf": int(time.time()) - 60,
}, A.JWT_SECRET)
r = client.get("/session?format=json", headers={"Authorization": "Bearer %s" % expired})
check("token expirado rechazado (TOKEN_EXPIRED)",
      r.status_code == 401 and r.get_json()["error"]["code"] == "TOKEN_EXPIRED",
      r.get_json().get("error", {}).get("code"))

# 7.4 emisor ajeno
forged = jwt_utils.encode_jwt({
    "iss": "otro-servicio", "aud": A.JWT_AUDIENCE, "sub": str(USERS[0]["id"]),
    "jti": "forged", "exp": int(time.time()) + 300,
}, A.JWT_SECRET)
r = client.get("/session?format=json", headers={"Authorization": "Bearer %s" % forged})
check("emisor ajeno rechazado (INVALID_ISSUER)",
      r.status_code == 401 and r.get_json()["error"]["code"] == "INVALID_ISSUER",
      r.get_json().get("error", {}).get("code"))

# 7.5 firmado con OTRO secreto (lo que haría un atacante que no conoce el secreto)
r = client.get("/session?format=json", headers={
    "Authorization": "Bearer %s" % jwt_utils.encode_jwt(
        {"iss": A.JWT_ISSUER, "aud": A.JWT_AUDIENCE, "sub": str(USERS[0]["id"]),
         "jti": "x", "exp": int(time.time()) + 300}, "secreto-del-atacante")})
check("token firmado con otro secreto rechazado",
      r.status_code == 401 and r.get_json()["error"]["code"] == "INVALID_SIGNATURE")

print("\n=== 8. REFRESH TOKEN (rotación y detección de reuso) ===")
r = login(EMAIL, PASSWORD)
session = r.get_json()["data"]["session"]
old_access, old_refresh = session["access_token"], session["refresh_token"]

r = client.post("/refresh?format=json", json={"refresh_token": old_refresh})
check("200 al canjear el refresh token", r.status_code == 200, r.get_json())
new_session = r.get_json()["data"]["session"]
new_access, new_refresh = new_session["access_token"], new_session["refresh_token"]
check("Devuelve un access token nuevo", new_access != old_access)
check("Rota el refresh token (uno nuevo)", new_refresh != old_refresh)
check("El access token nuevo es válido",
      client.get("/session?format=json",
                 headers={"Authorization": "Bearer %s" % new_access}).status_code == 200)

# Reuso del refresh token viejo -> se detecta el robo
r = client.post("/refresh?format=json", json={"refresh_token": old_refresh})
check("401 REFRESH_REUSED al reutilizar el token rotado",
      r.status_code == 401 and r.get_json()["error"]["code"] == "REFRESH_REUSED",
      r.get_json().get("error", {}).get("code"))
check("La detección de reuso revoca TODAS las sesiones de la cuenta",
      all(s["revoked_at"] is not None for s in SESSIONS))

r = client.post("/refresh?format=json", json={"refresh_token": "no-existe"})
check("401 REFRESH_INVALID con un refresh token inventado",
      r.status_code == 401 and r.get_json()["error"]["code"] == "REFRESH_INVALID")

r = client.post("/refresh?format=json", json={})
check("400 REFRESH_REQUIRED sin refresh_token",
      r.status_code == 400 and r.get_json()["error"]["code"] == "REFRESH_REQUIRED")

print("\n=== 9. VERIFICACIÓN SIN ESTADO (/verify) ===")
r = login(EMAIL, PASSWORD)
session = r.get_json()["data"]["session"]
h = {"Authorization": "Bearer %s" % session["access_token"]}

r = client.post("/verify?format=json", headers=h)
check("200 al verificar un token válido", r.status_code == 200, r.status_code)
check("Devuelve valid = true", r.get_json()["data"]["valid"] is True)
check("Devuelve las reclamaciones", r.get_json()["data"]["claims"]["aud"] == "library-api")

r = client.post("/verify?format=json", json={"token": "no-es-un-jwt"})
check("401 al verificar basura (MALFORMED_TOKEN)",
      r.status_code == 401 and r.get_json()["error"]["code"] == "MALFORMED_TOKEN")

print("\n=== 10. LOGOUT Y REVOCACIÓN ===")
r = client.post("/logout?format=json", headers=h)
check("200 al cerrar sesión", r.status_code == 200, r.status_code)
check("revoked = true", r.get_json()["data"]["revoked"] is True)

r = client.get("/session?format=json", headers=h)
check("401 al reutilizar el token tras logout",
      r.status_code == 401 and r.get_json()["error"]["code"] == "SESSION_INVALID",
      r.get_json().get("error", {}).get("code"))

print("\n=== 11. COMPATIBILIDAD CON EL TOKEN OPACO ANTERIOR ===")
legacy_token = "token-opaco-heredado-del-prompt-05"
SESSIONS.append({
    "id": len(SESSIONS) + 1, "token_hash": _sha256(legacy_token), "user_id": USERS[0]["id"],
    "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30), "revoked_at": None,
    "rotated_at": None, "replaced_by_hash": None, "jti": None,
})
r = client.get("/session?format=json", headers={"X-Session-Token": legacy_token})
check("200 con el header heredado X-Session-Token", r.status_code == 200, r.status_code)
check("credential = opaque (no rompe clientes anteriores)",
      r.get_json()["data"]["session"]["credential"] == "opaque")

print("\n=== 12. /health INFORMA EL ESQUEMA JWT ===")
r = client.get("/health?format=json")
jwt_block = r.get_json()["data"]["jwt"]
check("schema = ready (migraciones aplicadas)", r.get_json()["data"]["schema"] == "ready")
check("algorithm = HS256", jwt_block["algorithm"] == "HS256")
check("issuer = library-login", jwt_block["issuer"] == "library-login")
check("Nunca expone el secreto, solo su huella", "JWT_SECRET" not in str(r.get_json()))

print("\n" + "=" * 62)
print(" RESULTADO: %d pruebas OK, %d fallidas" % (len(PASSED), len(FAILED)))
if FAILED:
    for f in FAILED:
        print("   - FALLO: %s" % f)
print("=" * 62)
sys.exit(1 if FAILED else 0)

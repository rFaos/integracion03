"""
==============================================================================
PRUEBA DE HUMO DEL FLUJO DE AUTENTICACIÓN (sin PostgreSQL)
------------------------------------------------------------------------------
Reemplaza la capa de acceso a datos por un doble en memoria para poder
verificar el flujo completo: captcha -> register -> login -> session -> logout.

Ejecutar:
    ./venv/Scripts/python.exe tests/smoke_test.py
==============================================================================
"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as A
from psycopg.errors import UniqueViolation

# ------------------------------------------------------------------------------
# Doble en memoria de la capa de datos
# ------------------------------------------------------------------------------
USERS = []
SESSIONS = []
_seq = [1]

def _norm(sql):
    return " ".join(sql.split())


def fake_fetch_one(sql, params=()):
    s = _norm(sql)

    if s.startswith("SELECT version()"):
        return {"version": "PostgreSQL 16.0 (fake)", "server_time": datetime.now(timezone.utc)}

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

    if "FROM user_sessions s" in s:
        for se in SESSIONS:
            if se["token_hash"] == params[0]:
                user = next(u for u in USERS if u["id"] == se["user_id"])
                merged = dict(user)
                merged.update({
                    "session_id": se["id"], "expires_at": se["expires_at"],
                    "revoked_at": se["revoked_at"],
                })
                return merged
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

    if s.startswith("INSERT INTO user_sessions"):
        SESSIONS.append({
            "id": len(SESSIONS) + 1, "token_hash": params[0], "user_id": params[1],
            "expires_at": params[2], "revoked_at": None,
        })
        return 1

    if s.startswith("UPDATE user_sessions SET revoked_at"):
        for se in SESSIONS:
            if se["id"] == params[0]:
                se["revoked_at"] = datetime.now(timezone.utc)
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
check("GET / expone los 7 enlaces del API",
      all(k in links for k in ("register", "login", "logout", "session", "health", "captcha", "docs")),
      list(links))

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
      r.get_json()["error"]["code"])

cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid, "captcha_answer": ans + 999})
check("400 con respuesta incorrecta", r.status_code == 400 and r.get_json()["error"]["code"] == "INVALID_CAPTCHA")

cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid[:-4] + "0000", "captcha_answer": ans})
check("400 con firma HMAC manipulada",
      r.status_code == 400 and r.get_json()["error"]["code"] == "INVALID_CAPTCHA")

print("\n=== 5. LOGIN Y SESIÓN (sin cookies) ===")
cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid, "captcha_answer": ans})
body = r.get_json()
check("200 login correcto", r.status_code == 200, r.status_code)
check("No emite Set-Cookie (sin cookies)", "Set-Cookie" not in r.headers, dict(r.headers))
token = body["data"]["session"]["token"]
check("expires_in = 1800 segundos (30 min)", body["data"]["session"]["expires_in"] == 1800)
check("Indica el header X-Session-Token", body["data"]["session"]["header"] == "X-Session-Token")
check("Incluye _links con logout", "logout" in body["_links"])
check("El token NO se guarda en claro en la BD",
      all(token != s["token_hash"] for s in SESSIONS))
check("Solo se guarda el SHA-256 del token", len(SESSIONS[0]["token_hash"]) == 64,
      SESSIONS[0]["token_hash"])

h = {"X-Session-Token": token}
r = client.get("/session?format=json", headers=h)
check("200 en /session con token", r.status_code == 200, r.status_code)
check("authenticated = true", r.get_json()["data"]["authenticated"] is True)
check("remaining_seconds <= 1800", r.get_json()["data"]["session"]["remaining_seconds"] <= 1800)

r = client.get("/session?format=json")
check("401 sin token", r.status_code == 401 and r.get_json()["error"]["code"] == "SESSION_REQUIRED")

r = client.get("/session?format=json", headers={"X-Session-Token": "token-inventado"})
check("401 con token inválido", r.status_code == 401 and r.get_json()["error"]["code"] == "SESSION_INVALID")

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

print("\n=== 7. LOGOUT Y REVOCACIÓN ===")
r = client.post("/logout?format=json", headers=h)
check("200 al cerrar sesión", r.status_code == 200, r.status_code)
check("revoked = true", r.get_json()["data"]["revoked"] is True)

r = client.get("/session?format=json", headers=h)
check("401 al reutilizar el token tras logout",
      r.status_code == 401 and r.get_json()["error"]["code"] == "SESSION_INVALID", r.get_json())

print("\n=== 8. EXPIRACIÓN DE SESIÓN (30 min) ===")
cid, ans = new_captcha()
r = client.post("/login?format=json", json={"email": EMAIL, "password": PASSWORD,
                                            "captcha_id": cid, "captcha_answer": ans})
token2 = r.get_json()["data"]["session"]["token"]
SESSIONS[-1]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
r = client.get("/session?format=json", headers={"X-Session-Token": token2})
check("401 SESSION_EXPIRED al vencer los 30 minutos",
      r.status_code == 401 and r.get_json()["error"]["code"] == "SESSION_EXPIRED", r.get_json())

print("\n" + "=" * 62)
print(" RESULTADO: %d pruebas OK, %d fallidas" % (len(PASSED), len(FAILED)))
if FAILED:
    for f in FAILED:
        print("   - FALLO: %s" % f)
print("=" * 62)
sys.exit(1 if FAILED else 0)

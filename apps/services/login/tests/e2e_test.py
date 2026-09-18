"""
==============================================================================
PRUEBA END-TO-END CONTRA LA INSTANCIA DESPLEGADA
------------------------------------------------------------------------------
Valida el microservicio contra la base de datos real.

Ejecutar:
    python tests/e2e_test.py
    python tests/e2e_test.py http://localhost:5000

Nota: crea un usuario e2e.test.<timestamp>@library.local en la base de datos.
Se puede limpiar con:
    DELETE FROM users WHERE email LIKE 'e2e.test.%@library.local';
==============================================================================
"""
import json, os, re, sys, time
import urllib.request, urllib.error

B = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("BASE_URL", "http://34.51.29.27:5000")).rstrip("/")
PASSED, FAILED = [], []

def check(label, cond, detail=""):
    (PASSED if cond else FAILED).append(label)
    print(("  [OK]   " if cond else "  [FAIL] ") + label + ("" if cond else "   -> " + str(detail)[:220]))

def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"} if data else {}
    h.update(headers or {})
    r = urllib.request.Request(B + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()

def captcha():
    _, _, raw = req("GET", "/captcha?format=json")
    d = json.loads(raw)["data"]
    expr = re.search(r"\d+\s*[+\-]\s*\d+", d["question"]).group(0)
    return d["captcha_id"], int(eval(expr))

print("=== 0. HEALTH: PostgreSQL en la instancia ===")
s, h, raw = req("GET", "/health?format=json")
body = json.loads(raw)
check("200 y database=connected", s == 200 and body["data"]["database"] == "connected", body)
check("PostgreSQL 16.x", "16." in body["data"]["postgres_version"], body["data"].get("postgres_version"))

print("\n=== 1. USUARIO SEMBRADO (requiere sql/02_fix_seed_passwords.sql) ===")
cid, ans = captcha()
s, h, raw = req("POST", "/login?format=json", {
    "email": "usuario1@library.local", "password": "666",
    "captcha_id": cid, "captcha_answer": ans})
body = json.loads(raw)
check("usuario1@library.local / 666 inicia sesion", s == 200,
      "Si falla con INVALID_CREDENTIALS, ejecuta sql/02_fix_seed_passwords.sql "
      "(los hashes semilla originales eran un placeholder invalido).")
if s == 200:
    check("Token de sesion devuelto", isinstance(body["data"]["session"]["token"], str))
    check("expires_in = 1800", body["data"]["session"]["expires_in"] == 1800)
    check("No emite Set-Cookie", "Set-Cookie" not in h, list(h))

print("\n=== 2. REGISTRO contra PostgreSQL real ===")
EMAIL = "e2e.test.%d@library.local" % int(time.time())
PWD = "S3gura!2026"
cid, ans = captcha()
s, h, raw = req("POST", "/register?format=json", {
    "nombre": "Prueba", "apellido_paterno": "EndToEnd", "apellido_materno": "QA",
    "email": EMAIL, "password": PWD, "captcha_id": cid, "captcha_answer": ans})
body = json.loads(raw)
check("201 Created", s == 201, raw[:220])
check("Encabezado Location", "Location" in h, list(h))
check("No expone password_hash", "password_hash" not in raw)
uid = body["data"]["user"]["id"] if s == 201 else None
check("Devuelve el id del usuario", isinstance(uid, int), uid)
print("     -> usuario de prueba creado:", EMAIL, "| id =", uid)

cid, ans = captcha()
s, h, raw = req("POST", "/register?format=json", {
    "nombre": "Prueba", "apellido_paterno": "EndToEnd", "apellido_materno": "QA",
    "email": EMAIL, "password": PWD, "captcha_id": cid, "captcha_answer": ans})
check("409 al repetir el correo (UniqueViolation de PostgreSQL)",
      s == 409 and json.loads(raw)["error"]["code"] == "EMAIL_ALREADY_EXISTS", raw[:220])

print("\n=== 3. LOGIN del usuario nuevo ===")
cid, ans = captcha()
s, h, raw = req("POST", "/login?format=json", {
    "email": EMAIL, "password": PWD, "captcha_id": cid, "captcha_answer": ans})
body = json.loads(raw)
check("200 login correcto", s == 200, raw[:220])
token = body["data"]["session"]["token"] if s == 200 else ""
check("Incluye _links con logout", "logout" in body.get("_links", {}), body.get("_links"))

print("\n=== 4. SESION (sin cookies) ===")
s, h, raw = req("GET", "/session?format=json", headers={"X-Session-Token": token})
body = json.loads(raw)
check("200 con token", s == 200, raw[:200])
check("authenticated = true", body.get("data", {}).get("authenticated") is True)
check("remaining_seconds <= 1800", body["data"]["session"]["remaining_seconds"] <= 1800,
      body["data"]["session"].get("remaining_seconds"))

s, h, raw = req("GET", "/session?format=json")
check("401 sin token", s == 401 and json.loads(raw)["error"]["code"] == "SESSION_REQUIRED")

print("\n=== 5. RECURSO /users/<id> ===")
s, h, raw = req("GET", "/users/%s?format=json" % uid, headers={"X-Session-Token": token})
check("200 en /users/<id>", s == 200, raw[:200])
check("Nunca expone password_hash", "password_hash" not in raw)

print("\n=== 6. FORMATO XML (predeterminado) ===")
cid, ans = captcha()
s, h, raw = req("POST", "/login", {
    "email": EMAIL, "password": PWD, "captcha_id": cid, "captcha_answer": ans})
check("200 en XML", s == 200, raw[:200])
check("Content-Type application/xml", "application/xml" in h.get("Content-Type", ""), h.get("Content-Type"))
check("Devuelve <token> en XML", "<token>" in raw, raw[:300])
check("Incluye bloque <links>", "<links>" in raw)
token_xml = re.search(r"<token>([^<]+)</token>", raw)
token_xml = token_xml.group(1) if token_xml else ""

print("\n=== 7. LOGIN FALLIDO (anti-enumeracion) ===")
cid, ans = captcha()
s, h, raw = req("POST", "/login?format=json", {
    "email": EMAIL, "password": "incorrecta", "captcha_id": cid, "captcha_answer": ans})
check("401 con contrasena incorrecta",
      s == 401 and json.loads(raw)["error"]["code"] == "INVALID_CREDENTIALS", raw[:200])

cid, ans = captcha()
s, h, raw = req("POST", "/login?format=json", {
    "email": "no.existe.%d@library.local" % int(time.time()), "password": "x",
    "captcha_id": cid, "captcha_answer": ans})
check("401 identico con correo inexistente (no revela existencia)",
      s == 401 and json.loads(raw)["error"]["code"] == "INVALID_CREDENTIALS", raw[:200])

print("\n=== 8. LOGOUT Y REVOCACION ===")
s, h, raw = req("POST", "/logout?format=json", headers={"X-Session-Token": token})
check("200 al cerrar sesion", s == 200 and json.loads(raw)["data"]["revoked"] is True, raw[:200])
s, h, raw = req("GET", "/session?format=json", headers={"X-Session-Token": token})
check("401 al reutilizar el token tras logout",
      s == 401 and json.loads(raw)["error"]["code"] == "SESSION_INVALID", raw[:200])

if token_xml:
    s, h, raw = req("GET", "/session?format=json", headers={"X-Session-Token": token_xml})
    check("La sesion creada por XML tambien es valida (200)", s == 200, raw[:200])

print("\n=== 9. CAPTCHA: un solo uso ===")
cid, ans = captcha()
req("POST", "/login?format=json", {"email": EMAIL, "password": PWD, "captcha_id": cid, "captcha_answer": ans})
s, h, raw = req("POST", "/login?format=json", {"email": EMAIL, "password": PWD, "captcha_id": cid, "captcha_answer": ans})
check("400 CAPTCHA_ALREADY_USED al reutilizarlo",
      s == 400 and json.loads(raw)["error"]["code"] == "CAPTCHA_ALREADY_USED", raw[:200])

print("\n" + "=" * 64)
print(" RESULTADO CONTRA LA INSTANCIA: %d OK, %d fallidas" % (len(PASSED), len(FAILED)))
for f in FAILED:
    print("   - FALLO:", f)
print("=" * 64)
print(" Usuario de prueba creado en la BD: %s" % EMAIL)
sys.exit(1 if FAILED else 0)

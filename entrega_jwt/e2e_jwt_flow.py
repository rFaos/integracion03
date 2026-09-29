"""
==============================================================================
PRUEBA END-TO-END DEL FLUJO JWT (login 5000  <->  libros 5001)
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504) - UDEM SC-2236

QUE HACE
--------
Ejecuta el recorrido completo del nuevo requerimiento contra los dos
microservicios REALES (con PostgreSQL) y deja constancia literal de lo que se
envia y lo que se recibe, encabezado por encabezado:

    1.  GET  /books                      -> publico, sin token
    2.  POST /books                      -> SIN token: 401 + WWW-Authenticate
    3.  POST /books  (?format=xml)       -> SIN token: el 401 tambien en XML
    4.  GET  /captcha + POST /register   -> alta de un usuario de prueba
    5.  POST /login                      -> access_token (JWT) + refresh_token
    6.  inspeccion del JWT               -> header / payload / firma
    7.  POST /books                      -> CON token: 201
    8.  GET  /books/{isbn}               -> publico
    9.  PUT  /books/{isbn}               -> CON token: 200
    10. PATCH /books/{isbn}              -> CON token: 200
    11. POST /books (alias /api/book/insert) -> CON token: 201 (el alias tambien esta cubierto)
    12. GET  /session                    -> CON token: 200
    13. POST /refresh                    -> rotacion de tokens
    14. POST /refresh (token viejo)      -> 401 REFRESH_REUSED
    15. POST /books con token alg=none   -> 401
    16. POST /books con firma ajena      -> 401
    17. POST /books con token expirado   -> 401
    18. DELETE /books/{isbn}             -> CON token: 200
    19. POST /logout + GET /session      -> 200 y luego 401

USO
---
    # con los dos servicios levantados (login:5000, books:5001)
    python entrega_jwt/e2e_jwt_flow.py

SALIDAS
-------
    entrega_jwt/evidencia_e2e.txt     bitacora legible (evidencia cruda)
    entrega_jwt/flujo_e2e.json        los mismos intercambios, en JSON
==============================================================================
"""

import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import socket
import sys
import time
import urllib.parse

LOGIN_BASE = os.environ.get("LOGIN_BASE", "http://localhost:5000")
BOOKS_BASE = os.environ.get("BOOKS_BASE", "http://localhost:5001")

# Secreto compartido: se lee del .env del servicio de login para poder FABRICAR
# a proposito los tokens manipulados (alg=none, firma ajena, expirado) y
# demostrar que el servicio de libros los rechaza.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JWT_SECRET = None
JWT_ISSUER = "library-login"
JWT_AUDIENCE = "library-api"
_env_path = os.path.join(ROOT, "apps", "services", "login", ".env")
if os.path.exists(_env_path):
    for _line in open(_env_path, encoding="utf-8"):
        if _line.startswith("JWT_SECRET="):
            JWT_SECRET = _line.split("=", 1)[1].strip()
        elif _line.startswith("JWT_ISSUER="):
            JWT_ISSUER = _line.split("=", 1)[1].strip()
        elif _line.startswith("JWT_AUDIENCE="):
            JWT_AUDIENCE = _line.split("=", 1)[1].strip()

OUT_DIR = os.path.join(ROOT, "entrega_jwt")
os.makedirs(OUT_DIR, exist_ok=True)

EXCHANGES = []
LOG_LINES = []
PASSED, FAILED = [], []


# ------------------------------------------------------------------------------
# Registro
# ------------------------------------------------------------------------------
def log(line=""):
    print(line)
    LOG_LINES.append(line)


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        log("  [OK]   %s" % label)
    else:
        FAILED.append(label)
        log("  [FALLO] %s   %s" % (label, detail))


def banner(title):
    log("")
    log("=" * 78)
    log(" " + title)
    log("=" * 78)


# ------------------------------------------------------------------------------
# Cliente HTTP crudo (http.client) para poder volcar el intercambio completo
# ------------------------------------------------------------------------------
def call(base_url, method, path, headers=None, body=None, raw_body=None, note="", quiet=False):
    parsed = urllib.parse.urlsplit(base_url)
    target = path
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=15)

    send_headers = dict(headers or {})
    payload = None
    if raw_body is not None:
        payload = raw_body.encode("utf-8")
    elif body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        send_headers.setdefault("Content-Type", "application/json")
    if payload is not None:
        send_headers["Content-Length"] = str(len(payload))
    send_headers.setdefault("Accept", "application/json")

    conn.request(method, target, body=payload, headers=send_headers)
    resp = conn.getresponse()
    text = resp.read().decode("utf-8", "replace")
    resp_headers = [(k, v) for k, v in resp.getheaders()]
    status = resp.status
    conn.close()

    exchange = {
        "note": note,
        "request": {
            "method": method,
            "url": base_url + target,
            "headers": send_headers,
            "body": (json.loads(payload.decode("utf-8")) if payload and
                     send_headers.get("Content-Type", "").startswith("application/json")
                     else (payload.decode("utf-8") if payload else None)),
        },
        "response": {
            "status": status,
            "headers": resp_headers,
            "body": text,
        },
    }

    if quiet:
        try:
            parsed_body = json.loads(text)
        except Exception:
            parsed_body = {"raw": text}
        return status, dict(resp_headers), parsed_body, text

    EXCHANGES.append(exchange)

    # Volcado literal del intercambio en la bitacora.
    log("")
    log("-" * 78)
    log("  %s" % (note or "%s %s" % (method, path)))
    log("-" * 78)
    log("  >>> PETICION")
    log("  %s %s HTTP/1.1" % (method, target))
    for key, value in send_headers.items():
        shown = value
        if key.lower() == "authorization" and len(shown) > 60:
            shown = shown[:40] + "  ...[JWT truncado para el log]..." + shown[-18:]
        log("  %s: %s" % (key, shown))
    if payload:
        pretty = payload.decode("utf-8")
        try:
            pretty = json.dumps(json.loads(pretty), ensure_ascii=False, indent=2)
        except Exception:
            pass
        log("  " + pretty.replace("\n", "\n  "))
    log("")
    log("  <<< RESPUESTA  HTTP %d" % status)
    for key, value in resp_headers:
        log("  %s: %s" % (key, value))
    pretty = text
    try:
        pretty = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except Exception:
        pass
    log("  " + pretty.replace("\n", "\n  "))

    try:
        parsed_body = json.loads(text)
    except Exception:
        parsed_body = {"raw": text}
    return status, dict(resp_headers), parsed_body, text


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def error_code(payload):
    """Extrae el codigo de error del sobre de CUALQUIERA de los dos servicios.

    El servicio de login anida el codigo ({"error": {"code": ...}}); el de libros
    lo pone plano ({"error": "...", "code": ...}). Se soportan las dos formas.
    """
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("error"), dict):
        return payload["error"].get("code")
    return payload.get("code")


def make_token(payload, secret, alg="HS256", header_extra=None):
    header = {"alg": alg, "typ": "JWT"}
    header.update(header_extra or {})
    segments = [b64url(json.dumps(header, separators=(",", ":")).encode()),
                b64url(json.dumps(payload, separators=(",", ":")).encode())]
    signing_input = ".".join(segments)
    signature = b64url(hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest())
    return signing_input + "." + signature


def make_alg_none_token(payload):
    """Token con alg=none y FIRMA VACIA: el ataque clasico del RFC 7519."""
    header = b64url(json.dumps({"alg": "none", "typ": "JWT"}, separators=(",", ":")).encode())
    body = b64url(json.dumps(payload, separators=(",", ":")).encode())
    return "%s.%s." % (header, body)


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "desconocida"


# ==============================================================================
# EJECUCION
# ==============================================================================
banner("EVIDENCIA E2E - AUTORIZACION POR JWT EN LOS MICROSERVICIOS DE LA LIBRERIA")
log(" Fecha de la corrida : %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
log(" Host / instancia    : %s  (equipo: %s)" % (local_ip(), socket.gethostname()))
log(" Servicio de login   : %s" % LOGIN_BASE)
log(" Servicio de libros  : %s" % BOOKS_BASE)
log(" Secreto compartido  : %s" % (hashlib.sha256(JWT_SECRET.encode()).hexdigest()[:12]
                                  if JWT_SECRET else "NO CONFIGURADO"))

STAMP = str(int(time.time()))
EMAIL = "jwt.demo.%s@library.local" % STAMP
PASSWORD = "S3gura!2026"
ISBN = "PRUEBA-JWT-613504"
ISBN_ALIAS = "PRUEBA-ALIAS-613504"

# ------------------------------------------------------------------------------
banner("1 y 2. REGLA CLAVE: LA MISMA RUTA, DOS AUTORIZACIONES DISTINTAS")
# ------------------------------------------------------------------------------
status, headers, payload, _ = call(BOOKS_BASE, "GET", "/books?format=json", note=(
    "GET /books SIN token -> PUBLICO. Es la misma ruta que el POST protegido: "
    "por eso la proteccion se decide por METODO HTTP, no por ruta."))
check("GET /books sin token responde 200 (publico)", status == 200, status)

status, headers, payload, _ = call(BOOKS_BASE, "POST", "/books", body={
    "isbn": ISBN, "title": "Intento sin token", "publication_year": 2026,
    "price": 1.0, "format_id": 1, "category_id": 1,
}, note="POST /books SIN token -> PROTEGIDO. Debe responder 401 con WWW-Authenticate.")
check("POST /books sin token responde 401", status == 401, status)
check("Codigo TOKEN_REQUIRED", error_code(payload) == "TOKEN_REQUIRED", error_code(payload))
check("Cabecera WWW-Authenticate presente",
      any(k.lower() == "www-authenticate" for k in headers), headers)
check("El error incluye _links hacia el servicio de login",
      "_links" in payload and "login" in payload.get("_links", {}), payload.get("_links"))

status, headers, payload, _ = call(BOOKS_BASE, "POST", "/books?format=xml", body={
    "isbn": ISBN, "title": "Intento sin token", "publication_year": 2026,
    "price": 1.0, "format_id": 1, "category_id": 1,
}, note="POST /books?format=xml SIN token -> el 401 tambien se negocia a XML.")
check("El 401 sin token tambien responde en XML",
      status == 401 and "application/xml" in headers.get("Content-Type", ""), headers.get("Content-Type"))

# ------------------------------------------------------------------------------
banner("3. OBTENCION DEL TOKEN: CAPTCHA -> REGISTRO -> LOGIN")
# ------------------------------------------------------------------------------
status, _, payload, _ = call(LOGIN_BASE, "GET", "/captcha?format=json", note="GET /captcha (publico)")
question = payload["data"]["question"]
captcha_id = payload["data"]["captcha_id"]
captcha_answer = int(eval(re.search(r"\d+\s*[+\-]\s*\d+", question).group(0)))
log("")
log("  Desafio resuelto: '%s' -> respuesta %d" % (question, captcha_answer))
check("El servicio entrega un desafio CAPTCHA", bool(captcha_id))

status, _, payload, _ = call(LOGIN_BASE, "POST", "/register?format=json", body={
    "nombre": "Prueba", "apellido_paterno": "JWT", "apellido_materno": "Integracion",
    "email": EMAIL, "password": PASSWORD,
    "captcha_id": captcha_id, "captcha_answer": captcha_answer,
}, note="POST /register (usuario de prueba para la corrida)")
check("Registro 201", status == 201, (status, payload))

status, _, payload, _ = call(LOGIN_BASE, "GET", "/captcha?format=json", note="GET /captcha (nuevo desafio para el login)")
question = payload["data"]["question"]
captcha_id = payload["data"]["captcha_id"]
captcha_answer = int(eval(re.search(r"\d+\s*[+\-]\s*\d+", question).group(0)))

status, _, payload, _ = call(LOGIN_BASE, "POST", "/login?format=json", body={
    "email": EMAIL, "password": PASSWORD,
    "captcha_id": captcha_id, "captcha_answer": captcha_answer,
}, note="POST /login -> aqui nace el JWT (access_token) y el refresh_token")
check("Login 200", status == 200, (status, payload))

session = payload["data"]["session"]
ACCESS = session["access_token"]
REFRESH = session["refresh_token"]
check("Devuelve access_token JWT (3 segmentos)", ACCESS.count(".") == 2)
check("Devuelve refresh_token", bool(REFRESH) and REFRESH != ACCESS)
check("token_type = Bearer", session["token_type"] == "Bearer")
check("expires_in = %d s" % session["expires_in"], session["expires_in"] == 900)

# ------------------------------------------------------------------------------
banner("4. INSPECCION DEL JWT EMITIDO (header / payload / firma)")
# ------------------------------------------------------------------------------
head_seg, pay_seg, sig_seg = ACCESS.split(".")
def _decode(seg):
    return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)).decode())

log("")
log("  HEADER   : %s" % json.dumps(_decode(head_seg), ensure_ascii=False, sort_keys=True))
log("  PAYLOAD  : %s" % json.dumps(_decode(pay_seg), ensure_ascii=False, sort_keys=True))
log("  FIRMA    : %s  (%d caracteres base64url)" % (sig_seg[:32] + "...", len(sig_seg)))
log("  LONGITUD : %d caracteres" % len(ACCESS))
check("Header declara HS256", _decode(head_seg)["alg"] == "HS256")
check("Payload trae sub/sid/jti/iss/aud/exp",
      all(k in _decode(pay_seg) for k in ("sub", "sid", "jti", "iss", "aud", "exp")))
check("iss = %s" % JWT_ISSUER, _decode(pay_seg)["iss"] == JWT_ISSUER)
check("aud = %s" % JWT_AUDIENCE, _decode(pay_seg)["aud"] == JWT_AUDIENCE)
check("Vigencia del access token = 15 min",
      840 <= _decode(pay_seg)["exp"] - _decode(pay_seg)["iat"] <= 900)

AUTH = {"Authorization": "Bearer %s" % ACCESS}

# Limpieza previa: hace la corrida repetible (si un intento anterior dejo los
# ISBN a medias, el alta devolveria 409 y ensuciaria la evidencia). Va en modo
# silencioso: no es parte de la evidencia del flujo.
for _isbn in (ISBN, ISBN_ALIAS):
    call(BOOKS_BASE, "DELETE", "/books/%s" % _isbn, headers=AUTH, quiet=True)

# ------------------------------------------------------------------------------
banner("5. ESCRITURA CON TOKEN: POST /books")
# ------------------------------------------------------------------------------
status, _, catalogs, _ = call(BOOKS_BASE, "GET", "/catalogs", note="GET /catalogs (publico: ids reales para el alta)")
format_id = catalogs["formats"][0]["id"]
category_id = catalogs["categories"][0]["id"]
author_id = catalogs["authors"][0]["id"]

status, _, payload, _ = call(BOOKS_BASE, "POST", "/books", headers=AUTH, body={
    "isbn": ISBN, "title": "PRUEBA JWT - 613504", "publication_year": 2026,
    "price": 499.0, "stock": 7, "format_id": format_id, "category_id": category_id,
    "author_ids": [author_id], "genre_ids": [],
}, note="POST /books CON Authorization: Bearer <JWT> -> 201")
check("POST /books con token responde 201", status == 201, (status, payload))

status, _, payload, _ = call(BOOKS_BASE, "GET", "/books/%s?format=json" % ISBN,
                             note="GET /books/{isbn} SIN token -> PUBLICO (misma ruta que el PUT protegido)")
check("GET /books/{isbn} sin token responde 200", status == 200, status)

status, _, payload, _ = call(BOOKS_BASE, "PUT", "/books/%s" % ISBN, headers=AUTH, body={
    "title": "PRUEBA JWT - 613504 (PUT completo)", "publication_year": 2026,
    "price": 599.0, "stock": 9, "format_id": format_id, "category_id": category_id,
    "author_ids": [author_id], "genre_ids": [],
}, note="PUT /books/{isbn} CON token -> 200 (reemplazo completo)")
check("PUT con token responde 200", status == 200, (status, payload))

status, _, payload, _ = call(BOOKS_BASE, "PATCH", "/books/%s" % ISBN, headers=AUTH, body={
    "price": 650.0, "stock": 11,
}, note="PATCH /books/{isbn} CON token -> 200 (modificacion parcial)")
check("PATCH con token responde 200", status == 200, (status, payload))

status, _, payload, _ = call(BOOKS_BASE, "POST", "/api/book/insert", headers=AUTH, body={
    "isbn": ISBN_ALIAS, "title": "PRUEBA JWT - ALIAS /api/book/insert", "publication_year": 2026,
    "price": 199.0, "stock": 3, "format_id": format_id, "category_id": category_id,
}, note="POST /api/book/insert CON token -> 201: el ALIAS de escritura tambien queda cubierto")
check("El alias /api/book/insert exige y acepta token", status == 201, (status, payload))

status, _, payload, _ = call(BOOKS_BASE, "POST", "/api/book/insert", body={
    "isbn": "PRUEBA-JWT-ALIAS-SIN-TOKEN", "title": "x", "publication_year": 2026,
    "price": 1.0, "format_id": format_id, "category_id": category_id,
}, note="POST /api/book/insert SIN token -> 401 (no hay puerta trasera por el alias)")
check("El alias de escritura sin token responde 401", status == 401, status)

# ------------------------------------------------------------------------------
banner("6. SESION Y REFRESCO")
# ------------------------------------------------------------------------------
status, _, payload, _ = call(LOGIN_BASE, "GET", "/session?format=json", headers=AUTH,
                             note="GET /session CON Bearer -> el servicio de login valida el JWT")
check("GET /session con Bearer responde 200", status == 200, (status, payload))
check("credential = jwt", payload["data"]["session"]["credential"] == "jwt")

status, _, payload, _ = call(LOGIN_BASE, "POST", "/verify?format=json", headers=AUTH,
                             note="POST /verify -> introspeccion sin estado del token")
check("POST /verify responde valid=true", status == 200 and payload["data"]["valid"] is True, (status, payload))

status, _, payload, _ = call(LOGIN_BASE, "POST", "/refresh?format=json",
                             body={"refresh_token": REFRESH},
                             note="POST /refresh -> rota el refresh token y emite un JWT nuevo")
check("POST /refresh responde 200", status == 200, (status, payload))
new_session = payload["data"]["session"]
ACCESS2, REFRESH2 = new_session["access_token"], new_session["refresh_token"]
check("Emite un access_token distinto", ACCESS2 != ACCESS)
check("Rota el refresh_token", REFRESH2 != REFRESH)

status, _, payload, _ = call(LOGIN_BASE, "POST", "/refresh?format=json",
                             body={"refresh_token": REFRESH},
                             note="POST /refresh REUTILIZANDO el token ya rotado -> deteccion de reuso")
check("Reuso del refresh token -> 401 REFRESH_REUSED",
      status == 401 and error_code(payload) == "REFRESH_REUSED", (status, error_code(payload)))

# ------------------------------------------------------------------------------
banner("7. ATAQUES CONTRA EL JWT (el servicio de libros los rechaza)")
# ------------------------------------------------------------------------------
claims = _decode(pay_seg)

# 7.1 alg = none (firma vacia)
none_token = make_alg_none_token(claims)
status, headers, payload, _ = call(BOOKS_BASE, "POST", "/books", headers={
    "Authorization": "Bearer %s" % none_token}, body={
    "isbn": "ATAQUE-NONE", "title": "x", "publication_year": 2026, "price": 1.0,
    "format_id": format_id, "category_id": category_id,
}, note="POST /books con token alg=none (sin firma) -> debe rechazarse")
check("alg=none rechazado (ALGORITHM_NONE_REJECTED)",
      status == 401 and error_code(payload) == "ALGORITHM_NONE_REJECTED",
      (status, error_code(payload)))

# 7.2 firma con otro secreto
forged = make_token(claims, "secreto-que-no-es-el-compartido")
status, headers, payload, _ = call(BOOKS_BASE, "POST", "/books", headers={
    "Authorization": "Bearer %s" % forged}, body={
    "isbn": "ATAQUE-FIRMA", "title": "x", "publication_year": 2026, "price": 1.0,
    "format_id": format_id, "category_id": category_id,
}, note="POST /books con token firmado con OTRO secreto -> firma invalida")
check("Firma ajena rechazada (INVALID_SIGNATURE)",
      status == 401 and error_code(payload) == "INVALID_SIGNATURE", (status, error_code(payload)))

# 7.3 token expirado
expired_claims = dict(claims)
expired_claims["exp"] = int(time.time()) - 60
expired_claims["iat"] = int(time.time()) - 600
expired_token = make_token(expired_claims, JWT_SECRET)
status, headers, payload, _ = call(BOOKS_BASE, "POST", "/books", headers={
    "Authorization": "Bearer %s" % expired_token}, body={
    "isbn": "ATAQUE-EXP", "title": "x", "publication_year": 2026, "price": 1.0,
    "format_id": format_id, "category_id": category_id,
}, note="POST /books con token EXPIRADO (firmado correctamente) -> debe rechazarse")
check("Token expirado rechazado (TOKEN_EXPIRED)",
      status == 401 and error_code(payload) == "TOKEN_EXPIRED", (status, error_code(payload)))

# 7.4 audiencia ajena
aud_claims = dict(claims)
aud_claims["aud"] = "otra-api"
status, headers, payload, _ = call(BOOKS_BASE, "POST", "/books", headers={
    "Authorization": "Bearer %s" % make_token(aud_claims, JWT_SECRET)}, body={
    "isbn": "ATAQUE-AUD", "title": "x", "publication_year": 2026, "price": 1.0,
    "format_id": format_id, "category_id": category_id,
}, note="POST /books con token de OTRA audiencia -> debe rechazarse")
check("Audiencia ajena rechazada (INVALID_AUDIENCE)",
      status == 401 and error_code(payload) == "INVALID_AUDIENCE", (status, error_code(payload)))

# 7.5 lectura publica sigue funcionando aunque el token sea basura
status, _, payload, _ = call(BOOKS_BASE, "GET", "/books?format=json", headers={
    "Authorization": "Bearer basura.invalida.token"},
    note="GET /books con token basura -> sigue siendo PUBLICO y responde 200 (el token no se exige para leer)")
check("La lectura publica no depende del token", status == 200, status)

# ------------------------------------------------------------------------------
banner("8. LIMPIEZA Y CIERRE DE SESION")
# ------------------------------------------------------------------------------
status, _, payload, _ = call(BOOKS_BASE, "DELETE", "/books/%s" % ISBN_ALIAS, headers=AUTH,
                             note="DELETE /books/{isbn} CON token -> 200 (limpieza del alias)")
check("DELETE con token responde 200", status == 200, (status, payload))

status, _, payload, _ = call(BOOKS_BASE, "DELETE", "/books/%s" % ISBN, headers=AUTH,
                             note="DELETE /books/{isbn} CON token -> 200")
check("DELETE del libro principal responde 200", status == 200, (status, payload))

status, _, payload, _ = call(BOOKS_BASE, "DELETE", "/books/%s" % ISBN,
                             note="DELETE /books/{isbn} SIN token -> 401")
check("DELETE sin token responde 401", status == 401, status)

status, _, payload, _ = call(LOGIN_BASE, "POST", "/logout?format=json", headers=AUTH,
                             note="POST /logout -> revoca la sesion del JWT")
check("Logout 200", status == 200, (status, payload))

status, _, payload, _ = call(LOGIN_BASE, "GET", "/session?format=json", headers=AUTH,
                             note="GET /session con el token ya revocado -> 401")
check("Tras el logout el token es rechazado por el servicio de login",
      status == 401 and error_code(payload) == "SESSION_INVALID", (status, error_code(payload)))

# ------------------------------------------------------------------------------
banner("RESULTADO")
# ------------------------------------------------------------------------------
log(" Aserciones correctas : %d" % len(PASSED))
log(" Aserciones fallidas  : %d" % len(FAILED))
for f in FAILED:
    log("   - %s" % f)
log("")
log(" Intercambios HTTP registrados: %d" % len(EXCHANGES))

with open(os.path.join(OUT_DIR, "evidencia_e2e.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG_LINES) + "\n")

with open(os.path.join(OUT_DIR, "flujo_e2e.json"), "w", encoding="utf-8") as fh:
    json.dump({
        "generado": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": socket.gethostname(),
        "ip": local_ip(),
        "login_base": LOGIN_BASE,
        "books_base": BOOKS_BASE,
        "jwt_fingerprint": hashlib.sha256(JWT_SECRET.encode()).hexdigest()[:12] if JWT_SECRET else None,
        "aserciones_ok": len(PASSED),
        "aserciones_fallidas": len(FAILED),
        "intercambios": EXCHANGES,
    }, fh, ensure_ascii=False, indent=2)

print("\nEvidencia escrita en:")
print("  %s" % os.path.join(OUT_DIR, "evidencia_e2e.txt"))
print("  %s" % os.path.join(OUT_DIR, "flujo_e2e.json"))
sys.exit(1 if FAILED else 0)

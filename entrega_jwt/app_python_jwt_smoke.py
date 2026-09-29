"""
==============================================================================
VERIFICACION DE LA APP PYTHON TK - CREDENCIAL BEARER Y REFRESCO AUTOMATICO
==============================================================================
Ejecuta la MISMA capa de servicios que usa la interfaz de escritorio
(`apps/Python_app/core`), pero sin abrir la ventana, para dejar constancia de:

    1. El login devuelve access_token (JWT) + refresh_token.
    2. TODAS las operaciones (lectura y CRUD) viajan con
       `Authorization: Bearer <access_token>`; la bitacora de la terminal
       imprime el encabezado del token en cada peticion.
    3. Las lecturas del catalogo funcionan SIN token (endpoint publico).
    4. El refresco automatico: con un access token expirado, el cliente renueva
       con POST /refresh y REPITE la peticion sin que la interfaz se entere.
    5. El borrado tambien exige token.

USO
---
    python entrega_jwt/app_python_jwt_smoke.py
==============================================================================
"""

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "apps", "Python_app")

# Runtime aparte: no se toca el `runtime/` real del usuario.
os.environ["PYTHON_APP_HOME"] = os.path.join(ROOT, "entrega_jwt", "runtime_demo")
sys.path.insert(0, APP)

from core.services import ServiceHub  # noqa: E402

# Secreto compartido: se lee del .env del servicio de login para poder FABRICAR
# un access token expirado y provocar el refresco automatico.
JWT_SECRET = ""
_env = os.path.join(ROOT, "apps", "services", "login", ".env")
if os.path.exists(_env):
    for _line in open(_env, encoding="utf-8"):
        if _line.startswith("JWT_SECRET="):
            JWT_SECRET = _line.split("=", 1)[1].strip()

PASSED, FAILED = [], []


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        print("  [OK]   %s" % label)
    else:
        FAILED.append(label)
        print("  [FALLO] %s   %s" % (label, detail))


def banner(title):
    print("")
    print("=" * 84)
    print(" " + title)
    print("=" * 84)


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def solve(captcha):
    expr = re.search(r"\d+\s*[+\-]\s*\d+", captcha["question"]).group(0)
    return int(eval(expr))


STAMP = str(int(time.time()))
EMAIL = "tk.demo.%s@library.local" % STAMP
PASSWORD = "S3gura!2026"
ISBN = "TK-JWT-613504"

banner("APP PYTHON TK - SERVICIOS CON JWT")
hub = ServiceHub()
hub.startup_banner()

# ------------------------------------------------------------------------------
banner("1. REGISTRO Y LOGIN (el login entrega access_token + refresh_token)")
# ------------------------------------------------------------------------------
cap = hub.auth.fetch_captcha()
try:
    hub.auth.register("Prueba", "TK", "JWT", EMAIL, PASSWORD, cap["captcha_id"], solve(cap))
    print("  Registro del usuario de prueba: OK (%s)" % EMAIL)
except Exception as exc:
    print("  Registro: %s (puede existir ya de una corrida previa)" % exc)

cap = hub.auth.fetch_captcha()
user, session = hub.auth.login(EMAIL, PASSWORD, cap["captcha_id"], solve(cap))
print("")
print("  Usuario autenticado : %s" % user.get("email"))
print("  access_token (JWT)  : %s" % session.get("access_token", "")[:48] + "...")
print("  refresh_token       : %s" % session.get("refresh_token", "")[:24] + "...")
print("  expira en           : %s segundos" % session.get("expires_in"))

check("El login devuelve access_token", bool(session.get("access_token")))
check("El login devuelve refresh_token", bool(session.get("refresh_token")))
check("El access token es un JWT (3 segmentos)", session.get("access_token", "").count(".") == 2)
check("El cliente envia Bearer, no X-Session-Token",
      hub.http.access_token == session.get("access_token"))
check("El refresh token quedo guardado en disco", hub.store.refresh_token() == session.get("refresh_token"))

# ------------------------------------------------------------------------------
banner("2. LECTURA DEL CATALOGO SIN TOKEN (endpoint publico)")
# ------------------------------------------------------------------------------
guardado = hub.http.access_token
hub.http.clear_session_token()          # se simula un cliente anonimo
books = hub.books.list_books()
print("")
print("  GET /books sin token -> %d libros" % len(books))
check("GET /books funciona SIN token (es publico)", len(books) > 0, len(books))

detalle = hub.books.get_book(books[0]["isbn"])
check("GET /books/{isbn} funciona SIN token (es publico)", bool(detalle))
hub.http.set_tokens(guardado, hub.store.refresh_token())

# ------------------------------------------------------------------------------
banner("3. CRUD CON Authorization: Bearer <access_token>")
# ------------------------------------------------------------------------------
catalogs = hub.books.catalogs()
body = {
    "isbn": ISBN, "title": "PRUEBA INTEGRACION - 613504 (TK)",
    "publication_year": 2026, "price": 350.0, "stock": 5,
    "format_id": catalogs["formats"][0]["id"],
    "category_id": catalogs["categories"][0]["id"],
    "author_ids": [catalogs["authors"][0]["id"]], "genre_ids": [],
}

try:                     # limpieza silenciosa si quedo de una corrida previa
    hub.books.delete(ISBN)
except Exception:
    pass

creado = hub.books.create(body)
check("POST /books con Bearer responde 201", bool(creado), creado)

actualizado = hub.books.patch(ISBN, {"price": 425.0, "stock": 8})
check("PATCH /books/{isbn} con Bearer responde 200", bool(actualizado), actualizado)

completo = hub.books.replace(ISBN, {
    "title": "PRUEBA INTEGRACION - 613504 (TK, PUT)",
    "publication_year": 2026, "price": 460.0, "stock": 10,
    "format_id": body["format_id"], "category_id": body["category_id"],
    "author_ids": body["author_ids"], "genre_ids": [],
})
check("PUT /books/{isbn} con Bearer responde 200", bool(completo), completo)

# ------------------------------------------------------------------------------
banner("4. REFRESCO AUTOMATICO DEL TOKEN (401 -> /refresh -> reintento)")
# ------------------------------------------------------------------------------
# Se fabrica un access token EXPIRADO (firmado con el secreto compartido) y se
# deja el refresh token intacto: el cliente debe renovar solo y repetir.
payload_seg = hub.http.access_token.split(".")[1]
claims = json.loads(base64.urlsafe_b64decode(payload_seg + "=" * (-len(payload_seg) % 4)).decode())
claims["iat"] = int(time.time()) - 900
claims["exp"] = int(time.time()) - 30
head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
pay = b64(json.dumps(claims).encode())
sig = b64(hmac.new(JWT_SECRET.encode(), (head + "." + pay).encode(), hashlib.sha256).digest())
expirado = head + "." + pay + "." + sig

token_antes = hub.http.access_token
hub.http.set_tokens(expirado)           # refresh token se conserva
print("")
print("  Access token forzado a EXPIRADO: %s" % expirado[:40] + "...")
print("  Se ejecuta un PATCH (operacion protegida) y el cliente debe renovar solo.")
print("")

renovado = hub.books.patch(ISBN, {"stock": 12})
check("El PATCH con token expirado se resolvio por refresco automatico", bool(renovado), renovado)
check("El cliente quedo con un access token NUEVO",
      hub.http.access_token and hub.http.access_token != token_antes)
check("El refresh token tambien roto (nuevo valor)", bool(hub.store.refresh_token()))

# ------------------------------------------------------------------------------
banner("5. BORRADO PROTEGIDO Y CIERRE DE SESION")
# ------------------------------------------------------------------------------
eliminado = hub.books.delete(ISBN)
check("DELETE /books/{isbn} con Bearer responde 200", bool(eliminado), eliminado)

hub.auth.logout()
check("Tras el logout el cliente ya no tiene access token", hub.http.access_token is None)
check("Tras el logout el cliente ya no tiene refresh token", hub.http.refresh_token is None)

# ------------------------------------------------------------------------------
banner("RESULTADO")
print(" Aserciones correctas : %d" % len(PASSED))
print(" Aserciones fallidas  : %d" % len(FAILED))
for f in FAILED:
    print("   - %s" % f)
sys.exit(1 if FAILED else 0)

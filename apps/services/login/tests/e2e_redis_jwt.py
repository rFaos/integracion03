"""
==============================================================================
E2E: REDIS + JWT DE EXTREMO A EXTREMO ENTRE LOS DOS MICROSERVICIOS
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236

QUE DEMUESTRA (y por que importa)
---------------------------------
Esta prueba levanta LOS DOS servicios reales (login y books) contra la base de
datos PostgreSQL real, y comparte UNA sola instancia de Redis simulada
(fakeredis) entre ambos. Es exactamente el escenario del enunciado:

    "todos los microservicios deben conectarse mediante una URL comun"

El unico elemento simulado es el servidor Redis (no hay uno instalado en esta
maquina); todo lo demas es real: Flask, PostgreSQL, bcrypt, CAPTCHA y JWT.

Los seis puntos que se comprueban:

  1. El access token dura 20 MINUTOS (exp - iat == 1200), como pide el ejercicio.
  2. La sesion y el refresh token quedan en Redis con TTL.
  3. La cache del catalogo funciona: la 2.a lectura de GET /books es un acierto.
  4. La escritura sin token responde 401 (no se puede modificar el catalogo).
  5. LA PRUEBA CLAVE: tras /logout, el jti entra en la lista de revocacion y el
     servicio de LIBROS (otro proceso, otro codigo) rechaza el token al instante
     con TOKEN_REVOKED. Esto es justo lo que el JWT sin estado no podia hacer.
  6. Politica de fallo ASIMETRICA: con Redis caido, las escrituras responden 503
     (fail-closed) y las lecturas siguen funcionando (fail-open).

Ejecutar (requiere PostgreSQL con la base `library` sembrada):
    python tests/e2e_redis_jwt.py
==============================================================================
"""

import importlib.util
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../login
SOAP = os.path.join(os.path.dirname(BASE), "soap")                   # .../soap

EMAIL = os.getenv("E2E_EMAIL", "usuario1@library.local")
PASSWORD = os.getenv("E2E_PASSWORD", "666")

FAILS = []
CHECKS = [0]


def check(name, condition, detail=""):
    CHECKS[0] += 1
    if not condition:
        FAILS.append(name)
    print("  [%s] %s%s" % ("OK  " if condition else "FALLO", name,
                           ("  -> " + str(detail)) if detail else ""))


def section(title):
    print("\n== %s ==" % title)


def error_code(resp):
    """Código de error, con las DOS convenciones del proyecto.

    El servicio de login anida el error (`{"error": {"code": ...}}`) y el de
    libros lo pone plano (`{"code": ...}`). Cada servicio conserva su formato;
    el test se adapta a los dos.
    """
    body = resp.get_json() or {}
    if isinstance(body.get("error"), dict):
        return body["error"].get("code")
    return body.get("code")


def load_module(name, path):
    """Carga un app.py con un nombre de modulo unico (los dos servicios se
    llaman igual: 'app', asi que hay que desambiguarlos)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def captcha_answer(question):
    """Resuelve '¿Cuánto es 4 - 1?' sin pedir ayuda al servidor."""
    match = re.search(r"(-?\d+)\s*([+\-])\s*(-?\d+)", question)
    if not match:
        return None
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    return a + b if op == "+" else a - b


def solve_captcha(login):
    """Pide un desafio y lo resuelve. Devuelve (captcha_id, respuesta)."""
    resp = login.get("/captcha?format=json")
    if resp.status_code != 200:
        return None, None
    data = resp.get_json()
    payload = data.get("data", data)
    return payload.get("captcha_id"), captcha_answer(payload.get("question", ""))


def do_login(login):
    """Login completo (CAPTCHA incluido). Devuelve el bloque `session` o None."""
    cid, answer = solve_captcha(login)
    if cid is None:
        return None, None
    resp = login.post("/login?format=json", json={
        "email": EMAIL, "password": PASSWORD,
        "captcha_id": cid, "captcha_answer": answer,
    })
    if resp.status_code != 200:
        return None, resp
    data = resp.get_json()
    payload = data.get("data", data)
    return payload.get("session"), resp


def main():
    print("E2E Redis + JWT  (login + books reales, PostgreSQL real, Redis simulado)")

    import fakeredis

    # --- Carga de los dos servicios ------------------------------------------
    sys.path.insert(0, BASE)
    login_app = load_module("login_service", os.path.join(BASE, "app.py"))

    # Se retiran los modulos compartidos para que el servicio de libros cargue
    # LOS SUYOS (es lo que ocurre en produccion: cada servicio lleva su copia).
    for mod in ("redis_layer", "jwt_auth"):
        sys.modules.pop(mod, None)
    sys.path.insert(0, SOAP)
    soap_mod = load_module("soap_service", os.path.join(SOAP, "app.py"))

    check("los dos servicios cargaron", bool(login_app.app) and bool(soap_mod.app))
    check("cada servicio tiene SU PROPIA capa Redis (copias deliberadas)",
          login_app.redis_layer is not soap_mod.redis_layer)

    # --- UNA sola instancia de Redis compartida -------------------------------
    shared = fakeredis.FakeRedis(decode_responses=True)
    login_app.redis_layer.set_client(shared)
    soap_mod.redis_layer.set_client(shared)
    check("Redis compartido y alcanzable desde ambos servicios",
          login_app.redis_layer.available(force=True) and soap_mod.redis_layer.available(force=True))

    login = login_app.app.test_client()
    books = soap_mod.app.test_client()

    # --- 1. Login: JWT de 20 minutos -----------------------------------------
    section("1. Login y vigencia de 20 minutos")
    session, resp = do_login(login)
    if session is None:
        print("     No se pudo iniciar sesion (HTTP %s)." % (resp.status_code if resp else "?"))
        if resp is not None:
            print("     Respuesta: %s" % resp.get_data(as_text=True)[:300])
        print("\n     Revisa que PostgreSQL tenga la base 'library' sembrada y que")
        print("     E2E_EMAIL / E2E_PASSWORD sean correctos.")
        return 1

    access = session["access_token"]
    check("login devuelve access_token (JWT)", bool(access))
    check("expires_in == 1200 s (20 minutos)", session["expires_in"] == 1200,
          "expires_in=%s" % session["expires_in"])

    claims = login_app.jwt_utils.decode_jwt(
        access, login_app.JWT_SECRET, algorithms=("HS256",),
        issuer=login_app.JWT_ISSUER, audience=login_app.JWT_AUDIENCE)
    check("el algoritmo es HS256", claims["iss"] == login_app.JWT_ISSUER)
    check("exp - iat == 1200 s (20 min exactos)", claims["exp"] - claims["iat"] == 1200,
          "exp-iat=%s" % (claims["exp"] - claims["iat"]))
    check("el token trae 'jti' (para poder revocarlo)", bool(claims.get("jti")))
    check("el token trae 'sub' y 'role'", bool(claims.get("sub")) and "role" in claims,
          "sub=%s role=%s" % (claims.get("sub"), claims.get("role")))
    check("el token trae 'role_id' (lo exige el enunciado)",
          claims.get("role_id") is not None, "role_id=%s" % claims.get("role_id"))
    jti = claims["jti"]

    # --- 2. La sesion vive en Redis ------------------------------------------
    section("2. Sesion y refresh token en Redis")
    sid = claims.get("sid")
    check("la sesion esta en Redis (session:<sid>)", shared.exists("session:%s" % sid) == 1)
    refresh = session.get("refresh_token")
    import hashlib
    sha = hashlib.sha256(refresh.encode()).hexdigest()
    check("el refresh esta en Redis (refresh:<sha256>)", shared.exists("refresh:%s" % sha) == 1)
    check("el refresh NO se guarda en claro en Redis", not shared.exists("refresh:%s" % refresh))
    check("el jti aun NO esta revocado", not shared.exists("jwt:revoked:%s" % jti))

    # --- 3. Cache del catalogo -----------------------------------------------
    section("3. Cache del catalogo (GET /books)")
    for key in shared.scan_iter(match="books:*"):
        shared.delete(key)
    first = books.get("/books")
    check("GET /books responde 200", first.status_code == 200, "HTTP %s" % first.status_code)
    cached_keys = list(shared.scan_iter(match="books:list:*"))
    check("la respuesta quedo cacheada como books:list:<filtros>",
          len(cached_keys) >= 1, cached_keys)

    second = books.get("/books")
    body = second.get_json() or {}
    check("la 2.a lectura es un acierto de cache", body.get("cache") == "hit",
          "cache=%s" % body.get("cache"))

    # --- 4. Escritura protegida ----------------------------------------------
    section("4. Escritura sin token -> 401")
    no_token = books.post("/books", json={"title": "X"})
    check("POST /books sin Authorization responde 401", no_token.status_code == 401,
          "HTTP %s" % no_token.status_code)
    check("el motivo es TOKEN_REQUIRED", error_code(no_token) == "TOKEN_REQUIRED",
          "code=%s" % error_code(no_token))

    with_token = books.post("/books", json={"title": "X"},
                            headers={"Authorization": "Bearer " + access})
    check("POST /books CON token ya no es 401 (el guardián lo dejo pasar)",
          with_token.status_code != 401, "HTTP %s" % with_token.status_code)

    # --- 5. LA PRUEBA CLAVE: revocacion compartida ---------------------------
    section("5. Revocacion compartida: /logout surte efecto en el OTRO servicio")
    out = login.post("/logout?format=json", headers={"Authorization": "Bearer " + access})
    check("/logout responde 200", out.status_code == 200, "HTTP %s" % out.status_code)
    out_data = (out.get_json() or {}).get("data", {})
    check("/logout confirma revoked_in_redis", out_data.get("revoked_in_redis") is True,
          out_data)
    check("el jti quedo en jwt:revoked:<jti>", shared.exists("jwt:revoked:%s" % jti) == 1)

    blocked = books.post("/books", json={"title": "X"},
                         headers={"Authorization": "Bearer " + access})
    code = error_code(blocked)
    check("el servicio de LIBROS rechaza el token revocado con 401", blocked.status_code == 401,
          "HTTP %s" % blocked.status_code)
    check("el motivo es TOKEN_REVOKED", code == "TOKEN_REVOKED", "code=%s" % code)

    still = login.get("/session?format=json", headers={"Authorization": "Bearer " + access})
    still_code = error_code(still)
    check("el propio login tambien lo rechaza",
          still.status_code == 401 and still_code == "TOKEN_REVOKED",
          "HTTP %s code=%s" % (still.status_code, still_code))

    # --- 6. Politica de fallo asimetrica -------------------------------------
    section("6. Redis caido: fail-closed en escritura, fail-open en lectura")
    # Un token NUEVO y vigente (el anterior ya esta revocado).
    session2, _ = do_login(login)
    access2 = session2["access_token"] if session2 else None
    check("se obtuvo un token nuevo para la prueba de caida", bool(access2))

    # Se "desconecta" Redis SOLO para el servicio de libros.
    soap_mod.redis_layer.set_client(None)
    soap_mod.redis_layer.REDIS_URL = ""
    check("el servicio de libros ve Redis como caido",
          soap_mod.redis_layer.available(force=True) is False)

    write_down = books.post("/books", json={"title": "X"},
                            headers={"Authorization": "Bearer " + access2})
    check("POST /books con Redis caido responde 503 (fail-CLOSED)",
          write_down.status_code == 503, "HTTP %s" % write_down.status_code)
    check("el codigo es REDIS_UNAVAILABLE", error_code(write_down) == "REDIS_UNAVAILABLE",
          "code=%s" % error_code(write_down))

    read_down = books.get("/books")
    check("GET /books con Redis caido NO es 503 (fail-OPEN, sigue sirviendo)",
          read_down.status_code != 503, "HTTP %s" % read_down.status_code)

    # --- Resultado ------------------------------------------------------------
    print("\n" + "=" * 66)
    if FAILS:
        print("RESULTADO: %d/%d OK, %d FALLARON:" % (CHECKS[0] - len(FAILS), CHECKS[0], len(FAILS)))
        for name in FAILS:
            print("   - %s" % name)
        return 1
    print("RESULTADO: %d/%d comprobaciones OK." % (CHECKS[0], CHECKS[0]))
    print("Redis compartido + JWT de 20 min + revocacion entre servicios: VERIFICADO.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

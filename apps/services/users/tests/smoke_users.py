"""
==============================================================================
SMOKE TEST DEL MICROSERVICIO DE USUARIOS
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236

QUE COMPRUEBA
-------------
La matriz completa de autorizacion, que es donde se concentran los requisitos:

  1. Sin token            -> 401 TOKEN_REQUIRED
  2. Token con firma mala -> 401
  3. Token valido pero rol Usuario en una lectura administrativa -> 403
  4. Token de Administrador -> 200
  5. CRUD completo: crear, leer, modificar, borrar
  6. Politica de contrasena aplicada al crear
  7. Un usuario normal NO puede leer el registro de otro (403)
  8. Token revocado (jwt:revoked:<jti>) -> 401 TOKEN_REVOKED
  9. Redis caido -> 503 (fail-closed), nunca "acceso concedido"

Los tokens se firman con el MISMO `jwt_utils.py` del servicio de login, no con
un firmador de juguete: si la verificacion de este servicio funciona, es porque
es interoperable con el emisor real.

Requiere PostgreSQL con la base `library` y la migracion 04 aplicada.
Ejecutar:
    python tests/smoke_users.py
==============================================================================
"""

import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.dirname(HERE)
LOGIN_DIR = os.path.join(os.path.dirname(USERS_DIR), "login")

sys.path.insert(0, USERS_DIR)

import fakeredis  # noqa: E402
import app as users_app  # noqa: E402

# El firmador REAL del proyecto (no una reimplementacion de prueba).
_spec = importlib.util.spec_from_file_location(
    "login_jwt_utils", os.path.join(LOGIN_DIR, "jwt_utils.py"))
jwt_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jwt_utils)

FAILS = []
CHECKS = [0]
EMAIL = "smoke.users.%d@library.local" % int(time.time())


def check(name, condition, detail=""):
    CHECKS[0] += 1
    if not condition:
        FAILS.append(name)
    print("  [%s] %s%s" % ("OK  " if condition else "FALLO", name,
                           ("  -> " + str(detail)) if detail else ""))


def section(title):
    print("\n== %s ==" % title)


def mint(role_id, user_id, jti, secret=None, tamper=False):
    """Firma un access token con el jwt_utils del login (el emisor real)."""
    now = int(time.time())
    payload = {
        "iss": users_app.JWT_ISSUER,
        "aud": users_app.JWT_AUDIENCE,
        "sub": str(user_id),
        "jti": jti,
        "typ": "access",
        "email": "quien.sea@library.local",
        "role": "Administrador" if role_id == users_app.ADMIN_ROLE_ID else "Usuario",
        "role_id": role_id,
        "iat": now, "nbf": now, "exp": now + 1200,
    }
    token = jwt_utils.encode_jwt(payload, secret or users_app.JWT_SECRET, algorithm="HS256")
    return token[:-3] + "xxx" if tamper else token


def auth(token):
    return {"Authorization": "Bearer " + token}


def main():
    print("SMOKE TEST - microservicio de usuarios")

    fake = fakeredis.FakeRedis(decode_responses=True)
    users_app.redis_layer.set_client(fake)

    client = users_app.app.test_client()

    admin_token = mint(1, 1, "jti-admin-1")
    user_token = mint(2, 2, "jti-user-2")

    # --- 1. Sonda -------------------------------------------------------------
    section("1. Sonda /health")
    resp = client.get("/health")
    data = (resp.get_json() or {}).get("data", {})
    check("GET /health responde 200", resp.status_code == 200, "HTTP %s" % resp.status_code)
    check("la base de datos esta conectada", data.get("database") == "connected")
    check("el esquema esta listo (migracion 04 aplicada)", data.get("schema") == "ready",
          "schema=%s hint=%s" % (data.get("schema"), data.get("migration_hint")))
    check("CORS no es '*'", "*" not in (data.get("cors_origins") or []),
          data.get("cors_origins"))

    # --- 2. Matriz de autorizacion -------------------------------------------
    section("2. Autorizacion")
    r = client.get("/users")
    check("sin token -> 401", r.status_code == 401, "HTTP %s" % r.status_code)
    check("el codigo es TOKEN_REQUIRED", (r.get_json() or {}).get("code") == "TOKEN_REQUIRED")

    r = client.get("/users", headers=auth(mint(1, 1, "jti-x", secret="secreto-equivocado")))
    check("firma invalida -> 401", r.status_code == 401, "HTTP %s" % r.status_code)

    r = client.get("/users", headers=auth(mint(1, 1, "jti-x", tamper=True)))
    check("token manipulado -> 401", r.status_code == 401, "HTTP %s" % r.status_code)

    r = client.get("/users", headers=auth(user_token))
    check("rol Usuario en lectura administrativa -> 403", r.status_code == 403,
          "HTTP %s code=%s" % (r.status_code, (r.get_json() or {}).get("code")))
    check("el codigo es FORBIDDEN_ROLE", (r.get_json() or {}).get("code") == "FORBIDDEN_ROLE")

    r = client.get("/users", headers=auth(admin_token))
    check("rol Administrador -> 200", r.status_code == 200, "HTTP %s" % r.status_code)
    check("la lista no expone password_hash",
          "password_hash" not in resp.get_data(as_text=True))

    # --- 3. CRUD --------------------------------------------------------------
    section("3. CRUD de usuarios")
    r = client.post("/users", json={"email": EMAIL, "password": "debil"}, headers=auth(admin_token))
    check("contrasena debil -> 400 WEAK_PASSWORD",
          r.status_code == 400 and (r.get_json() or {}).get("code") == "WEAK_PASSWORD",
          "HTTP %s" % r.status_code)

    r = client.post("/users", json={
        "nombre": "Smoke", "apellido_paterno": "Test", "apellido_materno": "UDEM",
        "email": EMAIL, "password": "S3gura!2026", "role_id": 2, "is_active": True,
    }, headers=auth(admin_token))
    body = r.get_json() or {}
    check("crear usuario -> 201", r.status_code == 201,
          "HTTP %s %s" % (r.status_code, body.get("code") or ""))
    if r.status_code != 201:
        return 1
    new_id = body["data"]["id"]
    check("la respuesta no incluye password_hash", "password_hash" not in resp.get_data(as_text=True))
    check("role_id se devuelve normalizado", body["data"]["role_id"] == 2)

    r = client.post("/users", json={"email": EMAIL, "password": "S3gura!2026"}, headers=auth(admin_token))
    check("correo duplicado -> 409", r.status_code == 409,
          "HTTP %s code=%s" % (r.status_code, (r.get_json() or {}).get("code")))

    r = client.get("/users/%d" % new_id, headers=auth(admin_token))
    check("leer por id -> 200", r.status_code == 200, "HTTP %s" % r.status_code)

    r = client.patch("/users/%d" % new_id, json={"nombre": "Renombrado"},
                     headers=auth(admin_token))
    check("PATCH parcial -> 200", r.status_code == 200, "HTTP %s" % r.status_code)
    check("el cambio se aplico", (r.get_json() or {})["data"]["nombre"] == "Renombrado")

    r = client.put("/users/%d" % new_id, json={"nombre": "Incompleto"}, headers=auth(admin_token))
    check("PUT incompleto -> 400 (reemplazo completo)",
          r.status_code == 400, "HTTP %s" % r.status_code)

    r = client.patch("/users/%d" % new_id, json={"role_id": 999}, headers=auth(admin_token))
    check("rol inexistente -> 400 INVALID_ROLE",
          r.status_code == 400 and (r.get_json() or {}).get("code") == "INVALID_ROLE",
          "HTTP %s" % r.status_code)

    # --- 4. Aislamiento entre usuarios ---------------------------------------
    section("4. Aislamiento: un usuario no ve a otro")
    r = client.get("/users/%d" % new_id, headers=auth(user_token))
    check("usuario normal leyendo a OTRO -> 403", r.status_code == 403, "HTTP %s" % r.status_code)

    r = client.get("/users/2", headers=auth(user_token))
    check("usuario normal leyendo SU propio registro -> 200", r.status_code == 200,
          "HTTP %s" % r.status_code)

    # --- 5. Revocacion compartida en Redis -----------------------------------
    section("5. Revocacion (jwt:revoked:<jti>)")
    fake.set("jwt:revoked:jti-admin-1", "1", ex=600)
    r = client.get("/users", headers=auth(admin_token))
    check("token revocado -> 401 TOKEN_REVOKED",
          r.status_code == 401 and (r.get_json() or {}).get("code") == "TOKEN_REVOKED",
          "HTTP %s code=%s" % (r.status_code, (r.get_json() or {}).get("code")))
    fake.delete("jwt:revoked:jti-admin-1")

    # --- 6. Politica de fallo ------------------------------------------------
    section("6. Redis caido (fail-closed)")
    users_app.redis_layer.set_client(None)
    users_app.redis_layer.REDIS_URL = ""
    r = client.get("/users", headers=auth(mint(1, 1, "jti-admin-2")))
    check("sin poder comprobar la revocacion -> 503", r.status_code == 503,
          "HTTP %s" % r.status_code)
    check("el codigo es REDIS_UNAVAILABLE",
          (r.get_json() or {}).get("code") == "REDIS_UNAVAILABLE")

    # --- Limpieza -------------------------------------------------------------
    users_app.redis_layer.set_client(fake)
    users_app.redis_layer.REDIS_URL = "redis://fake:6379/0"
    r = client.delete("/users/%d" % new_id, headers=auth(admin_token))
    check("limpieza: borrar el usuario de prueba -> 200", r.status_code == 200,
          "HTTP %s" % r.status_code)

    print("\n" + "=" * 62)
    if FAILS:
        print("RESULTADO: %d/%d OK, %d FALLARON:" % (CHECKS[0] - len(FAILS), CHECKS[0], len(FAILS)))
        for f in FAILS:
            print("   - %s" % f)
        return 1
    print("RESULTADO: %d/%d comprobaciones OK. Servicio de usuarios verificado." % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

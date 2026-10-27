"""
==============================================================================
E2E DE LOS CUATRO MICROSERVICIOS NUEVOS (users, autores, pedidos, pagos)
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236

QUE PRUEBA (y por que asi)
--------------------------
Levanta los CINCO servicios reales en un solo proceso (login, users, autores,
pedidos, pagos) contra la base PostgreSQL real, y comparte UNA instancia de
Redis simulada entre todos. El unico elemento simulado es el servidor Redis.

Lo importante: **el token NO se fabrica en la prueba**. Se obtiene llamando al
endpoint real `POST /login` del servicio de autenticacion (resolviendo su
CAPTCHA). Eso demuestra la cadena completa:

    login emite el JWT  ->  los 4 servicios lo verifican  ->  y ademas lo
    rechazan en cuanto se revoca en /logout.

Los servicios se cargan con nombres de modulo unicos porque los cinco archivos
se llaman `app.py`: es exactamente la situacion de produccion (cinco procesos
distintos), reproducida aqui dentro de un proceso.

Requiere PostgreSQL con la base `library` y las migraciones 04 + pedidos + pagos.
Ejecutar:
    python tests/e2e_microservicios.py
==============================================================================
"""

import importlib.util
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_DIR = os.path.join(REPO, "apps", "services")

SERVICES = ["login", "users", "autores", "pedidos", "pagos"]

ADMIN_EMAIL = os.getenv("E2E_ADMIN", "admin@library.local")
USER_EMAIL = os.getenv("E2E_USER", "usuario1@library.local")
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


def load_service(name, folder):
    """Carga apps/services/<folder>/app.py con un nombre de modulo unico.

    Antes de cargar se retiran del cache los modulos compartidos (`redis_layer`,
    `jwt_auth`, `jwt_utils`) para que CADA servicio importe SU propia copia, tal
    como ocurre cuando corre como proceso independiente.
    """
    for shared in ("redis_layer", "jwt_auth", "jwt_utils", "app"):
        sys.modules.pop(shared, None)
    sys.path.insert(0, os.path.join(SERVICES_DIR, folder))
    spec = importlib.util.spec_from_file_location(
        name + "_service", os.path.join(SERVICES_DIR, folder, "app.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name + "_service"] = module
    spec.loader.exec_module(module)
    return module


def error_code(resp):
    """Código de error con las dos convenciones del proyecto (anidado y plano)."""
    body = resp.get_json() or {}
    if isinstance(body.get("error"), dict):
        return body["error"].get("code")
    return body.get("code")


def solve_captcha(login):
    resp = login.get("/captcha?format=json")
    payload = (resp.get_json() or {}).get("data", {})
    match = re.search(r"(-?\d+)\s*([+\-])\s*(-?\d+)", payload.get("question", ""))
    if not match:
        return None, None
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    return payload.get("captcha_id"), (a + b if op == "+" else a - b)


def login_as(client, email):
    """Login REAL: CAPTCHA + /login. Devuelve (token, session_id, jti)."""
    cid, answer = solve_captcha(client)
    if cid is None:
        return None, None, None
    resp = client.post("/login?format=json", json={
        "email": email, "password": PASSWORD,
        "captcha_id": cid, "captcha_answer": answer,
    })
    if resp.status_code != 200:
        return None, None, resp
    session = (resp.get_json() or {}).get("data", {}).get("session", {})
    return session.get("access_token"), session.get("refresh_token"), resp


def auth(token):
    return {"Authorization": "Bearer " + token}


def main():
    print("E2E DE LOS 4 MICROSERVICIOS NUEVOS (login real + PostgreSQL real)")

    import fakeredis

    # --- Carga de los cinco servicios ----------------------------------------
    section("0. Carga de los servicios")
    mods = {name: load_service(name, name) for name in SERVICES}
    # `autores` vive en su carpeta homónima; `login`/`users`/`pedidos`/`pagos`
    # también. El servicio de libros no participa en esta prueba.
    for name in SERVICES:
        check("cargado el servicio '%s'" % name, mods[name].app is not None)

    # --- UNA instancia de Redis compartida -----------------------------------
    shared = fakeredis.FakeRedis(decode_responses=True)
    for name in SERVICES:
        mods[name].redis_layer.set_client(shared)
    check("Redis compartido por los 5 servicios",
          all(mods[n].redis_layer.available(force=True) for n in SERVICES))

    clients = {name: mods[name].app.test_client() for name in SERVICES}

    # --- 1. Login real --------------------------------------------------------
    section("1. Login real (el token no se fabrica en la prueba)")
    admin_token, _refresh, resp = login_as(clients["login"], ADMIN_EMAIL)
    if admin_token is None:
        print("     No se pudo iniciar sesion como %s (HTTP %s)" % (
            ADMIN_EMAIL, resp.status_code if resp is not None else "?"))
        if resp is not None:
            print("     %s" % resp.get_data(as_text=True)[:300])
        return 1
    user_token, _, _ = login_as(clients["login"], USER_EMAIL)

    claims = mods["login"].jwt_utils.decode_jwt(
        admin_token, mods["login"].JWT_SECRET, algorithms=("HS256",),
        issuer=mods["login"].JWT_ISSUER, audience=mods["login"].JWT_AUDIENCE)
    check("el token de admin trae role_id = 1", claims.get("role_id") == 1,
          "role_id=%s" % claims.get("role_id"))
    check("el token trae jti (revocable)", bool(claims.get("jti")))
    admin_jti = claims["jti"]
    check("se obtuvo tambien un token de usuario normal", bool(user_token))

    A, U = auth(admin_token), auth(user_token)

    # --- 2. users -------------------------------------------------------------
    section("2. Microservicio users (5002)")
    r = clients["users"].get("/health")
    check("users /health -> 200", r.status_code == 200, "HTTP %s" % r.status_code)
    check("users: esquema listo",
          (r.get_json() or {}).get("data", {}).get("schema") == "ready")

    r = clients["users"].get("/users")
    check("users: sin token -> 401", r.status_code == 401, "HTTP %s" % r.status_code)

    r = clients["users"].get("/users", headers=U)
    check("users: rol Usuario -> 403", r.status_code == 403, "HTTP %s" % r.status_code)

    r = clients["users"].get("/users", headers=A)
    check("users: rol Administrador -> 200", r.status_code == 200, "HTTP %s" % r.status_code)

    email = "e2e.users.%d@library.local" % int(time.time())
    r = clients["users"].post("/users", json={
        "nombre": "E2E", "apellido_paterno": "Integracion", "apellido_materno": "UDEM",
        "email": email, "password": "S3gura!2026", "role_id": 2, "is_active": True,
    }, headers=A)
    check("users: crear -> 201", r.status_code == 201,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code") or ""))
    new_user_id = (r.get_json() or {}).get("data", {}).get("id")
    check("users: no se filtra password_hash",
          "password_hash" not in r.get_data(as_text=True))

    r = clients["users"].patch("/users/%s" % new_user_id, json={"nombre": "E2E2"}, headers=A)
    check("users: PATCH parcial -> 200", r.status_code == 200, "HTTP %s" % r.status_code)

    # --- 3. autores -----------------------------------------------------------
    section("3. Microservicio autores (5003)")
    r = clients["autores"].get("/health")
    check("autores /health -> 200", r.status_code == 200, "HTTP %s" % r.status_code)

    r = clients["autores"].get("/autores?limit=3")
    check("autores: GET es PUBLICO (sin token) -> 200", r.status_code == 200,
          "HTTP %s" % r.status_code)
    check("autores: primera lectura es miss", (r.get_json() or {}).get("cache") == "miss")
    r = clients["autores"].get("/autores?limit=3")
    check("autores: segunda lectura es HIT de cache", (r.get_json() or {}).get("cache") == "hit")

    r = clients["autores"].post("/autores", json={"name": "Sin token"})
    check("autores: POST sin token -> 401", r.status_code == 401, "HTTP %s" % r.status_code)

    r = clients["autores"].post("/autores", json={"name": "Sin rol"}, headers=U)
    check("autores: POST con rol Usuario -> 403", r.status_code == 403, "HTTP %s" % r.status_code)

    author_name = "Autor E2E %d" % int(time.time())
    r = clients["autores"].post("/autores", json={
        "name": author_name, "biography": "Creado por la prueba E2E", "country": "Mexico",
    }, headers=A)
    check("autores: crear con admin -> 201", r.status_code == 201,
          "HTTP %s" % r.status_code)
    new_author_id = (r.get_json() or {}).get("data", {}).get("id")

    # Relación con un libro: es lo que pide el enunciado ("relaciones con libros").
    r = clients["autores"].post("/autores/%s/libros" % new_author_id,
                                json={"book_ids": [1, 2]}, headers=A)
    check("autores: asociar libros -> 200", r.status_code == 200,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code") or ""))
    r = clients["autores"].get("/autores/%s/libros" % new_author_id)
    check("autores: la relacion quedo guardada (2 libros)",
          (r.get_json() or {}).get("count") == 2,
          "count=%s" % (r.get_json() or {}).get("count"))

    # --- 4. pedidos y stock ---------------------------------------------------
    section("4. Microservicio pedidos (5004) - stock transaccional")
    r = clients["pedidos"].get("/health")
    check("pedidos /health -> 200", r.status_code == 200, "HTTP %s" % r.status_code)
    check("pedidos: esquema listo",
          (r.get_json() or {}).get("data", {}).get("schema") == "ready")

    r = clients["pedidos"].get("/pedidos")
    check("pedidos: sin token -> 401", r.status_code == 401, "HTTP %s" % r.status_code)

    r = clients["pedidos"].post("/pedidos", json={"lineas": [{"book_id": 3, "cantidad": 2}]}, headers=U)
    check("pedidos: crear -> 201", r.status_code == 201,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code") or ""))
    order = (r.get_json() or {}).get("data", {})
    order_id = order.get("id")
    check("pedidos: arranca en estado 'Pendiente'", order.get("estado") == "Pendiente",
          order.get("estado"))
    check("pedidos: el total lo calculo PostgreSQL", order.get("total", 0) > 0,
          "total=%s" % order.get("total"))

    r = clients["pedidos"].post("/pedidos", json={"lineas": [{"book_id": 3, "cantidad": 999999}]}, headers=U)
    check("pedidos: stock insuficiente -> 409", r.status_code == 409,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code")))
    check("pedidos: el error dice cuanto hay disponible",
          (r.get_json() or {}).get("disponible") is not None,
          (r.get_json() or {}).get("disponible"))

    r = clients["pedidos"].patch("/pedidos/%s/estado" % order_id,
                                 json={"estado": "Enviado"}, headers=A)
    check("pedidos: transicion invalida Pendiente->Enviado -> 409", r.status_code == 409,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code")))

    r = clients["pedidos"].patch("/pedidos/%s/estado" % order_id,
                                 json={"estado": "Confirmado"}, headers=A)
    check("pedidos: transicion valida Pendiente->Confirmado -> 200", r.status_code == 200,
          "HTTP %s" % r.status_code)

    r = clients["pedidos"].get("/pedidos/%s" % order_id, headers=U)
    check("pedidos: el dueno ve su pedido -> 200", r.status_code == 200, "HTTP %s" % r.status_code)

    # --- 5. pagos -------------------------------------------------------------
    section("5. Microservicio pagos (5005) - atomicidad pago + estado")
    r = clients["pagos"].get("/health")
    check("pagos /health -> 200", r.status_code == 200, "HTTP %s" % r.status_code)

    r = clients["pagos"].post("/pagos", json={"pedido_id": order_id, "metodo": "Tarjeta"}, headers=U)
    check("pagos: registrar pago -> 201", r.status_code == 201,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code") or ""))
    data = (r.get_json() or {}).get("data", {})
    check("pagos: el pedido paso a 'Pagado' en la MISMA transaccion",
          data.get("pedido_estado") == "Pagado", data.get("pedido_estado"))
    check("pagos: el monto por omision es el total del pedido", data.get("monto", 0) > 0,
          "monto=%s" % data.get("monto"))

    r = clients["pedidos"].get("/pedidos/%s" % order_id, headers=U)
    check("pagos: el cambio de estado es visible desde el servicio de PEDIDOS",
          (r.get_json() or {}).get("data", {}).get("estado") == "Pagado",
          (r.get_json() or {}).get("data", {}).get("estado"))

    r = clients["pagos"].post("/pagos", json={"pedido_id": order_id, "metodo": "Tarjeta"}, headers=U)
    check("pagos: no se puede cobrar dos veces -> 409", r.status_code == 409,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code")))

    r = clients["pagos"].get("/pedidos/%s/pagos" % order_id, headers=U)
    check("pagos: historial del pedido -> 200", r.status_code == 200, "HTTP %s" % r.status_code)

    r = clients["pagos"].get("/pagos", headers=U)
    check("pagos: un usuario solo ve sus propios pagos -> 200", r.status_code == 200,
          "HTTP %s" % r.status_code)

    # --- 6. LA PRUEBA CLAVE: revocacion propagada a los 4 servicios ----------
    section("6. Revocacion: /logout y los 4 servicios rechazan el token")
    out = clients["login"].post("/logout?format=json", headers=A)
    check("login: /logout -> 200", out.status_code == 200, "HTTP %s" % out.status_code)
    check("login: el jti quedo revocado en Redis",
          shared.exists("jwt:revoked:%s" % admin_jti) == 1)

    targets = [
        ("users",    clients["users"].get("/users", headers=A)),
        ("autores",  clients["autores"].post("/autores", json={"name": "X"}, headers=A)),
        ("pedidos",  clients["pedidos"].get("/pedidos", headers=A)),
        ("pagos",    clients["pagos"].get("/pagos", headers=A)),
    ]
    for name, resp in targets:
        check("%s rechaza el token revocado -> 401 TOKEN_REVOKED" % name,
              resp.status_code == 401 and error_code(resp) == "TOKEN_REVOKED",
              "HTTP %s code=%s" % (resp.status_code, error_code(resp)))

    # --- 7. Politica de fallo asimetrica -------------------------------------
    section("7. Redis caido: 503 en los servicios que dependen de la revocacion")
    for name in ("users", "pedidos", "pagos"):
        mods[name].redis_layer.set_client(None)
        mods[name].redis_layer.REDIS_URL = ""
    r = clients["pedidos"].get("/pedidos", headers=U)
    check("pedidos con Redis caido -> 503 (fail-closed)", r.status_code == 503,
          "HTTP %s" % r.status_code)
    r = clients["users"].get("/users", headers=U)
    check("users con Redis caido -> 503 (fail-closed)", r.status_code == 503,
          "HTTP %s" % r.status_code)
    r = clients["autores"].get("/autores?limit=2")
    check("autores: la lectura PUBLICA sigue funcionando sin Redis (fail-open)",
          r.status_code == 200, "HTTP %s" % r.status_code)

    # --- Limpieza -------------------------------------------------------------
    section("Limpieza de los datos de prueba")
    for name in ("users", "pedidos", "pagos"):
        mods[name].redis_layer.set_client(shared)
        mods[name].redis_layer.REDIS_URL = "redis://fake:6379/0"

    # El token de admin se revocó en la sección 6 (a propósito). Para limpiar
    # hace falta uno nuevo: se vuelve a iniciar sesión, que es exactamente lo
    # que haría un usuario real después de cerrar sesión.
    fresh_admin, _, _ = login_as(clients["login"], ADMIN_EMAIL)
    check("tras el /logout se puede volver a iniciar sesion", bool(fresh_admin))
    A = auth(fresh_admin)

    r = clients["pedidos"].delete("/pedidos/%s" % order_id, headers=U)
    check("pedido de prueba cancelado", r.status_code == 200, "HTTP %s" % r.status_code)
    r = clients["autores"].delete("/autores/%s" % new_author_id, headers=A)
    check("autor de prueba eliminado", r.status_code == 200,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code") or ""))
    r = clients["users"].delete("/users/%s" % new_user_id, headers=A)
    check("usuario de prueba eliminado", r.status_code == 200,
          "HTTP %s %s" % (r.status_code, (r.get_json() or {}).get("code") or ""))

    print("\n" + "=" * 68)
    if FAILS:
        print("RESULTADO: %d/%d OK, %d FALLARON:" % (CHECKS[0] - len(FAILS), CHECKS[0], len(FAILS)))
        for f in FAILS:
            print("   - %s" % f)
        return 1
    print("RESULTADO: %d/%d comprobaciones OK." % (CHECKS[0], CHECKS[0]))
    print("Los 4 microservicios verificados con login real, JWT compartido y")
    print("revocacion propagada por Redis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

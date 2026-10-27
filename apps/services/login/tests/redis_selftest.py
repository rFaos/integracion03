"""
==============================================================================
SELF-TEST DE LA CAPA REDIS (sin servidor: usa fakeredis)
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236

QUE COMPRUEBA (y por que estos casos y no otros)
------------------------------------------------
  1. Contrato de claves: los nombres EXACTOS que pide el enunciado
     (jwt:revoked:<jti>, books:list:<filtros>, books:<isbn>).
  2. Sesion y refresh con TTL: se guardan y se leen; el TTL se aplica.
  3. Revocacion: tras revoke_jti(), is_revoked() es True.
  4. Cache del catalogo: get/set y, sobre todo, que la INVALIDACION total
     borre listas y fichas individuales de una sola pasada.
  5. Normalizacion de la clave de lista: los filtros en distinto orden deben
     producir la MISMA clave (si no, el cache no acierta nunca).
  6. Politica de fallo ASIMETRICA, que es la trampa del enunciado:
       - cache  -> fail-OPEN   (devuelve None, la peticion sigue)
       - auth   -> fail-CLOSED (lanza RedisUnavailable, se deniega)
  7. mask_url() no filtra la contrasena.

Ejecutar:
    python tests/redis_selftest.py
==============================================================================
"""

import os
import sys

# Permite ejecutar el archivo desde cualquier directorio.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fakeredis  # noqa: E402

import redis_layer as rl  # noqa: E402

FAILS = []
CHECKS = [0]


def check(name, condition, detail=""):
    CHECKS[0] += 1
    mark = "OK  " if condition else "FALLO"
    if not condition:
        FAILS.append(name)
    print("  [%s] %s%s" % (mark, name, ("  -> " + detail) if detail else ""))


def section(title):
    print("\n== %s ==" % title)


def main():
    print("SELF-TEST redis_layer.py  (cliente inyectado: fakeredis)")

    # --- 0. Contrato de claves -------------------------------------------------
    section("0. Contrato de claves")
    check("prefijo de revocacion es 'jwt:revoked:'", rl.K_REVOKED == "jwt:revoked:")
    check("prefijo de lista es 'books:list:'", rl.K_BOOKS_LIST == "books:list:")
    check("prefijo de ficha es 'books:'", rl.K_BOOK == "books:")
    check("clave de ficha = books:<isbn> en mayusculas",
          rl.book_key("isbn-123") == "books:ISBN-123", rl.book_key("isbn-123"))

    # --- 1. Normalizacion de filtros ------------------------------------------
    section("1. Normalizacion de la clave de lista")
    a = rl.books_list_key({"autor": 1, "tema": 2})
    b = rl.books_list_key({"tema": 2, "autor": 1})
    check("filtros en distinto orden dan la MISMA clave", a == b, "%s == %s" % (a, b))
    check("sin filtros -> books:list:all", rl.books_list_key() == "books:list:all")
    check("los filtros vacios no ensucian la clave",
          rl.books_list_key({"autor": "", "tema": None}) == "books:list:all")

    # --- 2. Cliente falso ------------------------------------------------------
    fake = fakeredis.FakeRedis(decode_responses=True)
    rl.set_client(fake)
    check("Redis disponible con el cliente inyectado", rl.available(force=True))

    # --- 3. Sesion y refresh con TTL ------------------------------------------
    section("2. Sesion y refresh token")
    rl.save_session("42", {"user_id": 7, "role": "admin"})
    ses = rl.get_session("42")
    check("la sesion se guarda y se lee", ses == {"user_id": 7, "role": "admin"}, str(ses))
    check("la clave real es session:<sid>", fake.exists("session:42") == 1)
    ttl = fake.ttl("session:42")
    check("la sesion tiene TTL aplicado", 0 < ttl <= rl.REDIS_REFRESH_TTL, "ttl=%s" % ttl)

    rl.save_refresh("abc123hash", {"sid": 42})
    check("el refresh se guarda bajo refresh:<sha256>",
          fake.exists("refresh:abc123hash") == 1)
    check("get_refresh devuelve el contenido",
          rl.get_refresh("abc123hash") == {"sid": 42})

    rl.rotate_refresh("abc123hash", "def456hash", {"sid": 42})
    check("la rotacion borra el refresh viejo", fake.exists("refresh:abc123hash") == 0)
    check("la rotacion guarda el nuevo", fake.exists("refresh:def456hash") == 1)

    check("delete_session borra la clave", rl.delete_session("42") == 1)
    check("tras delete_session ya no existe", fake.exists("session:42") == 0)

    # --- 4. Revocacion de JWT --------------------------------------------------
    section("3. Lista de revocacion de JWT")
    rl.revoke_jti("jti-aaaa", ttl_seconds=900)
    check("la clave es jwt:revoked:<jti>", fake.exists("jwt:revoked:jti-aaaa") == 1)
    check("is_revoked() detecta el token revocado", rl.is_revoked("jti-aaaa") is True)
    check("is_revoked() es False para un jti limpio", rl.is_revoked("jti-bbbb") is False)
    check("el TTL de la revocacion es la vida restante del token",
          fake.ttl("jwt:revoked:jti-aaaa") == 900,
          "ttl=%s" % fake.ttl("jwt:revoked:jti-aaaa"))

    # --- 5. Cache del catalogo e invalidacion ---------------------------------
    section("4. Cache del catalogo e invalidacion")
    rl.cache_set(rl.books_list_key({"q": "rayuela"}), [{"isbn": "1", "titulo": "Rayuela"}], ttl=30)
    rl.cache_set(rl.book_key("1"), {"isbn": "1", "titulo": "Rayuela"}, ttl=30)
    check("la lista cacheada se lee",
          rl.cache_get("books:list:q=rayuela") == [{"isbn": "1", "titulo": "Rayuela"}])
    check("la ficha cacheada se lee",
          rl.cache_get("books:1") == {"isbn": "1", "titulo": "Rayuela"})
    check("el TTL del cache es corto", fake.ttl("books:1") <= rl.REDIS_CACHE_TTL)

    deleted = rl.invalidate_books()
    check("invalidate_books() borra lista y ficha de una pasada", deleted == 2, "borradas=%s" % deleted)
    check("la lista ya no esta en cache", rl.cache_get("books:list:q=rayuela") is None)
    check("la ficha ya no esta en cache", rl.cache_get("books:1") is None)

    # --- 6. Politica de fallo asimetrica --------------------------------------
    section("5. Politica de fallo (la trampa del enunciado)")
    rl.set_client(None)  # simula Redis caido
    # Forzar que available() no crea cliente y devuelve False.
    os.environ["REDIS_URL"] = ""
    rl.REDIS_URL = ""

    # fail-OPEN para el cache:
    check("cache_get con Redis caido devuelve None (fail-OPEN)", rl.cache_get("books:1") is None)
    check("cache_set con Redis caido no lanza (fail-OPEN)", rl.cache_set("k", 1) is False)
    check("invalidate_books con Redis caido no lanza (fail-OPEN)", rl.invalidate_books() == 0)

    # fail-CLOSED para la autorizacion:
    closed = False
    try:
        rl.is_revoked("jti-cccc")
    except rl.RedisUnavailable as exc:
        closed = (exc.status == 503)
    check("is_revoked con Redis caido LANZA RedisUnavailable (fail-CLOSED)", closed)
    check("la excepcion es 503, no 401", rl.RedisUnavailable().status == 503)

    closed = False
    try:
        rl.save_session("9", {"a": 1})
    except rl.RedisUnavailable:
        closed = True
    check("save_session con Redis caido LANZA (fail-CLOSED)", closed)

    # --- 7. La URL no filtra la contrasena ------------------------------------
    section("6. Higiene de secretos")
    masked = rl.mask_url("redis://:S3cr3t0!@10.0.0.5:6379/0")
    check("mask_url oculta la contrasena", "S3cr3t0" not in masked, masked)
    check("mask_url conserva host y base", "10.0.0.5:6379/0" in masked, masked)
    check("health() nunca expone la contrasena",
          "S3cr3t0" not in str(rl.health()))

    # --- Resultado -------------------------------------------------------------
    print("\n" + "=" * 62)
    if FAILS:
        print("RESULTADO: %d/%d comprobaciones OK, %d FALLARON:" % (CHECKS[0] - len(FAILS), CHECKS[0], len(FAILS)))
        for name in FAILS:
            print("   - %s" % name)
        return 1
    print("RESULTADO: %d/%d comprobaciones OK. Capa Redis verificada." % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

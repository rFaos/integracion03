"""
==============================================================================
REDIS LAYER - Capa compartida de estado: sesiones, revocacion JWT y cache
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236

QUE ES (Y QUE NO ES) ESTA "CAPA COMPARTIDA"
-------------------------------------------
El enunciado pide Redis como *capa compartida*. Aqui "compartido" NO significa
un paquete de Python importado por todos: cada microservicio se despliega por
separado (login, books, users, autores, pedidos, pagos) y no debe acoplarse al
repositorio de otro. Lo compartido es, exactamente como con el JWT:

    1. La INSTANCIA de Redis  -> una sola URL comun: REDIS_URL
    2. El CONTRATO de claves  -> los mismos prefijos y TTL en todos
    3. El CONTRATO de fallo   -> que pasa cuando Redis no responde

Por eso este archivo es una COPIA DELIBERADA en cada servicio (igual que
`jwt_auth.py` respecto de `jwt_utils.py`): mismo comportamiento, cero acople.
Si manana se cambia el motor de cache, se cambia en un archivo y se copia.

CONTRATO DE CLAVES (identico en todos los servicios)
----------------------------------------------------
    session:<sid>                 -> JSON de la sesion            (TTL = refresh)
    refresh:<sha256(refresh)>     -> JSON con sid/user_id         (TTL = refresh)
    jwt:revoked:<jti>             -> "1"                          (TTL = vida restante)
    books:list:<filtros>          -> JSON de la lista de libros   (TTL corto)
    books:<isbn>                  -> JSON del libro               (TTL corto)

POLITICA DE FALLO (la parte que suele cobrar el examen)
-------------------------------------------------------
El enunciado es explicito y ASIMETRICO:

    * Lecturas cacheadas  -> Redis es OPCIONAL.  Si Redis cae, se va a
      PostgreSQL y la peticion sigue funcionando (fail-OPEN).
    * Sesion, revocacion y autorizacion -> si Redis cae, se NIEGA el acceso
      (fail-CLOSED). Nunca se acepta un JWT sin poder comprobar su revocacion.

Implementado asi:
    cache_get/cache_set/cache_delete   -> degradan a None / no-op  (fail-open)
    is_revoked/save_session/...        -> lanzan RedisUnavailable  (fail-closed)
    y `is_revoked()` lanza en vez de devolver False: "no pude comprobar" NUNCA
    se confunde con "no esta revocado".

SEGURIDAD
---------
    * La contrasena viaja dentro de REDIS_URL (variable de entorno) y jamas se
      imprime: `mask_url()` la tapa para los logs y el endpoint /health.
    * No se guardan contrasenas ni tokens en claro en los logs.
    * Los TTL son coherentes entre servicios: los define el emisor (login) y
      los demas los heredan de la misma configuracion.
==============================================================================
"""

import json
import os
import threading
import time

try:
    import redis as _redis
except ImportError:  # pragma: no cover - entorno sin la dependencia instalada
    _redis = None


# ------------------------------------------------------------------------------
# 1. CONFIGURACION
# ------------------------------------------------------------------------------
# OJO (fallo real detectado en pruebas): este módulo se importa en la cabecera de
# `app.py`, ANTES de que app.py llegue a ejecutar `load_dotenv()`. Si aquí no se
# cargara el .env, REDIS_URL llegaría vacía y la capa creería que Redis no está
# configurado (y, con fail-closed, el login respondería 503 sin motivo). Por eso
# el módulo carga el .env por su cuenta; es idempotente.
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv()
except ImportError:  # pragma: no cover - dotenv es dependencia del servicio
    pass

REDIS_URL = (os.getenv("REDIS_URL") or "").strip()

# TTL en segundos. Coherentes con el emisor (login):
#   * refresh 7 dias  -> es el que manda para la vida de la sesion
#   * cache de catalogo -> TTL corto (el enunciado pide "TTL corto")
REDIS_REFRESH_TTL   = int(os.getenv("REDIS_REFRESH_TTL", str(7 * 86400)))
REDIS_CACHE_TTL     = int(os.getenv("REDIS_CACHE_TTL", "30"))
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.5"))
REDIS_KEY_PREFIX    = os.getenv("REDIS_KEY_PREFIX", "")

# Interruptor de la politica fail-closed. Se puede apagar SOLO en un entorno de
# practica donde todavia no haya Redis levantado, y queda documentado.
REDIS_REQUIRED_FOR_AUTH = os.getenv("REDIS_REQUIRED_FOR_AUTH", "true").lower() in ("true", "1", "yes")

# --- Prefijos del contrato compartido -----------------------------------------
K_SESSION = "session:"
K_REFRESH = "refresh:"
K_REVOKED = "jwt:revoked:"
K_BOOKS_LIST = "books:list:"
K_BOOK = "books:"


class RedisUnavailable(Exception):
    """Redis no responde y la operacion era de las que NO pueden degradarse.

    Quien la captura debe responder 503 (no 401): el problema es del servidor,
    no del cliente, y jamas debe traducirse a "acceso concedido".
    """

    def __init__(self, message="Redis no esta disponible para una operacion critica."):
        super().__init__(message)
        self.code = "REDIS_UNAVAILABLE"
        self.status = 503


# ------------------------------------------------------------------------------
# 2. CLIENTE (perezoso, con timeouts y reconexion)
# ------------------------------------------------------------------------------
_client = None
_client_lock = threading.Lock()
_last_ping = 0.0
_last_ping_ok = False
_PING_CACHE_SECONDS = 2.0

# Contadores simples para /health y para la evidencia (el enunciado pide metricas)
_metrics = {
    "ops": 0,
    "hits": 0,
    "misses": 0,
    "errors": 0,
    "revoked_hits": 0,
    "auth_denied_by_outage": 0,
    "auth_allowed_by_outage": 0,
}


def metrics():
    """Copia del contador de metricas (no expone el objeto mutable)."""
    return dict(_metrics)


def mask_url(url=None):
    """REDIS_URL sin la contrasena, para logs y /health. Nunca se loguea el secreto."""
    raw = url if url is not None else REDIS_URL
    if not raw:
        return "(sin configurar)"
    if "@" not in raw:
        return raw
    scheme, _, rest = raw.partition("://")
    creds, _, host = rest.rpartition("@")
    user, _, _pw = creds.partition(":")
    return "%s://%s:***@%s" % (scheme, user, host)


def get_client():
    """Devuelve el cliente Redis o None. No lanza: la decision es del llamador."""
    global _client
    if _client is not None:
        return _client
    if _redis is None or not REDIS_URL:
        return None
    with _client_lock:
        if _client is None:
            try:
                # from_url ya interpreta redis://:password@host:6379/0
                _client = _redis.Redis.from_url(
                    REDIS_URL,
                    socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
                    socket_timeout=REDIS_SOCKET_TIMEOUT,
                    health_check_interval=15,
                    retry_on_timeout=False,
                    decode_responses=True,
                )
            except Exception:
                _metrics["errors"] += 1
                return None
    return _client


def set_client(client):
    """Inyecta un cliente (pruebas con fakeredis). No usar en produccion."""
    global _client
    _client = client


def available(force=False):
    """True si Redis responde PING. Se cachea 2 s para no golpear en cada request."""
    global _last_ping, _last_ping_ok
    now = time.time()
    if not force and (now - _last_ping) < _PING_CACHE_SECONDS:
        return _last_ping_ok
    client = get_client()
    ok = False
    if client is not None:
        try:
            ok = bool(client.ping())
        except Exception:
            _metrics["errors"] += 1
            ok = False
    _last_ping, _last_ping_ok = now, ok
    return ok


def health():
    """Bloque para /health. Nunca incluye la contrasena."""
    ok = available(force=True)
    return {
        "configured": bool(REDIS_URL),
        "reachable": ok,
        "url": mask_url(),
        "required_for_auth": REDIS_REQUIRED_FOR_AUTH,
        "cache_ttl_seconds": REDIS_CACHE_TTL,
        "metrics": metrics(),
    }


def _key(name):
    return REDIS_KEY_PREFIX + name


# ------------------------------------------------------------------------------
# 3. SESIONES Y REFRESH TOKENS  (fail-CLOSED)
# ------------------------------------------------------------------------------
def _critical(operation):
    """Prepara una operacion critica: exige cliente y Redis vivo."""
    client = get_client()
    if client is None or not available():
        _metrics["errors"] += 1
        if REDIS_REQUIRED_FOR_AUTH:
            _metrics["auth_denied_by_outage"] += 1
            raise RedisUnavailable(
                "Redis no responde: '%s' no puede completarse sin poder comprobar "
                "la sesion. Se deniega por seguridad (fail-closed)." % operation
            )
        _metrics["auth_allowed_by_outage"] += 1
        return None
    return client


def save_session(session_id, data, ttl=None):
    """Guarda la sesion (JSON) con TTL. Lanza RedisUnavailable si Redis no responde."""
    client = _critical("save_session")
    if client is None:
        return False
    _metrics["ops"] += 1
    client.set(_key(K_SESSION + str(session_id)), json.dumps(data, default=str),
               ex=int(ttl or REDIS_REFRESH_TTL))
    return True


def get_session(session_id):
    """Devuelve el dict de la sesion, o None si no existe (ya expiro o se cerro)."""
    client = _critical("get_session")
    if client is None:
        return None
    _metrics["ops"] += 1
    raw = client.get(_key(K_SESSION + str(session_id)))
    if raw is None:
        _metrics["misses"] += 1
        return None
    _metrics["hits"] += 1
    return json.loads(raw)


def delete_session(session_id):
    """Elimina la sesion de Redis. Devuelve cuantas claves borro."""
    client = _critical("delete_session")
    if client is None:
        return 0
    _metrics["ops"] += 1
    return int(client.delete(_key(K_SESSION + str(session_id))))


def save_refresh(token_sha256, data, ttl=None):
    """Guarda el refresh token (ya hasheado) con su TTL. NUNCA se guarda en claro."""
    client = _critical("save_refresh")
    if client is None:
        return False
    _metrics["ops"] += 1
    client.set(_key(K_REFRESH + token_sha256), json.dumps(data, default=str),
               ex=int(ttl or REDIS_REFRESH_TTL))
    return True


def get_refresh(token_sha256):
    client = _critical("get_refresh")
    if client is None:
        return None
    _metrics["ops"] += 1
    raw = client.get(_key(K_REFRESH + token_sha256))
    if raw is None:
        _metrics["misses"] += 1
        return None
    _metrics["hits"] += 1
    return json.loads(raw)


def delete_refresh(token_sha256):
    client = _critical("delete_refresh")
    if client is None:
        return 0
    _metrics["ops"] += 1
    return int(client.delete(_key(K_REFRESH + token_sha256)))


def rotate_refresh(old_sha256, new_sha256, data, ttl=None):
    """Rotacion atomica: borra el refresh viejo y guarda el nuevo."""
    client = _critical("rotate_refresh")
    if client is None:
        return False
    _metrics["ops"] += 1
    pipe = client.pipeline()
    pipe.delete(_key(K_REFRESH + old_sha256))
    pipe.set(_key(K_REFRESH + new_sha256), json.dumps(data, default=str),
             ex=int(ttl or REDIS_REFRESH_TTL))
    pipe.execute()
    return True


# ------------------------------------------------------------------------------
# 4. LISTA DE REVOCACION DE JWT  (fail-CLOSED)
# ------------------------------------------------------------------------------
def revoke_jti(jti, ttl_seconds):
    """Marca un `jti` como revocado. TTL = vida restante del token.

    Guardar la clave solo hasta que el token expira solo es lo correcto: al
    caducar el token, la entrada deja de tener sentido y Redis se limpia solo.
    """
    if not jti:
        return False
    client = _critical("revoke_jti")
    if client is None:
        return False
    _metrics["ops"] += 1
    client.set(_key(K_REVOKED + str(jti)), "1", ex=max(int(ttl_seconds), 1))
    return True


def is_revoked(jti):
    """True si el `jti` esta revocado.

    IMPORTANTE: si Redis no responde lanza RedisUnavailable (fail-closed). No
    devolver False ante un fallo es deliberado: "no pude comprobar" no es
    "no esta revocado".
    """
    if not jti:
        return False
    client = _critical("is_revoked")
    if client is None:
        return False
    _metrics["ops"] += 1
    if client.exists(_key(K_REVOKED + str(jti))):
        _metrics["revoked_hits"] += 1
        return True
    return False


# ------------------------------------------------------------------------------
# 5. CACHE DEL CATALOGO  (fail-OPEN: opcional por diseno)
# ------------------------------------------------------------------------------
def cache_get(key):
    """Lee del cache. Si Redis no responde devuelve None y el llamador va a Postgres."""
    client = get_client()
    if client is None or not available():
        _metrics["misses"] += 1
        return None
    try:
        _metrics["ops"] += 1
        raw = client.get(_key(key))
    except Exception:
        _metrics["errors"] += 1
        return None
    if raw is None:
        _metrics["misses"] += 1
        return None
    _metrics["hits"] += 1
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def cache_set(key, value, ttl=None):
    """Escribe en el cache. Silencioso si Redis no responde (es opcional)."""
    client = get_client()
    if client is None or not available():
        return False
    try:
        _metrics["ops"] += 1
        client.set(_key(key), json.dumps(value, default=str),
                   ex=int(ttl or REDIS_CACHE_TTL))
        return True
    except Exception:
        _metrics["errors"] += 1
        return False


def cache_delete(*keys):
    """Invalida claves concretas. Devuelve cuantas borro (0 si Redis no responde)."""
    client = get_client()
    if client is None or not keys:
        return 0
    try:
        _metrics["ops"] += 1
        return int(client.delete(*[_key(k) for k in keys]))
    except Exception:
        _metrics["errors"] += 1
        return 0


def invalidate_resource(resource):
    """Invalida TODO el cache de un recurso tras un POST/PUT/PATCH/DELETE.

    Borra tanto las listas (`<recurso>:list:*`) como las fichas
    (`<recurso>:*`), asi que una sola llamada deja el cache coherente.

    Se recorre con SCAN (no KEYS) para no bloquear Redis en produccion.
    """
    client = get_client()
    if client is None:
        return 0
    deleted = 0
    try:
        _metrics["ops"] += 1
        pattern = _key(resource) + ":*"
        for found in client.scan_iter(match=pattern, count=200):
            deleted += int(client.delete(found))
    except Exception:
        _metrics["errors"] += 1
    return deleted


# Alias del catalogo de libros (el contrato del enunciado lo nombra asi).
def invalidate_books():
    return invalidate_resource("books")


# ------------------------------------------------------------------------------
# 6. CLAVES DE RECURSO (formato que pide el enunciado)
# ------------------------------------------------------------------------------
def resource_list_key(resource, filters=None):
    """`<resource>:list:<filtros>` con los filtros normalizados y ordenados.

    Ordenar las claves es lo que hace que /books?autor=1&tema=2 y
    /books?tema=2&autor=1 compartan la MISMA entrada de cache.
    """
    if not filters:
        return "%s:list:all" % resource
    parts = ["%s=%s" % (k, filters[k]) for k in sorted(filters)
             if filters[k] not in (None, "", [])]
    return "%s:list:%s" % (resource, "&".join(parts) if parts else "all")


def resource_key(resource, identifier):
    """`<resource>:<id>` normalizado a mayusculas."""
    return "%s:%s" % (resource, str(identifier).strip().upper())


# Alias del catalogo de libros: el contrato del enunciado los nombra asi, y las
# funciones genericas de arriba son las que hacen el trabajo.
def books_list_key(filters=None):
    return resource_list_key("books", filters)


def book_key(isbn):
    return resource_key("books", isbn)

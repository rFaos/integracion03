"""Cliente HTTP delgado sobre la biblioteca estandar (`urllib`).

Se implementa a mano, sin `requests`, por dos razones:
  1. La aplicacion se ejecuta en cualquier Python 3.10+ sin instalar nada.
  2. Deja a la vista que se comprenden los verbos HTTP, las cabeceras, el
     timeout y los codigos de estado (objetivo de la actividad).

Responsabilidades:
  - Construir la URL final (direccion base + ruta + parametros de consulta).
  - Inyectar la credencial JWT: `Authorization: Bearer <access_token>`.
    (Antes se enviaba el header propio `X-Session-Token`; el nuevo requerimiento
    exige el esquema estandar Bearer, y ese es el que se usa en TODAS las
    operaciones, incluidas las de escritura del catalogo.)
  - Renovar el token de forma transparente: si el servicio responde 401 porque
    el access token expiro, se canjea el refresh token en POST /refresh y se
    repite la peticion UNA vez. La interfaz nunca ve ese detalle.
  - Negociar el formato: se pide JSON, pero si el servicio responde XML
    (su formato predeterminado) se convierte a las mismas estructuras Python.
  - Entregar a la bitacora un registro estructurado de cada intercambio, del
    que `core/trace.py` arma el log de la terminal (con el encabezado del token).
  - Traducir TODO fallo a un `ApiError` con mensaje comprensible.
"""

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .errors import ApiError, build_http_error

USER_AGENT = "PythonApp-Biblioteca/1.0 (Cliente de escritorio UDEM)"


# ------------------------------------------------------------------------------
# Construccion de direcciones
# ------------------------------------------------------------------------------
def normalize_base_url(base_url):
    return (base_url or "").strip().rstrip("/")


def join_url(base_url, path, params=None):
    """Une la direccion base con la ruta y agrega los parametros de consulta.

    Se usa `urljoin` sobre una base con barra final para que una base con
    prefijo (por ejemplo http://host/biblioteca) no se coma el prefijo.

    La ruta se codifica (porcentaje) porque un ISBN puede contener espacios:
    el enunciado pide registrar "PRUEBA INTEGRACION - <MATRICULA>" y ese texto
    viaja en la ruta de /books/<isbn>. Sin codificar, `http.client` rechaza la
    peticion con "URL can't contain control characters".
    """
    base = normalize_base_url(base_url) + "/"
    relative = urllib.parse.quote((path or "").lstrip("/"), safe="/%")
    url = urllib.parse.urljoin(base, relative)
    if params:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean:
            url = f"{url}?{urllib.parse.urlencode(clean)}"
    return url


# ------------------------------------------------------------------------------
# Interpretacion del cuerpo de la respuesta
# ------------------------------------------------------------------------------
def _element_to_value(element):
    """Convierte un elemento XML a estructuras Python (dict/list/str).

    Reglas pensadas para el sobre del microservicio de login:
      <response><status>success</status><data>...</data><links>...</links></response>
    Los hijos repetidos se agrupan en listas y `<links><link rel=... />` se
    convierte en el diccionario `_links` que usa la version JSON, de modo que la
    interfaz reciba siempre la misma forma sin importar el formato recibido.
    """
    children = list(element)
    if not children:
        text = (element.text or "").strip()
        return text if text else None

    # Caso especial: bloque de hipermedia.
    if element.tag == "links" and all(child.tag == "link" for child in children):
        links = {}
        for child in children:
            rel = child.attrib.get("rel")
            if rel:
                links[rel] = {"href": child.attrib.get("href"), "method": child.attrib.get("method")}
        return links

    grouped = {}
    for child in children:
        value = _element_to_value(child)
        if child.tag in grouped:
            if not isinstance(grouped[child.tag], list):
                grouped[child.tag] = [grouped[child.tag]]
            grouped[child.tag].append(value)
        else:
            grouped[child.tag] = value
    return grouped


def parse_xml_body(text):
    """Convierte el cuerpo XML en el diccionario equivalente del formato JSON."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ApiError("El servicio respondio XML que no se pudo interpretar.",
                       kind="parse", detail=str(exc))
    value = _element_to_value(root)
    return value if isinstance(value, dict) else {"data": value}


def parse_body(text, content_type=""):
    """Interpreta el cuerpo segun el tipo de contenido anunciado."""
    if not text or not text.strip():
        return {}
    lowered = (content_type or "").lower()
    stripped = text.lstrip()
    if "xml" in lowered or stripped.startswith("<"):
        return parse_xml_body(text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # El servicio anuncio JSON pero mando otra cosa: se conserva el texto
        # crudo para que el mensaje de error tenga contexto.
        return {"raw": text}
    return parsed


# ------------------------------------------------------------------------------
# Cliente
# ------------------------------------------------------------------------------
class HttpResult:
    """Resultado crudo de una peticion (lo que se guarda en la bitacora)."""

    def __init__(self, method, url, status, payload, elapsed_ms, content_type):
        self.method = method
        self.url = url
        self.status = status
        self.payload = payload
        self.elapsed_ms = elapsed_ms
        self.content_type = content_type

    def __repr__(self):
        return f"<HttpResult {self.method} {self.url} -> {self.status} ({self.elapsed_ms:.0f} ms)>"


class HttpClient:
    """Cliente HTTP con credencial JWT, refresco automatico y bitacora."""

    def __init__(self, timeout=8.0, logger=None, refresh_callback=None):
        self.timeout = timeout
        self.logger = logger
        self.refresh_callback = refresh_callback
        self.access_token = None
        self.refresh_token = None
        self.last_result = None      # HttpResult de la ultima peticion
        self.history = []            # historial corto, para la bitacora en pantalla

    # ------------------------------------------------------------------ sesion
    def set_tokens(self, access_token, refresh_token=None):
        """Guarda el par de credenciales. El refresh solo se pisa si se envia."""
        self.access_token = access_token or None
        if refresh_token is not None:
            self.refresh_token = refresh_token or None

    def set_session_token(self, token):
        """Compatibilidad con el codigo anterior (el token de sesion es el access)."""
        self.set_tokens(token)

    def clear_session_token(self):
        """Olvida el access token (se usa cuando el servidor lo rechaza)."""
        self.access_token = None

    def clear_tokens(self):
        """Olvida ambas credenciales (logout)."""
        self.access_token = None
        self.refresh_token = None

    # ----------------------------------------------------------------- peticion
    def request(self, base_url, path, method="GET", params=None, body=None,
                extra_headers=None, timeout=None, accept="application/json",
                _retry=True, note=""):
        """Ejecuta la peticion y devuelve el cuerpo ya interpretado.

        Cualquier fallo se traduce a ApiError: la interfaz grafica no necesita
        try/except de bajo nivel en ningun punto.
        """
        url = join_url(base_url, path, params)
        headers = {
            "User-Agent": USER_AGENT,
            # Se pide JSON explicitamente; el servicio de login responde XML si
            # no se le indica lo contrario, y ambos formatos se interpretan.
            "Accept": f"{accept}, application/json;q=0.9, application/xml;q=0.8",
        }
        # Credencial JWT: el esquema estandar Bearer, en TODAS las peticiones.
        if self.access_token:
            headers["Authorization"] = "Bearer %s" % self.access_token
        headers.update(extra_headers or {})

        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        effective_timeout = timeout if timeout is not None else self.timeout
        started = time.perf_counter()

        try:
            with urllib.request.urlopen(request, timeout=effective_timeout) as response:
                raw = response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                resp_headers = dict(response.headers)
        except urllib.error.HTTPError as exc:
            # El servicio SI respondio: es un error de aplicacion (4xx/5xx).
            raw = exc.read().decode("utf-8", "replace")
            status = exc.code
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            resp_headers = dict(exc.headers) if exc.headers else {}
        except (socket.timeout, TimeoutError) as exc:
            raise ApiError(
                f"El servicio en {base_url} no respondio en {effective_timeout:.0f} segundos.",
                kind="timeout", url=url, method=method, detail=str(exc))
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise ApiError(
                f"No se pudo conectar con {base_url}. Verifica que el servicio este en "
                f"ejecucion y que la direccion sea correcta.",
                kind="network", url=url, method=method, detail=str(reason))
        except (ConnectionError, OSError) as exc:
            raise ApiError(
                f"No se pudo conectar con {base_url}. La conexion fue rechazada o se interrumpio.",
                kind="network", url=url, method=method, detail=str(exc))

        elapsed_ms = (time.perf_counter() - started) * 1000
        payload = parse_body(raw, content_type)

        result = HttpResult(method.upper(), url, status, payload, elapsed_ms, content_type)
        self.last_result = result
        self.history.append(result)
        del self.history[:-30]          # solo interesan las ultimas peticiones

        if self.logger:
            self.logger({
                "time": time.strftime("%H:%M:%S"),
                "method": result.method,
                "url": url,
                "status": status,
                "elapsed_ms": elapsed_ms,
                "content_type": content_type,
                "token": self.access_token,
                "note": note,
                "retry": not _retry,
                "refreshed": bool(extra_headers and extra_headers.get("X-Token-Refreshed")),
            })

        if status >= 400:
            # Refresco transparente: un 401 puede significar "el access token
            # expiro". Si hay refresh token, se canjea y se repite UNA vez.
            if status == 401 and _retry and self.refresh_callback and self.refresh_token:
                if self.refresh_callback():
                    retry_headers = dict(extra_headers or {})
                    retry_headers["X-Token-Refreshed"] = "1"
                    return self.request(base_url, path, method=method, params=params,
                                        body=body, extra_headers=retry_headers,
                                        timeout=timeout, accept=accept,
                                        _retry=False, note=note)
            raise build_http_error(status, payload, url, method.upper())
        return payload

    # ------------------------------------------------------------- atajos REST
    def get(self, base_url, path, params=None, **kwargs):
        return self.request(base_url, path, method="GET", params=params, **kwargs)

    def post(self, base_url, path, body=None, params=None, **kwargs):
        return self.request(base_url, path, method="POST", params=params, body=body, **kwargs)

    def put(self, base_url, path, body=None, **kwargs):
        return self.request(base_url, path, method="PUT", body=body, **kwargs)

    def patch(self, base_url, path, body=None, **kwargs):
        return self.request(base_url, path, method="PATCH", body=body, **kwargs)

    def delete(self, base_url, path, **kwargs):
        return self.request(base_url, path, method="DELETE", **kwargs)

    # ------------------------------------------------------ comprobacion ligera
    def ping(self, base_url, path, params=None, timeout=None):
        """Peticion de salud: devuelve (status, payload) SIN lanzar excepciones.

        La usa el semaforo de estado: un servicio caido debe ser un dato, no una
        excepcion que interrumpa la comprobacion del otro servicio.
        """
        try:
            payload = self.get(base_url, path, params=params, timeout=timeout)
            return self.last_result.status, payload, None
        except ApiError as error:
            status = error.status if error.status else None
            return status, error.payload, error

    def describe_last_request(self):
        """Texto para mostrar en pantalla el recorrido de la ultima peticion."""
        result = self.last_result
        if not result:
            return "Todavia no se ha realizado ninguna peticion."
        return (f"{result.method} {result.url} -> HTTP {result.status} "
                f"en {result.elapsed_ms:.0f} ms ({result.content_type or 'sin content-type'})")

"""Errores de la capa de comunicacion y traduccion de codigos HTTP.

Objetivo: que la interfaz grafica NUNCA muestre un traceback de Python. Toda
falla (de red, de timeout, o un 4xx/5xx del servicio) se convierte en un
`ApiError` con un mensaje comprensible en espanol y datos utiles para depurar.
"""

# Descripcion corta por codigo de estado. El mensaje definitivo prioriza lo que
# diga el servidor; esto es el respaldo cuando el cuerpo viene vacio o ilegible.
HTTP_STATUS_TEXT = {
    400: "La solicitud tiene datos invalidos.",
    401: "La sesion no es valida o ya expiro.",
    403: "La cuenta no tiene permiso para realizar esta operacion.",
    404: "El recurso solicitado no existe.",
    405: "El servicio no admite ese metodo HTTP en esa ruta.",
    409: "La operacion entra en conflicto con informacion existente.",
    415: "El servicio no acepta el formato de los datos enviados.",
    422: "Los datos enviados no superan la validacion del servicio.",
    429: "Demasiadas solicitudes en poco tiempo. Espera unos segundos.",
    500: "Error interno del microservicio.",
    502: "El servicio responde a traves de un intermediario que fallo.",
    503: "El servicio esta disponible pero una dependencia no lo esta.",
    504: "El servicio no respondio a tiempo.",
}

# Codigos de error de negocio del microservicio de login que conviene traducir
# a una accion concreta en la interfaz.
AUTH_ERROR_HINTS = {
    "INVALID_CREDENTIALS": "El correo o la contrasena son incorrectos.",
    "INVALID_CAPTCHA": "La respuesta del CAPTCHA es incorrecta.",
    "CAPTCHA_EXPIRED": "El desafio CAPTCHA expiro. Solicita uno nuevo.",
    "CAPTCHA_ALREADY_USED": "Ese desafio CAPTCHA ya se uso. Solicita uno nuevo.",
    "ACCOUNT_LOCKED": "La cuenta esta bloqueada temporalmente por intentos fallidos.",
    "ACCOUNT_DISABLED": "La cuenta todavia no puede autenticarse: esta deshabilitada.",
    "EMAIL_ALREADY_EXISTS": "Ese correo ya esta registrado.",
    "WEAK_PASSWORD": "La contrasena no cumple la politica de seguridad.",
    "SESSION_EXPIRED": "La sesion expiro. Inicia sesion de nuevo.",
    "SESSION_INVALID": "La sesion ya no es valida. Inicia sesion de nuevo.",
    "SESSION_REQUIRED": "No hay sesion activa.",
    "TOO_MANY_REQUESTS": "Demasiadas solicitudes. Espera un momento.",
    "INVALID_CURRENT_PASSWORD": "La contrasena actual no es correcta.",
    "VALIDATION_ERROR": "El servicio rechazo los datos enviados.",
}


class ApiError(Exception):
    """Falla de comunicacion con un microservicio.

    kind:
        "network"  -> no hubo respuesta (servicio caido, host o puerto mal)
        "timeout"  -> hubo conexion pero no respondio a tiempo
        "http"     -> respondio con 4xx/5xx
        "parse"    -> respondio algo que no se pudo interpretar
    """

    def __init__(self, message, kind="http", status=None, code=None,
                 url=None, method=None, payload=None, detail=None):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.status = status
        self.code = code
        self.url = url
        self.method = method
        self.payload = payload
        self.detail = detail

    # ------------------------------------------------------------------ ayudas
    @property
    def is_network_failure(self):
        """True si el servicio no respondio (servicio caido / URL incorrecta)."""
        return self.kind in ("network", "timeout")

    @property
    def is_session_problem(self):
        """True si el problema es de sesion y conviene volver al login."""
        if self.status in (401,):
            return True
        return self.code in ("SESSION_EXPIRED", "SESSION_INVALID", "SESSION_REQUIRED")

    @property
    def is_conflict(self):
        return self.status == 409

    @property
    def is_not_found(self):
        return self.status == 404

    def technical_summary(self):
        """Linea corta para la bitacora de la aplicacion (no para el usuario final)."""
        parts = [f"{self.method or '?'} {self.url or '?'}"]
        if self.status:
            parts.append(f"HTTP {self.status}")
        if self.code:
            parts.append(f"codigo={self.code}")
        parts.append(f"tipo={self.kind}")
        return " | ".join(parts)

    def __str__(self):
        return self.message


def extract_error_code(payload):
    """Obtiene el codigo de error del sobre de cualquiera de los dos servicios.

    El microservicio de login responde {"status":"error","error":{"code","message"}}
    y el de libros responde {"error":"...", "details":"..."}.
    """
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        return error.get("code")
    return None


def extract_error_message(payload):
    """Obtiene el mensaje de error mas util del cuerpo de la respuesta."""
    if not isinstance(payload, dict):
        return None

    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("message", "detail", "details"):
            if error.get(key):
                return str(error[key])
        if error.get("code"):
            return str(error["code"])
    elif isinstance(error, str) and error:
        # El microservicio de libros usa {"error": "Conflicto", "message": "El
        # ISBN ... ya existe"}: el texto util esta en message/details, no en error.
        tail = payload.get("details") or payload.get("message")
        return f"{error}: {tail}" if tail else error

    for key in ("message", "detail", "details"):
        if payload.get(key):
            return str(payload[key])
    return None


def describe_status(status):
    return HTTP_STATUS_TEXT.get(status, f"El servicio respondio HTTP {status}.")


def build_http_error(status, payload, url, method):
    """Construye el ApiError definitivo para una respuesta 4xx/5xx."""
    code = extract_error_code(payload)
    server_message = extract_error_message(payload)

    # Prioridad: mensaje del servidor > pista por codigo de negocio > texto por HTTP.
    message = server_message or AUTH_ERROR_HINTS.get(code) or describe_status(status)
    if code == "ACCOUNT_LOCKED":
        # Aqui el texto del servicio agrega contexto util (los minutos de bloqueo).
        message = server_message or AUTH_ERROR_HINTS[code]
    elif code == "ACCOUNT_DISABLED":
        # El servicio responde algo escueto ("La cuenta esta deshabilitada"); se usa
        # la pista local, que explica que la cuenta todavia no puede autenticarse.
        message = AUTH_ERROR_HINTS[code]

    return ApiError(message, kind="http", status=status, code=code,
                    url=url, method=method, payload=payload)

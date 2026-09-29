"""Configuracion de la aplicacion: donde viven las direcciones de los servicios.

La configuracion se guarda en disco (`runtime/config.json`) para que sobreviva al
cierre de la aplicacion y para que NO haya que tocar el codigo fuente para pasar
del escenario local al remoto (requisito 13 y 14 del enunciado).

El archivo `config.example.json` versionado en git es solo una plantilla: el
archivo real se genera en `runtime/` y esta excluido por `.gitignore`, porque la
configuracion de cada estudiante puede contener direcciones propias.
"""

import json
import os
from pathlib import Path

# ------------------------------------------------------------------------------
# Rutas de la aplicacion
# ------------------------------------------------------------------------------
APP_ROOT = Path(__file__).resolve().parent.parent

# Se puede reubicar con la variable de entorno PYTHON_APP_HOME (util para probar
# con distintos juegos de configuracion sin ensuciar la carpeta del proyecto).
RUNTIME_DIR = Path(os.environ.get("PYTHON_APP_HOME", APP_ROOT / "runtime"))
CONFIG_PATH = RUNTIME_DIR / "config.json"
SESSION_PATH = RUNTIME_DIR / "session.json"
LOG_PATH = RUNTIME_DIR / "bitacora.log"

# ------------------------------------------------------------------------------
# Valores predeterminados
# ------------------------------------------------------------------------------
# Escenario 1 (local): los microservicios en la propia computadora.
# El boton "Usar remoto" de la pantalla de configuracion construye las
# direcciones del escenario 2 (instancia en GCloud) a partir de remote_host.
#
# NOTA sobre 127.0.0.1 en lugar de localhost:
# en Windows, "localhost" se resuelve primero a IPv6 (::1) mientras los
# microservicios escuchan en IPv4. Cada peticion esperaba a que la conexion a
# ::1 fallara antes de reintentar por IPv4, y eso costaba ~2 segundos por
# llamada. Con la direccion IPv4 explicita el mismo request tarda ~60 ms.
DEFAULT_CONFIG = {
    "login_base_url": "http://127.0.0.1:5000",
    "books_base_url": "http://127.0.0.1:5001",
    "remote_host": "34.51.29.27",
    "remote_login_port": 5000,
    "remote_books_port": 5001,
    "request_timeout": 8.0,
    "health_interval_seconds": 30,
    "session_warning_seconds": 300,
    "page_size": 12,
    "remember_credentials": True,
}

# Etiquetas para mostrar en la interfaz sin repetir cadenas por todo el codigo.
SERVICE_LABELS = {
    "login": "Microservicio de Login",
    "books": "Microservicio de Libros",
}


class ConfigError(ValueError):
    """Configuracion invalida escrita por el usuario en la pantalla de ajustes."""


def _as_float(value, default, minimum, maximum, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ConfigError(f"El campo '{field}' debe ser un numero.")
    if not minimum <= number <= maximum:
        raise ConfigError(f"El campo '{field}' debe estar entre {minimum} y {maximum}.")
    return number


def _as_int(value, default, minimum, maximum, field):
    return int(_as_float(value, default, minimum, maximum, field))


def validate_base_url(url, field):
    """Comprueba que una direccion base sea utilizable antes de guardarla."""
    url = (url or "").strip()
    if not url:
        raise ConfigError(f"El campo '{field}' no puede quedar vacio.")
    if not url.startswith(("http://", "https://")):
        raise ConfigError(f"El campo '{field}' debe iniciar con http:// o https://")
    if " " in url:
        raise ConfigError(f"El campo '{field}' no puede contener espacios.")
    host_part = url.split("://", 1)[1]
    if not host_part or host_part.startswith("/"):
        raise ConfigError(f"El campo '{field}' no incluye un host valido.")
    return url.rstrip("/")


class ConfigStore:
    """Lee, valida y guarda la configuracion de los servicios."""

    def __init__(self, path=None):
        self.path = Path(path) if path else CONFIG_PATH
        self._data = dict(DEFAULT_CONFIG)

    # --------------------------------------------------------------- ciclo vida
    def load(self):
        """Carga el archivo; si no existe o esta corrupto usa los predeterminados."""
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    # Solo se aceptan claves conocidas: un archivo viejo con
                    # campos que ya no existen no debe romper la aplicacion.
                    self._data = {**DEFAULT_CONFIG,
                                  **{k: v for k, v in stored.items() if k in DEFAULT_CONFIG}}
            except (json.JSONDecodeError, OSError):
                self._data = dict(DEFAULT_CONFIG)
        else:
            self.save()
        return self

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        return self

    def reset(self):
        """Restaura los valores predeterminados (boton de la pantalla de ajustes)."""
        self._data = dict(DEFAULT_CONFIG)
        self.save()
        return self

    # ------------------------------------------------------------------ acceso
    def get(self, key):
        return self._data.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        if key not in DEFAULT_CONFIG:
            raise ConfigError(f"Clave de configuracion desconocida: {key}")
        self._data[key] = value

    def as_dict(self):
        return dict(self._data)

    def update_from_form(self, values):
        """Valida y aplica el formulario de configuracion completo.

        Lanza ConfigError con el primer problema encontrado, de modo que la
        interfaz pueda mostrar el mensaje sin que nada quede a medio guardar.
        """
        cleaned = {
            "login_base_url": validate_base_url(values.get("login_base_url"), "URL del servicio de login"),
            "books_base_url": validate_base_url(values.get("books_base_url"), "URL del servicio de libros"),
            "remote_host": (values.get("remote_host") or "").strip(),
            "remote_login_port": _as_int(values.get("remote_login_port"), 5000, 1, 65535, "Puerto de login remoto"),
            "remote_books_port": _as_int(values.get("remote_books_port"), 5001, 1, 65535, "Puerto de libros remoto"),
            "request_timeout": _as_float(values.get("request_timeout"), 8.0, 1, 120, "Timeout de peticiones"),
            "health_interval_seconds": _as_int(values.get("health_interval_seconds"), 30, 5, 3600, "Intervalo de comprobacion"),
            "session_warning_seconds": _as_int(values.get("session_warning_seconds"), 300, 30, 1800, "Aviso de sesion por expirar"),
            "page_size": _as_int(values.get("page_size"), 12, 4, 60, "Libros por pagina"),
            "remember_credentials": bool(values.get("remember_credentials", True)),
        }
        if not cleaned["remote_host"]:
            raise ConfigError("El host remoto no puede quedar vacio.")
        self._data.update(cleaned)
        return self

    # ------------------------------------------------------------- direcciones
    def base_url(self, service):
        """Direccion base del servicio indicado ('login' o 'books')."""
        if service == "login":
            return self.get("login_base_url")
        if service == "books":
            return self.get("books_base_url")
        raise ConfigError(f"Servicio desconocido: {service}")

    def remote_urls(self):
        """Direcciones del escenario remoto (instancia en GCloud)."""
        host = self.get("remote_host")
        return {
            "login": f"http://{host}:{self.get('remote_login_port')}",
            "books": f"http://{host}:{self.get('remote_books_port')}",
        }

    def apply_local_preset(self):
        """Deja la configuracion apuntando a los servicios locales."""
        self._data["login_base_url"] = DEFAULT_CONFIG["login_base_url"]
        self._data["books_base_url"] = DEFAULT_CONFIG["books_base_url"]
        return self

    def apply_remote_preset(self):
        """Deja la configuracion apuntando a la instancia remota."""
        urls = self.remote_urls()
        self._data["login_base_url"] = urls["login"]
        self._data["books_base_url"] = urls["books"]
        return self

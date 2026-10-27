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
    # Esquema preferido de todas las direcciones. Por defecto HTTP (escenario de
    # practica); al cambiarlo a "https" se reescriben TODAS las direcciones y la
    # preferencia queda guardada en config.json, de modo que sobrevive al cierre.
    "scheme": "http",
    "login_base_url": "http://127.0.0.1:5000",
    "books_base_url": "http://127.0.0.1:5001",
    "users_base_url": "http://127.0.0.1:5002",
    "autores_base_url": "http://127.0.0.1:5003",
    "pedidos_base_url": "http://127.0.0.1:5004",
    "pagos_base_url": "http://127.0.0.1:5005",
    "remote_host": "34.51.29.27",
    "remote_login_port": 5000,
    "remote_books_port": 5001,
    "remote_users_port": 5002,
    "remote_autores_port": 5003,
    "remote_pedidos_port": 5004,
    "remote_pagos_port": 5005,
    "request_timeout": 8.0,
    "health_interval_seconds": 30,
    "session_warning_seconds": 300,
    "page_size": 12,
    "remember_credentials": True,
}

# Los seis microservicios que la aplicacion conoce. Centralizar la lista evita
# olvidar uno al construir direcciones, presets o el semaforo.
SERVICE_KEYS = ("login", "books", "users", "autores", "pedidos", "pagos")

# Etiquetas para mostrar en la interfaz sin repetir cadenas por todo el codigo.
SERVICE_LABELS = {
    "login": "Microservicio de Login",
    "books": "Microservicio de Libros",
    "users": "Microservicio de Usuarios",
    "autores": "Microservicio de Autores",
    "pedidos": "Microservicio de Pedidos",
    "pagos": "Microservicio de Pagos",
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
        scheme = str(values.get("scheme") or self.get("scheme") or "http").lower()
        if scheme not in ("http", "https"):
            raise ConfigError("El esquema debe ser 'http' o 'https'.")

        cleaned = {
            "scheme": scheme,
            "remote_host": (values.get("remote_host") or "").strip(),
            "request_timeout": _as_float(values.get("request_timeout"), 8.0, 1, 120, "Timeout de peticiones"),
            "health_interval_seconds": _as_int(values.get("health_interval_seconds"), 30, 5, 3600, "Intervalo de comprobacion"),
            "session_warning_seconds": _as_int(values.get("session_warning_seconds"), 300, 30, 1800, "Aviso de sesion por expirar"),
            "page_size": _as_int(values.get("page_size"), 12, 4, 60, "Libros por pagina"),
            "remember_credentials": bool(values.get("remember_credentials", True)),
        }
        if not cleaned["remote_host"]:
            raise ConfigError("El host remoto no puede quedar vacio.")

        # Direcciones base de los seis servicios (el esquema se aplica al final).
        for svc in SERVICE_KEYS:
            key = f"{svc}_base_url"
            url = values.get(key, self.get(key))
            url = validate_base_url(url, f"URL del servicio de {SERVICE_LABELS.get(svc, svc)}")
            cleaned[key] = _force_scheme(url, scheme)
            port_val = values.get(f"remote_{svc}_port")
            if port_val in (None, ""):          # campo no enviado: conservar el actual
                port_val = self.get(f"remote_{svc}_port")
            cleaned[f"remote_{svc}_port"] = _as_int(
                port_val, DEFAULT_CONFIG[f"remote_{svc}_port"],
                1, 65535, f"Puerto remoto de {SERVICE_LABELS.get(svc, svc)}")

        self._data.update(cleaned)
        return self

    # ------------------------------------------------------------- direcciones
    def base_url(self, service):
        """Direccion base del servicio indicado (ver SERVICE_KEYS)."""
        key = f"{service}_base_url"
        if key in DEFAULT_CONFIG:
            return self.get(key)
        raise ConfigError(f"Servicio desconocido: {service}")

    def remote_urls(self):
        """Direcciones del escenario remoto (instancia en GCloud)."""
        host = self.get("remote_host")
        scheme = self.get("scheme")
        return {svc: f"{scheme}://{host}:{self.get('remote_' + svc + '_port')}"
                for svc in SERVICE_KEYS}

    def set_scheme(self, scheme):
        """Cambia http<->https en TODAS las direcciones y lo persiste."""
        scheme = str(scheme or "").lower()
        if scheme not in ("http", "https"):
            raise ConfigError("El esquema debe ser 'http' o 'https'.")
        for svc in SERVICE_KEYS:
            key = f"{svc}_base_url"
            self._data[key] = _force_scheme(self.get(key), scheme)
        self._data["scheme"] = scheme
        return self

    def apply_local_preset(self):
        """Deja la configuracion apuntando a los servicios locales."""
        for svc in SERVICE_KEYS:
            self._data[f"{svc}_base_url"] = _force_scheme(
                DEFAULT_CONFIG[f"{svc}_base_url"], self.get("scheme"))
        return self

    def apply_remote_preset(self):
        """Deja la configuracion apuntando a la instancia remota."""
        for svc, url in self.remote_urls().items():
            self._data[f"{svc}_base_url"] = url
        return self


def _force_scheme(url, scheme):
    """Devuelve la misma direccion con el esquema indicado."""
    rest = url.split("://", 1)[1] if "://" in url else url
    return f"{scheme}://{rest}"

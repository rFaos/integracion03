"""Persistencia local de la sesion ("local storage" del cliente de escritorio).

Que se guarda y por que:

  - Credenciales (correo y contrasena): pedido expresamente para que la
    aplicacion no vuelva a pedirlas al reabrirse.
  - Token de sesion y su vencimiento: para no volver a autenticarse mientras el
    servidor considere la sesion vigente.
  - Datos publicos del usuario: para pintar la cabecera antes de que responda
    el servidor.

Regla de oro que implementa este modulo: **recordar al usuario localmente no
significa que la sesion del servidor siga siendo valida**. Al arrancar, la
aplicacion NO confia en lo guardado: llama a `GET /session` y, si el servidor
dice que expiro o fue revocada, borra el token y regresa al login.

ADVERTENCIA DE SEGURIDAD
------------------------
El contenido se guarda ofuscado en base64 con una clave fija. Eso evita que las
credenciales queden legibles a simple vista, pero NO es cifrado: cualquiera con
acceso al archivo puede recuperarlas. Por eso `runtime/` esta excluido en
`.gitignore` y nunca debe subirse al repositorio.
"""

import base64
import json
from datetime import datetime, timezone

from .config import SESSION_PATH

# Clave de ofuscacion (no es una clave criptografica; ver advertencia arriba).
_OBFUSCATION_KEY = b"integracion03-python-app"


def _xor(data: bytes) -> bytes:
    key = _OBFUSCATION_KEY
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))


def _obfuscate(text):
    if not text:
        return None
    return base64.b64encode(_xor(text.encode("utf-8"))).decode("ascii")


def _deobfuscate(text):
    if not text:
        return None
    try:
        return _xor(base64.b64decode(text.encode("ascii"))).decode("utf-8")
    except Exception:
        return None


def parse_iso_datetime(value):
    """Convierte una marca ISO del servicio en datetime con zona horaria."""
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class SessionStore:
    """Almacen local de la sesion y de las credenciales recordadas."""

    def __init__(self, path=None):
        self.path = path or SESSION_PATH
        self._data = {
            "email": None,
            "password": None,      # ofuscada
            "token": None,              # access token (JWT)
            "refresh_token": None,      # refresh token (opaco, rotativo)
            "expires_at": None,         # vencimiento del access token
            "refresh_expires_at": None, # vencimiento del refresh token
            "user": None,
        }

    # --------------------------------------------------------------- ciclo vida
    def load(self):
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    self._data.update({k: stored.get(k) for k in self._data})
            except (json.JSONDecodeError, OSError):
                pass
        return self

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        return self

    def clear(self):
        """Olvida absolutamente todo lo guardado (usado por el logout total)."""
        self._data = {"email": None, "password": None, "token": None,
                      "refresh_token": None, "expires_at": None,
                      "refresh_expires_at": None, "user": None}
        self.save()
        return self

    # -------------------------------------------------------------- credenciales
    def remember_credentials(self, email, password):
        self._data["email"] = email
        self._data["password"] = _obfuscate(password)
        self.save()

    def forget_credentials(self):
        self._data["email"] = None
        self._data["password"] = None
        self.save()

    def has_credentials(self):
        return bool(self._data.get("email") and self._data.get("password"))

    def credentials(self):
        """Devuelve (correo, contrasena) o (None, None)."""
        email = self._data.get("email")
        password = _deobfuscate(self._data.get("password"))
        if email and password:
            return email, password
        return None, None

    # ------------------------------------------------------------------- sesion
    def set_session(self, token, expires_at, user=None,
                    refresh_token=None, refresh_expires_at=None):
        """Guarda el par de credenciales del nuevo modelo JWT.

        `token` es el ACCESS token (el JWT que viaja en `Authorization: Bearer`)
        y `refresh_token` el token opaco con el que se pide uno nuevo. El refresh
        solo se pisa cuando se envia: asi una simple consulta a /session no borra
        la credencial de refresco.
        """
        self._data["token"] = token
        self._data["expires_at"] = expires_at
        if refresh_token is not None:
            self._data["refresh_token"] = refresh_token
        if refresh_expires_at is not None:
            self._data["refresh_expires_at"] = refresh_expires_at
        if user is not None:
            self._data["user"] = user
        self.save()

    def set_user(self, user):
        self._data["user"] = user
        self.save()

    def token(self):
        """Access token (JWT) actual."""
        return self._data.get("token")

    def access_token(self):
        return self._data.get("token")

    def refresh_token(self):
        return self._data.get("refresh_token")

    def user(self):
        return self._data.get("user") or {}

    def expires_at(self):
        return parse_iso_datetime(self._data.get("expires_at"))

    def clear_session(self):
        """Olvida las credenciales de sesion pero conserva lo recordado."""
        self._data["token"] = None
        self._data["refresh_token"] = None
        self._data["expires_at"] = None
        self._data["refresh_expires_at"] = None
        self._data["user"] = None
        self.save()

    def remaining_seconds(self):
        """Segundos que le quedan a la sesion segun el reloj del cliente.

        Es solo una estimacion para avisar al usuario: la validez real la
        determina el servidor en `GET /session`.
        """
        expiry = self.expires_at()
        if not expiry:
            return None
        return int((expiry - datetime.now(timezone.utc)).total_seconds())

    def is_expired_locally(self):
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0

    def describe(self):
        """Resumen de una linea para mostrar en la pantalla de perfil."""
        remaining = self.remaining_seconds()
        if remaining is None:
            return "Sin sesion guardada."
        if remaining <= 0:
            return "La sesion guardada ya expiro (se validara contra el servidor)."
        minutes, seconds = divmod(remaining, 60)
        return f"Sesion local: quedan {minutes} min {seconds} s."

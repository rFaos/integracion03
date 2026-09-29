"""Punto unico donde se construyen los servicios que usa la interfaz.

La ventana no crea clientes HTTP ni sabe de direcciones: recibe este objeto ya
armado. Cambiar de servidor local a remoto es cambiar `config`, nada mas.

Aqui tambien se conecta el REFRESCO AUTOMATICO del token: el cliente HTTP, al
recibir un 401, invoca `auth.refresh_session()` y repite la peticion. Y aqui se
imprime la bitacora en la TERMINAL (con el encabezado del token), que es lo que
pide la actividad.
"""

from . import trace
from .auth_service import AuthService
from .books_service import BooksService
from .config import ConfigStore
from .health_service import HealthMonitor, HealthService
from .http_client import HttpClient
from .session_store import SessionStore


class ServiceHub:
    """Agrupa configuracion, cliente HTTP y los tres servicios de la aplicacion."""

    def __init__(self, config=None, store=None):
        self.config = config if config is not None else ConfigStore().load()
        self.store = store if store is not None else SessionStore().load()
        self.log_lines = []

        self.http = HttpClient(timeout=self.config.get("request_timeout"), logger=self._log)
        self.auth = AuthService(self.http, self.config, self.store)
        self.books = BooksService(self.http, self.config)
        self.health = HealthService(self.http, self.config)
        self.monitor = HealthMonitor(self.health, self.config.get("health_interval_seconds"))

        # Renovacion transparente del access token: el cliente HTTP llama aqui
        # cuando un servicio responde 401 antes de dar la peticion por fallida.
        self.http.refresh_callback = self.auth.refresh_session

        # Si hay credenciales guardadas, se preparan desde el arranque; su
        # validez real se comprueba contra el servidor despues.
        if self.store.token():
            self.http.set_tokens(self.store.token(), self.store.refresh_token())

    # ------------------------------------------------------------------ bitacora
    def _log(self, entry):
        """Imprime el intercambio en la TERMINAL y guarda un resumen para la UI.

        `entry` es el registro estructurado que arma `HttpClient`; el formato lo
        decide `core/trace.py` para no mezclar presentacion con transporte.
        """
        for line in trace.format_block(entry):
            print(line)
        self.log_lines.append(trace.format_summary(entry))
        del self.log_lines[:-200]

    def recent_log(self, limit=40):
        return self.log_lines[-limit:]

    # ------------------------------------------------------------------ arranque
    def startup_banner(self):
        """Cabecera que se imprime al abrir la aplicacion (queda en la terminal)."""
        targets = self.describe_targets()
        token = self.http.access_token
        lines = [
            "=" * 84,
            " CLIENTE DE ESCRITORIO DE LA LIBRERIA - microservicios + JWT (RFC 7519)",
            "=" * 84,
            " Microservicio de login  : %s" % targets["login"],
            " Microservicio de libros : %s" % targets["books"],
            " Esquema de autorizacion : Authorization: Bearer <access_token>",
            " Metodos publicos (libros): GET /books y GET /books/{isbn} (sin token)",
            " Metodos protegidos       : POST / PUT / PATCH / DELETE (exigen token)",
            "-" * 84,
            " Credencial en memoria    : %s" % (
                trace.mask(token) if token else "(ninguna: la sesion inicia sin token)"),
        ]
        claims = trace.describe_claims(token)
        if claims:
            lines.append(" Token cargado            : sub=%s rol=%s expira en %s"
                         % (claims["sub"], claims["rol"], claims["restante_texto"]))
        lines.append(" Renovacion automatica    : activa (POST /refresh al recibir 401)")
        lines.append("=" * 84)
        for line in lines:
            print(line)
        return lines

    # ------------------------------------------------------------------ ajustes
    def apply_config(self):
        """Reaplica la configuracion tras editarla en la pantalla de ajustes."""
        self.http.timeout = self.config.get("request_timeout")
        self.monitor.set_interval(self.config.get("health_interval_seconds"))
        if self.store.token():
            self.http.set_tokens(self.store.token(), self.store.refresh_token())

    def describe_targets(self):
        """Resumen de las direcciones activas (se muestra en varias pantallas)."""
        return {
            "login": self.config.base_url("login"),
            "books": self.config.base_url("books"),
        }

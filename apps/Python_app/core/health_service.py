"""Semaforo de estado de los microservicios (endpoint /health).

Tres estados, tal como pide la actividad:

    VERDE  (up)       -> el servicio responde y su base de datos esta disponible.
    AMARILLO (degraded) -> el servicio responde, pero una dependencia no esta
                          disponible o esta a medias (por ejemplo PostgreSQL
                          caido, o falta aplicar una migracion).
    ROJO   (down)     -> no hubo respuesta: servicio detenido, puerto incorrecto
                          o direccion mal escrita.

Detalle importante que se maneja aqui: un HTTP 503 NO es "servicio caido". El
servicio contesto (esta vivo), lo que falla es su dependencia; por eso se
clasifica como degradado y no como rojo.

La comprobacion periodica corre en un hilo aparte para que la ventana nunca se
congele mientras espera un timeout.
"""

import queue
import threading
from datetime import datetime

UP = "up"
DEGRADED = "degraded"
DOWN = "down"

STATE_LABELS = {
    UP: "Operativo",
    DEGRADED: "Degradado",
    DOWN: "Sin respuesta",
}

# Color del semaforo por estado (coincide con la leyenda de la interfaz).
STATE_COLORS = {
    UP: "#1e8e3e",        # verde
    DEGRADED: "#e8a600",  # ambar
    DOWN: "#d93025",      # rojo
}

SERVICES = ("login", "books")

SERVICE_NAMES = {
    "login": "Microservicio de Login",
    "books": "Microservicio de Libros",
}


class HealthResult:
    """Resultado de comprobar un servicio."""

    def __init__(self, service, state, headline, detail="", http_status=None,
                 base_url="", error=None, checked_at=None):
        self.service = service
        self.state = state
        self.headline = headline
        self.detail = detail
        self.http_status = http_status
        self.base_url = base_url
        self.error = error
        self.checked_at = checked_at or datetime.now()

    @property
    def label(self):
        return SERVICE_NAMES.get(self.service, self.service)

    @property
    def color(self):
        return STATE_COLORS.get(self.state, "#5f6368")

    @property
    def state_label(self):
        return STATE_LABELS.get(self.state, self.state)

    def checked_at_text(self):
        return self.checked_at.strftime("%H:%M:%S")

    def summary(self):
        text = f"{self.state_label}: {self.headline}"
        if self.detail:
            text += f" ({self.detail})"
        return text

    def __repr__(self):
        return f"<HealthResult {self.service} {self.state} http={self.http_status}>"


class HealthService:
    """Comprueba el estado de los dos microservicios."""

    def __init__(self, http, config):
        self.http = http
        self.config = config

    def check(self, service, base_url=None, timeout=4.0):
        """Comprueba un servicio. Nunca lanza excepciones: siempre devuelve estado."""
        url = base_url or self.config.base_url(service)
        params = {"format": "json"} if service == "login" else None

        status, payload, error = self.http.ping(url, "/health", params=params, timeout=timeout)

        if error is not None and error.is_network_failure:
            kind = "timeout" if error.kind == "timeout" else "sin conexion"
            return HealthResult(
                service, DOWN,
                "El servicio no responde",
                f"{kind} en {url}",
                http_status=None, base_url=url, error=error,
            )

        if error is not None:
            # Hubo respuesta HTTP de error inesperada (por ejemplo 500).
            return HealthResult(
                service, DEGRADED,
                f"El servicio responde HTTP {error.status}",
                error.message,
                http_status=error.status, base_url=url, error=error,
            )

        return self._classify(service, status, payload or {}, url)

    # ------------------------------------------------------------------ internos
    def _classify(self, service, status, payload, url):
        """Traduce la respuesta de /health al estado del semaforo."""
        if service == "login":
            return self._classify_login(status, payload, url)
        return self._classify_books(status, payload, url)

    @staticmethod
    def _classify_login(status, payload, url):
        data = payload.get("data") if isinstance(payload, dict) else None
        data = data if isinstance(data, dict) else {}

        if status == 200:
            database = data.get("database")
            schema = data.get("schema")
            if database == "connected" and schema == "ready":
                return HealthResult(
                    "login", UP, "Servicio y base de datos operativos",
                    f"PostgreSQL {data.get('postgres_version', '')}".strip(),
                    http_status=status, base_url=url,
                )
            if schema and schema != "ready":
                return HealthResult(
                    "login", DEGRADED, "Servicio arriba, esquema incompleto",
                    data.get("migration_hint") or f"schema={schema}",
                    http_status=status, base_url=url,
                )
            return HealthResult(
                "login", DEGRADED, "Servicio arriba, base de datos no confirmada",
                f"database={database or 'desconocido'}",
                http_status=status, base_url=url,
            )

        if status == 503:
            # El servicio contesto: esta vivo, pero no alcanza PostgreSQL.
            detail = "No fue posible conectar con PostgreSQL"
            if isinstance(payload, dict):
                detail = (payload.get("error") or {}).get("message") or detail \
                    if isinstance(payload.get("error"), dict) else detail
            return HealthResult(
                "login", DEGRADED, "Servicio accesible, base de datos no disponible",
                detail, http_status=status, base_url=url,
            )

        return HealthResult(
            "login", DEGRADED, f"Respuesta inesperada HTTP {status}",
            "El endpoint /health no devolvio el sobre esperado",
            http_status=status, base_url=url,
        )

    @staticmethod
    def _classify_books(status, payload, url):
        payload = payload if isinstance(payload, dict) else {}

        if status == 200:
            service_status = str(payload.get("status") or "").lower()
            database = str(payload.get("database") or "").lower()
            if service_status == "healthy" and database == "connected":
                return HealthResult(
                    "books", UP, "Servicio y base de datos operativos",
                    f"db_response={payload.get('db_response')}",
                    http_status=status, base_url=url,
                )
            return HealthResult(
                "books", DEGRADED, "Servicio arriba, dependencia degradada",
                f"status={service_status or 'desconocido'} database={database or 'desconocido'}",
                http_status=status, base_url=url,
            )

        if status == 503:
            return HealthResult(
                "books", DEGRADED, "Servicio accesible, base de datos no disponible",
                str(payload.get("error") or "PostgreSQL no disponible"),
                http_status=status, base_url=url,
            )

        return HealthResult(
            "books", DEGRADED, f"Respuesta inesperada HTTP {status}",
            "El endpoint /health no devolvio el cuerpo esperado",
            http_status=status, base_url=url,
        )

    def check_all(self, timeout=4.0):
        """Comprueba los dos servicios y devuelve {servicio: HealthResult}."""
        return {service: self.check(service, timeout=timeout) for service in SERVICES}


class HealthMonitor:
    """Comprobaciones periodicas en segundo plano.

    La interfaz llama a `poll()` desde el bucle de eventos de Tk: asi la red
    nunca bloquea la ventana y los resultados llegan siempre al hilo principal.
    """

    def __init__(self, health_service, interval_seconds=30):
        self.health_service = health_service
        self.interval_seconds = max(5, int(interval_seconds))
        self._results = queue.Queue()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self.last_run = None

    # ------------------------------------------------------------------ control
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="health-monitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def trigger_now(self):
        """Fuerza una comprobacion inmediata (boton 'Comprobar ahora')."""
        self._wake.set()

    def set_interval(self, seconds):
        self.interval_seconds = max(5, int(seconds))
        self._wake.set()

    def poll(self):
        """Devuelve la lista de resultados nuevos (no bloquea)."""
        results = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except queue.Empty:
                break
        return results

    # ------------------------------------------------------------------- hilo
    def _loop(self):
        while not self._stop.is_set():
            try:
                results = self.health_service.check_all()
                self.last_run = datetime.now()
                self._results.put(results)
            except Exception as exc:                     # nunca debe morir el hilo
                self._results.put({"error": str(exc)})
            # Espera el intervalo o hasta que alguien pida una comprobacion.
            self._wake.wait(self.interval_seconds)
            self._wake.clear()

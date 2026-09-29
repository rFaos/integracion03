"""Ventana principal: cabecera, navegacion, sesion y estado de los servicios.

Decisiones de diseno relevantes:

  - **Nada de red en el hilo de la interfaz.** Toda peticion se ejecuta en un
    hilo aparte mediante `run_async`; el resultado se devuelve al hilo de Tk con
    `after`. Asi un servicio caido o lento nunca congela ni cierra la ventana
    (requisito 6 de tolerancia a fallos).
  - **Los errores nunca llegan crudos a la pantalla.** `handle_error` traduce
    cualquier excepcion a un aviso en lenguaje claro y, si el problema es de
    sesion, regresa de forma controlada al inicio de sesion.
  - **La sesion se valida contra el servidor al arrancar.** Tener un token en
    disco no significa que siga siendo valido.
"""

import queue
import sys
import threading
import tkinter as tk
import traceback
from tkinter import ttk

from core.errors import ApiError
from core.health_service import STATE_COLORS, STATE_LABELS

from .theme import COLORS, FONT_BOLD, FONT_H1, FONT_SMALL
from .widgets import Banner, ImageLoader, StatusLight

APP_TITLE = "Biblioteca UDEM - Cliente de microservicios"


class AppWindow(tk.Tk):
    """Ventana unica de la aplicacion."""

    def __init__(self, services):
        super().__init__()
        self.services = services
        self.user = services.store.user() or {}
        self._views = {}
        self.current_view = None
        self._session_warned = False
        self._closing = False

        self.title(APP_TITLE)
        self.geometry("1200x780")
        self.minsize(1040, 680)
        self.configure(bg=COLORS["bg"])

        from .theme import apply_theme
        apply_theme(self)

        self.images = ImageLoader(self)

        # Cola de resultados de los hilos trabajadores (ver run_async).
        self._results = queue.Queue()

        self._build_header()
        self.banner = Banner(self)
        self.banner.pack(fill="x", padx=16, pady=(8, 0))
        self._build_content()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(60, self._drain_results)
        self.after(120, self._bootstrap)

    # ==========================================================================
    # Construccion de la ventana
    # ==========================================================================
    def _build_header(self):
        header = tk.Frame(self, bg=COLORS["surface"], highlightthickness=0)
        header.pack(fill="x")

        # Franja de acento superior.
        tk.Frame(header, bg=COLORS["primary"], height=4).pack(fill="x")

        row = tk.Frame(header, bg=COLORS["surface"])
        row.pack(fill="x", padx=16, pady=(10, 6))

        brand = tk.Frame(row, bg=COLORS["surface"])
        brand.pack(side="left")
        tk.Label(brand, text="Biblioteca UDEM", bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H1).pack(anchor="w")
        tk.Label(brand, text="Cliente de escritorio de los microservicios de Login y Libros",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w")

        # --- zona derecha: semaforos y sesion ---------------------------------
        right = tk.Frame(row, bg=COLORS["surface"])
        right.pack(side="right")

        lights = tk.Frame(right, bg=COLORS["surface"])
        lights.pack(side="left", padx=(0, 14))
        tk.Label(lights, text="Estado de los servicios", bg=COLORS["surface"],
                 fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w")
        self.lights = {}
        for service in ("login", "books"):
            light = StatusLight(lights, service,
                                "Login" if service == "login" else "Libros",
                                on_click=lambda key: self.check_service_now(key),
                                bg=COLORS["surface"])
            light.pack(anchor="w")
            self.lights[service] = light

        tk.Frame(right, bg=COLORS["border"], width=1).pack(side="left", fill="y", padx=12)

        self.user_area = tk.Frame(right, bg=COLORS["surface"])
        self.user_area.pack(side="left")

        # --- navegacion -------------------------------------------------------
        nav = tk.Frame(header, bg=COLORS["surface"])
        nav.pack(fill="x", padx=12, pady=(0, 8))
        self.nav = nav
        tk.Frame(header, bg=COLORS["border"], height=1).pack(fill="x")

        self._render_user_area()
        self._render_nav()

    def _render_nav(self):
        for child in self.nav.winfo_children():
            child.destroy()

        authenticated = bool(self.user)
        buttons = [("Catálogo", "catalog")]
        if authenticated:
            buttons += [("Panel principal", "dashboard"),
                        ("Administración de libros", "books"),
                        ("Sesión y perfil", "profile")]
        buttons += [("Configuración del servidor", "settings")]

        self.nav_buttons = {}
        for label, target in buttons:
            button = ttk.Button(self.nav, text=label, style="Link.TButton",
                                command=lambda t=target: self.show(t))
            button.pack(side="left")
            self.nav_buttons[target] = button

        ttk.Button(self.nav, text="Comprobar ahora", style="Ghost.TButton",
                   command=self.check_services_now).pack(side="right")
        ttk.Label(self.nav, text="El semáforo se actualiza solo; "
                                 "clic en un servicio para revisarlo al instante.",
                  background=COLORS["surface"], foreground=COLORS["muted"],
                  font=FONT_SMALL).pack(side="right", padx=12)

    def _render_user_area(self):
        for child in self.user_area.winfo_children():
            child.destroy()

        if self.user:
            name = " ".join(part for part in (
                self.user.get("nombre"), self.user.get("apellido_paterno")) if part) or "Usuario"
            tk.Label(self.user_area, text=name, bg=COLORS["surface"], fg=COLORS["text"],
                     font=FONT_BOLD).pack(anchor="e")
            tk.Label(self.user_area, text=self.user.get("email") or "", bg=COLORS["surface"],
                     fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="e")

            remaining = self.services.store.remaining_seconds()
            if remaining is not None and 0 < remaining < self.services.config.get("session_warning_seconds"):
                ttk.Button(self.user_area, text=f"Extender sesión ({remaining // 60} min)",
                           style="Primary.TButton", command=self.extend_session).pack(pady=(4, 0))

            ttk.Button(self.user_area, text="Cerrar sesión", style="Ghost.TButton",
                       command=self.logout).pack(pady=(4, 0))
        else:
            tk.Label(self.user_area, text="Sin sesión iniciada", bg=COLORS["surface"],
                     fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="e")
            row = tk.Frame(self.user_area, bg=COLORS["surface"])
            row.pack(pady=(4, 0))
            ttk.Button(row, text="Iniciar sesión", style="Primary.TButton",
                       command=lambda: self.show("login")).pack(side="left")
            ttk.Button(row, text="Registrarse", style="Ghost.TButton",
                       command=lambda: self.show("register")).pack(side="left", padx=(6, 0))

    def _build_content(self):
        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.pack(fill="both", expand=True, padx=16, pady=12)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=COLORS["surface_alt"], highlightthickness=1,
                       highlightbackground=COLORS["border"])
        bar.pack(fill="x", side="bottom")
        inner = tk.Frame(bar, bg=COLORS["surface_alt"])
        inner.pack(fill="x", padx=14, pady=5)

        legend = tk.Frame(inner, bg=COLORS["surface_alt"])
        legend.pack(side="left")
        for state in ("up", "degraded", "down"):
            dot = tk.Canvas(legend, width=12, height=12, highlightthickness=0,
                            bg=COLORS["surface_alt"])
            dot.create_oval(2, 2, 10, 10, fill=STATE_COLORS[state], outline="")
            dot.pack(side="left", padx=(0, 3))
            tk.Label(legend, text=STATE_LABELS[state], bg=COLORS["surface_alt"],
                     fg=COLORS["muted"], font=FONT_SMALL).pack(side="left", padx=(0, 10))

        self.status_label = tk.Label(inner, text="Iniciando...", bg=COLORS["surface_alt"],
                                     fg=COLORS["muted"], font=FONT_SMALL, anchor="w")
        self.status_label.pack(side="left", padx=12)

        self.request_label = tk.Label(inner, text="", bg=COLORS["surface_alt"],
                                      fg=COLORS["muted"], font=FONT_SMALL, anchor="e")
        self.request_label.pack(side="right")

    # ==========================================================================
    # Arranque
    # ==========================================================================
    def _bootstrap(self):
        self.show("catalog")
        self.services.monitor.start()
        self._poll_health()
        self._tick_session()

        if self.services.store.token():
            self.set_status("Validando la sesión guardada contra el servidor...")
            self.run_async(
                lambda: self.services.auth.validate_session(),
                on_done=self._on_session_restored,
                on_error=lambda error: self.handle_error(error, "validar la sesión guardada"),
            )
        else:
            self.set_status("Sin sesión. Puedes consultar el catálogo o iniciar sesión.")

    def _on_session_restored(self, result):
        """Resultado de GET /session al arrancar."""
        user, _session = result
        if user:
            self.user = user
            self._session_warned = False
            self._render_user_area()
            self._render_nav()
            # El aviso va despues de navegar: `show` limpia la franja de avisos.
            self.show("dashboard")
            self.banner.show(
                "Sesión restaurada desde el almacenamiento local y validada contra el servidor. "
                "No fue necesario escribir las credenciales otra vez.", kind="success")
        else:
            self.user = {}
            self._render_user_area()
            self._render_nav()
            self.banner.show(
                "El servidor ya no reconoce la sesión guardada (expiró o fue cerrada). "
                "Se regresó al catálogo: inicia sesión de nuevo.", kind="warning")

    # ==========================================================================
    # Navegacion
    # ==========================================================================
    def _view_factories(self):
        from .view_auth import LoginView, RegisterView
        from .view_book_detail import BookDetailView
        from .view_book_form import BookFormView
        from .view_catalog import CatalogView
        from .view_dashboard import DashboardView
        from .view_profile import ProfileView
        from .view_settings import SettingsView

        return {
            "catalog": lambda master, app, **kw: CatalogView(master, app, mode="public", **kw),
            "books": lambda master, app, **kw: CatalogView(master, app, mode="admin", **kw),
            "login": lambda master, app, **kw: LoginView(master, app, **kw),
            "register": lambda master, app, **kw: RegisterView(master, app, **kw),
            "dashboard": lambda master, app, **kw: DashboardView(master, app, **kw),
            "book_detail": lambda master, app, **kw: BookDetailView(master, app, **kw),
            "book_form": lambda master, app, **kw: BookFormView(master, app, **kw),
            "profile": lambda master, app, **kw: ProfileView(master, app, **kw),
            "settings": lambda master, app, **kw: SettingsView(master, app, **kw),
        }

    def show(self, name, **kwargs):
        """Cambia la pantalla visible. Crea la vista nueva y destruye la anterior."""
        factory = self._view_factories().get(name)
        if factory is None:
            self.set_status(f"Pantalla desconocida: {name}")
            return None

        if self.current_view is not None:
            try:
                self.current_view.on_hide()
            except Exception:
                pass
            self.current_view.destroy()
            self.current_view = None

        try:
            view = factory(self.content, self, **kwargs)
        except Exception as error:                      # nunca debe tumbar la ventana
            self.handle_error(error, f"abrir la pantalla '{name}'")
            return None

        view.pack(fill="both", expand=True)
        self.current_view = view
        self.banner.clear()

        for target, button in getattr(self, "nav_buttons", {}).items():
            button.configure(style="Primary.TButton" if target == name else "Link.TButton")

        try:
            view.on_show()
        except Exception as error:
            self.handle_error(error, f"actualizar la pantalla '{name}'")
        return view

    # ==========================================================================
    # Ejecucion en segundo plano
    # ==========================================================================
    def run_async(self, work, on_done=None, on_error=None, busy=None):
        """Ejecuta `work()` en un hilo y entrega el resultado al hilo de Tk.

        El hilo trabajador NO toca Tkinter: deposita el resultado en una cola y
        el hilo principal la vacia en `_drain_results` (invocado con `after`).
        Llamar a `after` desde otro hilo provoca "main thread is not in main
        loop" cuando el bucle de eventos no esta corriendo; con la cola eso no
        puede ocurrir y la ventana nunca se queda esperando.
        """
        if busy:
            self.set_status(busy)

        def worker():
            try:
                result = work()
            except BaseException as error:              # se reenvia al hilo principal
                self._results.put(("error", error, on_error))
            else:
                self._results.put(("ok", result, on_done))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_results(self):
        """Procesa en el hilo de Tk lo que dejaron los hilos trabajadores."""
        while True:
            try:
                kind, payload, callback = self._results.get_nowait()
            except queue.Empty:
                break

            if self._closing:
                continue
            if kind == "ok":
                self._deliver_done(payload, callback)
            else:
                self._deliver_error(payload, callback)

        if not self._closing:
            self.after(60, self._drain_results)

    def _deliver_done(self, result, on_done):
        if self._closing:
            return
        if on_done:
            try:
                on_done(result)
            except Exception as error:
                self.handle_error(error, "procesar la respuesta del servicio")

    def _deliver_error(self, error, on_error):
        if self._closing:
            return
        if on_error:
            try:
                on_error(error)
                return
            except Exception as inner:
                self.handle_error(inner, "procesar el error del servicio")
                return
        self.handle_error(error, "comunicarse con el servicio")

    # ==========================================================================
    # Errores
    # ==========================================================================
    def handle_error(self, error, context=""):
        """Traduce cualquier falla a un aviso comprensible. Nunca propaga."""
        prefix = f"No fue posible {context}. " if context else ""

        if isinstance(error, ApiError):
            if error.is_session_problem:
                self.services.http.clear_session_token()
                self.services.store.clear_session()
                self.user = {}
                self._render_user_area()
                self._render_nav()
                # Se vuelve al inicio de sesion y LUEGO se avisa: `show` limpia la
                # franja de avisos, asi que el mensaje debe mostrarse despues.
                self.show("login")
                self.banner.show(
                    f"{prefix}El servidor rechazó la sesión: {error.message}",
                    kind="warning", technical=error.technical_summary())
                return
            self.banner.show(f"{prefix}{error.message}", kind="error",
                             technical=error.technical_summary())
            self.set_status(f"Error: {error.message}")
            return

        # Cualquier otra excepcion (bug, dato raro) tampoco debe cerrar la app.
        # El rastro completo se escribe en la consola para poder depurar; al
        # usuario solo se le muestra un mensaje entendible (nunca un traceback).
        print(traceback.format_exc(), file=sys.stderr)
        self.banner.show(
            f"{prefix}Ocurrió un error inesperado en la aplicación.",
            kind="error", technical=f"{type(error).__name__}: {error}")
        self.set_status(f"Error inesperado: {type(error).__name__}")

    # ==========================================================================
    # Estado de los servicios
    # ==========================================================================
    def _poll_health(self):
        for results in self.services.monitor.poll():
            if isinstance(results, dict) and "error" not in results:
                for service, result in results.items():
                    light = self.lights.get(service)
                    if light:
                        light.set_result(result)
                self._last_health = results
                self.set_status(
                    "Estado actualizado: "
                    + " | ".join(f"{r.label} {r.state_label}" for r in results.values()))
            elif isinstance(results, dict):
                self.set_status(f"No se pudo comprobar el estado: {results['error']}")
        if not self._closing:
            self.after(600, self._poll_health)

    def check_services_now(self):
        self.services.monitor.trigger_now()
        self.set_status("Comprobando los dos microservicios...")

    def last_health_results(self):
        """Último resultado conocido de /health por servicio (puede estar vacío)."""
        return getattr(self, "_last_health", {})

    def check_service_now(self, service):
        """Comprobacion inmediata de un solo servicio (clic en el semaforo)."""
        self.set_status(f"Comprobando {service}...")

        def done(result):
            self.lights[service].set_result(result)
            self.banner.show(f"{result.label}: {result.summary()}",
                             kind="success" if result.state == "up" else
                             ("warning" if result.state == "degraded" else "error"),
                             technical=f"{result.base_url} (comprobado {result.checked_at_text()})")

        self.run_async(lambda: self.services.health.check(service), on_done=done)

    # ==========================================================================
    # Sesion
    # ==========================================================================
    def _tick_session(self):
        """Avisa cuando la sesión está por expirar y refresca el aviso del perfil."""
        if self.user:
            remaining = self.services.store.remaining_seconds()
            limit = self.services.config.get("session_warning_seconds")
            if remaining is not None and 0 < remaining <= limit and not self._session_warned:
                self._session_warned = True
                self.banner.show(
                    f"Tu sesión expira en menos de {max(1, remaining // 60)} minuto(s). "
                    "Puedes extenderla desde 'Sesión y perfil' o con el botón de la cabecera.",
                    kind="warning")
                self._render_user_area()
            if remaining is not None and remaining <= 0 and self._session_warned:
                self._session_warned = False
        if not self._closing:
            self.after(5000, self._tick_session)

    def extend_session(self):
        """POST /session/extend."""
        def done(session):
            self._session_warned = False
            self._render_user_area()
            self.banner.show(
                f"Sesión extendida. Nuevo vencimiento: {session.get('expires_at', 'desconocido')}",
                kind="success")
            self.set_status("Sesión extendida correctamente.")

        self.run_async(lambda: self.services.auth.extend_session(), on_done=done,
                       busy="Extendiendo la sesión...")

    def logout(self):
        """Cierra la sesión en el servidor (POST /logout) y limpia el cliente."""
        if not self.user:
            self.show("login")
            return
        from .widgets import confirm
        if not confirm(self, "¿Cerrar la sesión en el servidor?\n\n"
                             "Se llamará a POST /logout y se olvidará el token guardado "
                             "en este equipo. Las credenciales recordadas se conservan "
                             "para el próximo inicio de sesión."):
            return

        def done(error):
            self.user = {}
            self._session_warned = False
            self._render_user_area()
            self._render_nav()
            if error is None:
                self.banner.show("Sesión cerrada en el servidor (POST /logout). "
                                 "El token local fue eliminado.", kind="success")
            else:
                self.banner.show(
                    "El token local se eliminó, pero el servidor no confirmó el cierre: "
                    f"{error.message}", kind="warning", technical=error.technical_summary())
            self.show("catalog")
            self.set_status("Sesión cerrada.")

        self.run_async(lambda: self.services.auth.logout(), on_done=done,
                       busy="Cerrando la sesión en el servidor...")

    def set_user(self, user):
        """Lo llaman las vistas de login/registro tras autenticar."""
        self.user = user or {}
        self._session_warned = False
        self._render_user_area()
        self._render_nav()

    # ==========================================================================
    # Barra de estado y cierre
    # ==========================================================================
    def set_status(self, text):
        if getattr(self, "status_label", None):
            self.status_label.configure(text=text)
        if getattr(self, "request_label", None):
            self.request_label.configure(text=self.services.http.describe_last_request())

    def on_close(self):
        self._closing = True
        try:
            self.services.monitor.stop()
            self.images.shutdown()
        except Exception:
            pass
        self.destroy()

"""Vista base: todas las pantallas heredan de aqui."""

import tkinter as tk

from .theme import COLORS


class BaseView(tk.Frame):
    """Pantalla de la aplicacion.

    `app` da acceso a la configuracion, a los servicios y a la navegacion, de
    modo que las vistas no construyen direcciones ni ejecutan red por su cuenta.

    Detalle importante: una peticion puede tardar mas que la pantalla. Si el
    usuario navega a otra vista antes de que llegue la respuesta, el callback
    apuntaria a widgets ya destruidos y Tkinter lanzaria
    "invalid command name ...". `run_async` envuelve los callbacks y los ignora
    cuando la vista ya no existe, asi que ninguna pantalla se cae por eso.
    """

    #: Titulo mostrado en la barra superior.
    title = "Pantalla"

    def __init__(self, master, app, **kwargs):
        super().__init__(master, bg=COLORS["bg"], **kwargs)
        self.app = app
        self._alive = True
        self.build()

    # ------------------------------------------------------------------ a definir
    def build(self):
        """Construye el contenido de la vista (obligatorio en las hijas)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ opcional
    def on_show(self):
        """Se invoca cada vez que la vista pasa a primer plano."""

    def on_hide(self):
        """Se invoca cuando la vista deja de estar visible."""

    # --------------------------------------------------------------- ciclo vida
    def destroy(self):
        self._alive = False
        super().destroy()

    def is_alive(self):
        return self._alive and bool(self.winfo_exists())

    # ------------------------------------------------------------------ ayudas
    @property
    def services(self):
        return self.app.services

    def run_async(self, work, on_done=None, on_error=None, busy=None):
        """Ejecuta una operacion de red sin bloquear la ventana."""
        return self.app.run_async(work,
                                  on_done=self._guarded(on_done),
                                  on_error=self._guarded(on_error),
                                  busy=busy)

    def _guarded(self, callback):
        """Envuelve un callback para que se ignore si la vista ya se destruyo."""
        if callback is None:
            return None

        def wrapper(value):
            if not self._alive:
                return
            try:
                callback(value)
            except tk.TclError:
                # La ventana se cerro mientras se pintaba la respuesta.
                pass

        return wrapper

    def handle_error(self, error, context=""):
        return self.app.handle_error(error, context=context)

    def notify(self, message, kind="info", technical=None):
        self.app.banner.show(message, kind=kind, technical=technical)

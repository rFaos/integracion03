"""Interfaz grafica (Tkinter).

Reparto de responsabilidades:

    theme.py            -> colores, tipografia y estilos ttk
    widgets.py          -> piezas reutilizables (semaforo, tarjetas, imagenes)
    app_window.py       -> ventana principal, navegacion, sesion y estado
    view_catalog.py     -> catalogo (vista publica y modo administracion)
    view_auth.py        -> inicio de sesion y registro
    view_dashboard.py   -> panel principal
    view_book_detail.py -> detalle del libro (galeria, conceptos, PUT/PATCH/DELETE)
    view_book_form.py   -> alta y edicion de libros
    view_profile.py     -> perfil y sesion
    view_settings.py    -> configuracion de los servidores

Ninguna vista construye direcciones ni usa `urllib`: todo pasa por `core`.
"""

from .base_view import BaseView                                    # noqa: F401
from .app_window import AppWindow                                  # noqa: F401

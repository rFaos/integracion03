"""Catálogo de libros.

Es la vista 1 de la aplicación y también la pantalla de administración, con dos
modos sobre el mismo código:

    mode="public"  -> consulta del catálogo sin necesidad de sesión.
    mode="admin"   -> añade alta, edición y eliminación (requiere sesión).

Se reutiliza la misma rejilla para no duplicar la lógica de consulta y
paginación; lo único que cambia son las acciones disponibles.
"""

import tkinter as tk
from tkinter import ttk

from core.books_service import normalize_book
from core.validators import ValidationError, parse_number

from .base_view import BaseView
from .theme import COLORS, FONT_BOLD, FONT_H2, FONT_SMALL
from .widgets import BookCard, ScrollableFrame, confirm


class CatalogView(BaseView):
    """Catálogo remoto consumido desde GET /books (nunca desde la base de datos)."""

    def __init__(self, master, app, mode="public", **kwargs):
        self.mode = mode
        self.books = []
        self.page = 1
        self.filters = {}
        self.loading = False
        super().__init__(master, app, **kwargs)

    # ==========================================================================
    # Construcción
    # ==========================================================================
    def build(self):
        admin = self.mode == "admin"

        head = tk.Frame(self, bg=COLORS["bg"])
        head.pack(fill="x", pady=(0, 8))

        titles = tk.Frame(head, bg=COLORS["bg"])
        titles.pack(side="left", anchor="w")
        tk.Label(titles, text="Administración de libros" if admin else "Catálogo de libros",
                 bg=COLORS["bg"], fg=COLORS["text"], font=FONT_H2).pack(anchor="w")
        tk.Label(titles,
                 text=("Alta, edición y baja contra el microservicio de libros "
                       "(POST, PUT, PATCH y DELETE).") if admin else
                      ("Consulta del catálogo remoto mediante GET /books. "
                       "Inicia sesión para administrar."),
                 bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w")

        actions = tk.Frame(head, bg=COLORS["bg"])
        actions.pack(side="right")
        if admin:
            ttk.Button(actions, text="Nuevo libro", style="Primary.TButton",
                       command=self.new_book).pack(side="left")
        ttk.Button(actions, text="Recargar", style="Ghost.TButton",
                   command=self.reload).pack(side="left", padx=(6, 0))

        self._build_filters()

        self.count_label = tk.Label(self, text="", bg=COLORS["bg"], fg=COLORS["muted"],
                                    font=FONT_SMALL, anchor="w")
        self.count_label.pack(fill="x", pady=(4, 4))

        self.grid_area = ScrollableFrame(self)
        self.grid_area.pack(fill="both", expand=True)

        self.pager = tk.Frame(self, bg=COLORS["bg"])
        self.pager.pack(fill="x", pady=(8, 0))
        self.prev_button = ttk.Button(self.pager, text="< Anterior", style="Ghost.TButton",
                                      command=lambda: self.go_page(self.page - 1))
        self.prev_button.pack(side="left")
        self.page_label = tk.Label(self.pager, text="", bg=COLORS["bg"], fg=COLORS["text"],
                                   font=FONT_BOLD)
        self.page_label.pack(side="left", padx=12)
        self.next_button = ttk.Button(self.pager, text="Siguiente >", style="Ghost.TButton",
                                      command=lambda: self.go_page(self.page + 1))
        self.next_button.pack(side="left")

    def _build_filters(self):
        """Criterios de búsqueda que admite GET /books/search."""
        box = tk.Frame(self, bg=COLORS["surface"], highlightthickness=1,
                       highlightbackground=COLORS["border"])
        box.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(box, bg=COLORS["surface"])
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="Buscar por", bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_BOLD).grid(row=0, column=0, sticky="w", columnspan=6)
        tk.Label(inner, text="El campo de texto busca en título e ISBN al mismo tiempo.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).grid(
            row=1, column=0, columnspan=6, sticky="w", pady=(0, 6))

        fields = [
            ("text", "Título o ISBN", 22),
            ("author", "Autor", 16),
            ("genre", "Género", 14),
            ("year", "Año", 7),
            ("min_price", "Precio mín.", 9),
            ("max_price", "Precio máx.", 9),
        ]
        self.entries = {}
        for index, (key, label, width) in enumerate(fields):
            column = index
            tk.Label(inner, text=label, bg=COLORS["surface"], fg=COLORS["muted"],
                     font=FONT_SMALL).grid(row=2, column=column, sticky="w", padx=(0, 8))
            entry = ttk.Entry(inner, width=width)
            entry.grid(row=3, column=column, sticky="we", padx=(0, 8))
            entry.bind("<Return>", lambda _e: self.apply_filters())
            self.entries[key] = entry

        buttons = tk.Frame(inner, bg=COLORS["surface"])
        buttons.grid(row=3, column=len(fields), sticky="e")
        ttk.Button(buttons, text="Buscar", style="Primary.TButton",
                   command=self.apply_filters).pack(side="left")
        ttk.Button(buttons, text="Limpiar", style="Ghost.TButton",
                   command=self.clear_filters).pack(side="left", padx=(6, 0))

    # ==========================================================================
    # Ciclo de vida
    # ==========================================================================
    def on_show(self):
        if self.mode == "admin" and not self.app.user:
            self.notify("La administración de libros requiere sesión iniciada. "
                        "Inicia sesión para dar de alta, editar o eliminar libros.", kind="warning")
            self.app.show("login")
            return
        self.reload()

    # ==========================================================================
    # Filtros y paginación
    # ==========================================================================
    def apply_filters(self):
        values = {key: entry.get().strip() for key, entry in self.entries.items()}

        # Validación local del rango de precios: evita una petición con datos
        # incoherentes y avisa antes de molestar al servicio.
        try:
            minimum = parse_number(values["min_price"], "precio mínimo", allow_empty=True)
            maximum = parse_number(values["max_price"], "precio máximo", allow_empty=True)
        except ValidationError as error:
            self.notify(str(error), kind="error")
            return
        if minimum is not None and maximum is not None and minimum > maximum:
            self.notify("El precio mínimo no puede ser mayor que el máximo.", kind="error")
            return

        self.filters = {
            "q": values["text"] or None,
            "author": values["author"] or None,
            "genre": values["genre"] or None,
            "year": values["year"] or None,
            "min_price": values["min_price"] or None,
            "max_price": values["max_price"] or None,
        }
        self.page = 1
        self.load_books()

    def clear_filters(self):
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.filters = {}
        self.page = 1
        self.load_books()

    def reload(self):
        self.load_books()

    def go_page(self, page):
        total_pages = max(1, (len(self.books) + self.page_size - 1) // self.page_size)
        page = max(1, min(page, total_pages))
        if page == self.page:
            return
        self.page = page
        self.render_page()

    @property
    def page_size(self):
        return int(self.app.services.config.get("page_size"))

    # ==========================================================================
    # Carga remota
    # ==========================================================================
    def load_books(self):
        if self.loading:
            return
        self.loading = True
        active = {key: value for key, value in self.filters.items() if value}
        description = f"GET /books/search {active}" if active else "GET /books"
        self.count_label.configure(text=f"Consultando {description} ...")

        def work():
            if active:
                raw = self.services.books.search(**self.filters)
            else:
                raw = self.services.books.list_books()
            return [normalize_book(item) for item in raw]

        self.run_async(work, on_done=self._on_loaded, on_error=self._on_load_error,
                       busy=f"Consultando {description} ...")

    def _on_loaded(self, books):
        self.loading = False
        self.load_error = None
        self.books = books
        self.render_page()
        self.app.set_status(f"Catálogo actualizado: {len(books)} libro(s).")

    def _on_load_error(self, error):
        self.loading = False
        self.books = []
        self.load_error = error
        self.render_page()
        self.handle_error(error, "consultar el catálogo de libros")

    # ==========================================================================
    # Pintado
    # ==========================================================================
    def render_page(self):
        for child in self.grid_area.inner.winfo_children():
            child.destroy()

        total = len(self.books)
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.page = min(self.page, total_pages)

        active = {key: value for key, value in self.filters.items() if value}
        suffix = f" (filtros: {', '.join(f'{k}={v}' for k, v in active.items())})" if active else ""
        if self.load_error is not None:
            self.count_label.configure(
                text="No fue posible consultar el catálogo: el microservicio de libros "
                     "no respondió. Revisa su estado en la cabecera e inténtalo de nuevo.")
        else:
            self.count_label.configure(
                text=f"{total} libro(s) encontrado(s){suffix}. "
                     f"Los datos provienen del microservicio de libros, no de la base de datos.")

        start = (self.page - 1) * self.page_size
        for index, book in enumerate(self.books[start:start + self.page_size]):
            card = BookCard(
                self.grid_area.inner, book,
                on_open=self.open_detail,
                image_loader=self.app.images,
                on_edit=self.edit_book if self.mode == "admin" else None,
                on_delete=self.delete_book if self.mode == "admin" else None,
                show_actions=self.mode == "admin",
            )
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=8)

        self.grid_area.inner.grid_columnconfigure(0, weight=1)
        self.grid_area.inner.grid_columnconfigure(1, weight=1)
        self.grid_area.reset_scroll()

        if total == 0:
            if self.load_error is not None:
                empty_text = ("El catálogo no pudo cargarse. Comprueba el estado del "
                              "microservicio de libros y pulsa \"Recargar\".")
                empty_color = COLORS["danger"]
            elif active:
                empty_text = "No hay libros que coincidan con la búsqueda."
                empty_color = COLORS["muted"]
            else:
                empty_text = "El catálogo está vacío: todavía no hay libros registrados."
                empty_color = COLORS["muted"]
            tk.Label(self.grid_area.inner, text=empty_text,
                     bg=COLORS["bg"], fg=empty_color, font=FONT_SMALL,
                     wraplength=620, justify="center").grid(
                row=0, column=0, columnspan=2, pady=30)

        self.page_label.configure(text=f"Página {self.page} de {total_pages}")
        self.prev_button.configure(state="normal" if self.page > 1 else "disabled")
        self.next_button.configure(state="normal" if self.page < total_pages else "disabled")

    # ==========================================================================
    # Acciones
    # ==========================================================================
    def open_detail(self, book):
        self.app.show("book_detail", book=book)

    def new_book(self):
        self.app.show("book_form", book=None)

    def edit_book(self, book):
        self.app.show("book_form", book=book)

    def delete_book(self, book):
        """DELETE /books/{isbn} con confirmación previa obligatoria."""
        isbn = book.get("isbn")
        if not confirm(self,
                       f"¿Eliminar el libro?\n\n"
                       f"Título: {book.get('title')}\nISBN: {isbn}\n\n"
                       "El libro desaparecerá del catálogo y esta acción no se puede deshacer.",
                       title="Confirmar eliminación",
                       detail=f"DELETE {self.services.config.base_url('books')}/books/{isbn}",
                       confirm_text="Sí, eliminar"):
            return

        def done(_result):
            self.notify(f"Libro eliminado: {book.get('title')} (ISBN {isbn}).", kind="success")
            self.load_books()

        self.run_async(lambda: self.services.books.delete(isbn), on_done=done,
                       on_error=lambda error: self.handle_error(error, f"eliminar el libro {isbn}"),
                       busy=f"Eliminando {isbn}...")

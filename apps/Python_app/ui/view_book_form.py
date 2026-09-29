"""Alta y edición de libros.

Se usa para dos operaciones distintas, y la pantalla lo dice explícitamente:

    mode="create" -> POST /books        (alta; el ISBN es obligatorio)
    mode="put"    -> PUT  /books/{isbn} (reemplazo completo de la representación)

La modificación parcial (PATCH) no vive aquí, sino en el detalle del libro,
porque PATCH solo envía el atributo que cambia.
"""

import json
import tkinter as tk
from tkinter import ttk

from core.validators import ValidationError, validate_book_form

from .base_view import BaseView
from .theme import COLORS, FONT_BOLD, FONT_H2, FONT_MONO, FONT_SMALL
from .widgets import ScrollableFrame


class BookFormView(BaseView):
    """Formulario de alta (POST) o de reemplazo completo (PUT)."""

    def __init__(self, master, app, book=None, mode="create", **kwargs):
        self.book = book or {}
        self.mode = mode
        self.catalogs = {"formats": [], "categories": [], "authors": [], "genres": []}
        self.fields = {}
        super().__init__(master, app, **kwargs)

    @property
    def is_put(self):
        return self.mode == "put"

    # ==========================================================================
    def build(self):
        head = tk.Frame(self, bg=COLORS["bg"])
        head.pack(fill="x", pady=(0, 8))
        ttk.Button(head, text="< Volver", style="Link.TButton",
                   command=self.go_back).pack(side="left")
        title = "Reemplazo completo del libro (PUT)" if self.is_put else "Registrar un libro nuevo"
        tk.Label(head, text=title, bg=COLORS["bg"], fg=COLORS["text"],
                 font=FONT_H2).pack(side="left", padx=12)

        explanation = (
            f"PUT /books/{self.book.get('isbn')} reemplaza la representación completa del libro: "
            "se envían TODOS los atributos editables. El ISBN no se modifica (identifica al recurso)."
            if self.is_put else
            "POST /books crea el libro con sus relaciones (autores, géneros e imágenes) en una sola "
            "transacción. El ISBN debe ser único: si ya existe, el servicio responde 409."
        )
        tk.Label(self, text=explanation, bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL,
                 justify="left", wraplength=1000).pack(anchor="w", pady=(0, 8))

        area = tk.Frame(self, bg=COLORS["bg"])
        area.pack(fill="both", expand=True)
        area.columnconfigure(0, weight=3)
        area.columnconfigure(1, weight=2)
        area.rowconfigure(0, weight=1)

        form_card = tk.Frame(area, bg=COLORS["surface"], highlightthickness=1,
                             highlightbackground=COLORS["border"])
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.scroll = ScrollableFrame(form_card, bg=COLORS["surface"])
        self.scroll.pack(fill="both", expand=True, padx=14, pady=12)
        self.form = self.scroll.inner

        self._build_fields()

        # --- columna derecha: cuerpo que se enviará ---------------------------
        preview_card = tk.Frame(area, bg=COLORS["surface"], highlightthickness=1,
                                highlightbackground=COLORS["border"])
        preview_card.grid(row=0, column=1, sticky="nsew")
        inner = tk.Frame(preview_card, bg=COLORS["surface"])
        inner.pack(fill="both", expand=True, padx=14, pady=12)
        tk.Label(inner, text="Cuerpo JSON que se enviará", bg=COLORS["surface"],
                 fg=COLORS["text"], font=FONT_BOLD).pack(anchor="w")
        tk.Label(inner, text="Permite explicar exactamente qué información viaja al microservicio.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w",
                                                                                 pady=(0, 6))
        self.preview = tk.Label(inner, text="", bg=COLORS["surface_alt"], fg=COLORS["text"],
                                font=FONT_MONO, justify="left", anchor="nw", padx=8, pady=8,
                                wraplength=380)
        self.preview.pack(fill="both", expand=True)

        actions = tk.Frame(self, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(10, 0))
        label = "Enviar PUT (reemplazo completo)" if self.is_put else "Enviar POST (crear libro)"
        ttk.Button(actions, text=label, style="Primary.TButton",
                   command=self.submit).pack(side="left")
        ttk.Button(actions, text="Cancelar", style="Ghost.TButton",
                   command=self.go_back).pack(side="left", padx=6)

    # ==========================================================================
    def _build_fields(self):
        self.fields = {}
        form = self.form

        def label(text, row, column=0, span=2):
            tk.Label(form, text=text, bg=COLORS["surface"], fg=COLORS["text"],
                     font=FONT_SMALL).grid(row=row, column=column, columnspan=span,
                                           sticky="w", pady=(8, 0))

        def entry(key, row, column=0, width=30, state="normal"):
            widget = ttk.Entry(form, width=width, state=state)
            widget.grid(row=row + 1, column=column, sticky="we", padx=(0, 10))
            self.fields[key] = widget
            return widget

        label("ISBN *", 0)
        label("Título *", 0, column=1)
        isbn_state = "readonly" if self.is_put else "normal"
        isbn_entry = entry("isbn", 0, width=22, state=isbn_state)
        if self.is_put:
            isbn_entry.configure(state="normal")
            isbn_entry.insert(0, self.book.get("isbn") or "")
            isbn_entry.configure(state="readonly")
        entry("title", 0, column=1, width=40)

        label("Año de publicación *", 2)
        label("Precio *", 2, column=1)
        entry("publication_year", 2, width=22)
        entry("price", 2, column=1, width=40)

        label("Existencia *", 4)
        label("Formato *", 4, column=1)
        entry("stock", 4, width=22)
        self.format_box = ttk.Combobox(form, state="readonly", width=38)
        self.format_box.grid(row=5, column=1, sticky="we", padx=(0, 10))

        label("Categoría *", 6)
        self.category_box = ttk.Combobox(form, state="readonly", width=38)
        self.category_box.grid(row=7, column=0, sticky="we", padx=(0, 10))

        label("Autores (selección múltiple)", 8)
        authors_frame = tk.Frame(form, bg=COLORS["surface"])
        authors_frame.grid(row=9, column=0, sticky="nsew", padx=(0, 10))
        self.authors_list = tk.Listbox(authors_frame, selectmode="extended", height=6,
                                       exportselection=False, font=FONT_SMALL,
                                       highlightthickness=1, highlightbackground=COLORS["border"])
        self.authors_list.pack(side="left", fill="both", expand=True)
        ttk.Scrollbar(authors_frame, orient="vertical",
                      command=self.authors_list.yview).pack(side="right", fill="y")
        self.authors_list.configure(yscrollcommand=lambda *args: None)

        label("Géneros (selección múltiple)", 8, column=1)
        genres_frame = tk.Frame(form, bg=COLORS["surface"])
        genres_frame.grid(row=9, column=1, sticky="nsew", padx=(0, 10))
        self.genres_list = tk.Listbox(genres_frame, selectmode="extended", height=6,
                                      exportselection=False, font=FONT_SMALL,
                                      highlightthickness=1, highlightbackground=COLORS["border"])
        self.genres_list.pack(side="left", fill="both", expand=True)
        ttk.Scrollbar(genres_frame, orient="vertical",
                      command=self.genres_list.yview).pack(side="right", fill="y")

        label("Imágenes (una URL por línea; la primera será la portada)", 10, span=2)
        self.images_text = tk.Text(form, height=4, width=80, font=FONT_SMALL,
                                   highlightthickness=1, highlightbackground=COLORS["border"])
        self.images_text.grid(row=11, column=0, columnspan=2, sticky="we", pady=(2, 0))

        tk.Label(form, text="* Campos obligatorios. El título admite hasta 200 caracteres y el "
                            "ISBN hasta 20.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL,
                 justify="left").grid(row=12, column=0, columnspan=2, sticky="w", pady=(8, 0))

        for widget in (self.fields["isbn"], self.fields["title"], self.fields["publication_year"],
                       self.fields["price"], self.fields["stock"]):
            widget.bind("<KeyRelease>", lambda _e: self.update_preview())

    # ==========================================================================
    def on_show(self):
        self.load_catalogs()

    def load_catalogs(self):
        """GET /catalogs para poblar formatos, categorías, autores y géneros."""

        def done(catalogs):
            self.catalogs = catalogs
            self._fill_catalogs()
            self._prefill()

        self.run_async(lambda: self.services.books.catalogs(), on_done=done,
                       on_error=lambda error: self.handle_error(
                           error, "obtener las listas de formatos, categorías, autores y géneros"),
                       busy="Consultando las listas de apoyo...")

    def _fill_catalogs(self):
        self.format_box.configure(values=[f"{item['id']} - {item['name']}"
                                          for item in self.catalogs["formats"]])
        self.category_box.configure(values=[f"{item['id']} - {item['name']}"
                                           for item in self.catalogs["categories"]])
        self.authors_list.delete(0, "end")
        for item in self.catalogs["authors"]:
            self.authors_list.insert("end", f"{item['id']} - {item['name']}")
        self.genres_list.delete(0, "end")
        for item in self.catalogs["genres"]:
            self.genres_list.insert("end", f"{item['id']} - {item['name']}")

    def _prefill(self):
        """Rellena el formulario (modo PUT) con el libro recibido."""
        if not self.book:
            self.update_preview()
            return

        self.fields["title"].insert(0, str(self.book.get("title") or ""))
        self.fields["publication_year"].insert(0, str(self.book.get("year") or ""))
        self.fields["price"].insert(0, str(self.book.get("price") if self.book.get("price") is not None else ""))
        self.fields["stock"].insert(0, str(self.book.get("stock") if self.book.get("stock") is not None else ""))

        format_id = self.book.get("format_id")
        for index, item in enumerate(self.catalogs["formats"]):
            if format_id is not None and int(item["id"]) == int(format_id):
                self.format_box.current(index)
        category_id = self.book.get("category_id")
        for index, item in enumerate(self.catalogs["categories"]):
            if category_id is not None and int(item["id"]) == int(category_id):
                self.category_box.current(index)

        for wanted, widget in ((self.book.get("author_ids") or [], self.authors_list),
                               (self.book.get("genre_ids") or [], self.genres_list)):
            for index in range(widget.size()):
                identifier = int(widget.get(index).split(" - ")[0])
                if identifier in wanted:
                    widget.selection_set(index)

        urls = self.book.get("image_urls") or []
        if urls:
            self.images_text.insert("1.0", "\n".join(urls))

        self.update_preview()

    # ==========================================================================
    # Previsualización del cuerpo
    # ==========================================================================
    def _collect(self):
        """Reúne los valores del formulario tal como se enviarían."""
        def text_of(key):
            widget = self.fields[key]
            try:
                return widget.get().strip()
            except tk.TclError:
                return ""

        return {
            "isbn": text_of("isbn"),
            "title": text_of("title"),
            "publication_year": text_of("publication_year"),
            "price": text_of("price"),
            "stock": text_of("stock"),
            "format_id": self.format_box.get().split(" - ")[0] if self.format_box.get() else "",
            "category_id": self.category_box.get().split(" - ")[0] if self.category_box.get() else "",
            "author_ids": [int(self.authors_list.get(i).split(" - ")[0])
                           for i in self.authors_list.curselection()],
            "genre_ids": [int(self.genres_list.get(i).split(" - ")[0])
                          for i in self.genres_list.curselection()],
            "images_text": self.images_text.get("1.0", "end"),
        }

    def update_preview(self):
        try:
            payload = validate_book_form(self._collect(), is_new=not self.is_put)
        except ValidationError as error:
            self.preview.configure(text=f"Faltan datos o hay un error:\n{error}")
            return
        if self.is_put:
            payload.pop("isbn", None)
        self.preview.configure(text=json.dumps(payload, indent=2, ensure_ascii=False))

    # ==========================================================================
    # Envío
    # ==========================================================================
    def submit(self):
        try:
            payload = validate_book_form(self._collect(), is_new=not self.is_put)
        except ValidationError as error:
            self.notify(str(error), kind="error")
            return

        if self.is_put:
            isbn = self.book.get("isbn")
            payload.pop("isbn", None)
            work = lambda: self.services.books.replace(isbn, payload)
            success = f"PUT aplicado: la representación completa de {isbn} fue reemplazada."
            context = f"reemplazar el libro {isbn}"
            busy = f"Enviando PUT de {isbn}..."
        else:
            work = lambda: self.services.books.create(payload)
            success = f"POST correcto: el libro {payload['isbn']} quedó registrado."
            context = "registrar el libro"
            busy = "Enviando POST para crear el libro..."

        def done(_result):
            # Primero se navega y despues se avisa: `show` limpia la franja de avisos.
            self.app.show("books" if self.app.user else "catalog")
            self.notify(success + " Se recargó el catálogo para reflejarlo.", kind="success")

        self.run_async(work, on_done=done,
                       on_error=lambda error: self.handle_error(error, context), busy=busy)

    def go_back(self):
        if self.is_put and self.book.get("isbn"):
            self.app.show("book_detail", book=self.book)
        else:
            self.app.show("books" if self.app.user else "catalog")

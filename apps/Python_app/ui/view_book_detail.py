"""Detalle de un libro.

Consume `GET /books/{isbn}` y permite ejercitar las tres operaciones de
escritura sobre un recurso concreto:

    PATCH  /books/{isbn}   modificación parcial (solo el atributo elegido)
    PUT    /books/{isbn}   reemplazo completo de la representación
    DELETE /books/{isbn}   baja, con confirmación previa

La pantalla muestra en todo momento el cuerpo JSON exacto que se enviará, para
poder explicar qué información viaja al servidor y por qué se eligió PUT o PATCH.
"""

import json
import tkinter as tk
from tkinter import ttk

from core.books_service import normalize_book
from core.validators import ValidationError, parse_int, parse_number

from .base_view import BaseView
from .theme import COLORS, FONT_BOLD, FONT_H2, FONT_H3, FONT_MONO, FONT_SMALL
from .widgets import CoverBox, ScrollableFrame, confirm, format_money, format_text

# Atributos que se pueden modificar con PATCH y cómo se convierten.
PATCHABLE = {
    "title": ("Título (texto)", "text"),
    "publication_year": ("Año de publicación (entero)", "int"),
    "price": ("Precio (número)", "number"),
    "stock": ("Existencia (entero)", "int"),
}


class BookDetailView(BaseView):
    """Ficha completa del libro."""

    def __init__(self, master, app, book=None, **kwargs):
        self.book = book or {}
        self.isbn = self.book.get("isbn")
        self.detail = None
        self.images = []
        self.image_index = 0
        super().__init__(master, app, **kwargs)

    # ==========================================================================
    def build(self):
        head = tk.Frame(self, bg=COLORS["bg"])
        head.pack(fill="x", pady=(0, 8))
        ttk.Button(head, text="< Volver al catálogo", style="Link.TButton",
                   command=lambda: self.app.show("books" if self.app.user else "catalog")
                   ).pack(side="left")
        tk.Label(head, text="Detalle del libro", bg=COLORS["bg"], fg=COLORS["text"],
                 font=FONT_H2).pack(side="left", padx=12)
        ttk.Button(head, text="Recargar (GET)", style="Ghost.TButton",
                   command=self.load_detail).pack(side="right")
        self.title_label = tk.Label(head, text="", bg=COLORS["bg"], fg=COLORS["muted"],
                                    font=FONT_SMALL)
        self.title_label.pack(side="right", padx=12)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # --- columna izquierda: galería ---------------------------------------
        left = tk.Frame(body, bg=COLORS["surface"], highlightthickness=1,
                        highlightbackground=COLORS["border"])
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        inner_left = tk.Frame(left, bg=COLORS["surface"])
        inner_left.pack(padx=16, pady=16)

        self.cover = CoverBox(inner_left, size=(220, 300), text="Sin imagen registrada")
        self.cover.pack()

        gallery = tk.Frame(inner_left, bg=COLORS["surface"])
        gallery.pack(fill="x", pady=(8, 0))
        self.prev_image = ttk.Button(gallery, text="<", style="Ghost.TButton", width=3,
                                     command=lambda: self.change_image(-1))
        self.prev_image.pack(side="left")
        self.image_label = tk.Label(gallery, text="", bg=COLORS["surface"], fg=COLORS["muted"],
                                    font=FONT_SMALL)
        self.image_label.pack(side="left", expand=True)
        self.next_image = ttk.Button(gallery, text=">", style="Ghost.TButton", width=3,
                                     command=lambda: self.change_image(1))
        self.next_image.pack(side="right")

        # --- columna derecha: datos ------------------------------------------
        right = tk.Frame(body, bg=COLORS["surface"], highlightthickness=1,
                         highlightbackground=COLORS["border"])
        right.grid(row=0, column=1, sticky="nsew")
        inner_right = tk.Frame(right, bg=COLORS["surface"])
        inner_right.pack(fill="both", expand=True, padx=16, pady=14)

        self.fields_text = tk.Label(inner_right, text="Cargando...", bg=COLORS["surface"],
                                    fg=COLORS["text"], font=FONT_SMALL, justify="left",
                                    anchor="w")
        self.fields_text.pack(anchor="w")

        tk.Frame(inner_right, bg=COLORS["border"], height=1).pack(fill="x", pady=10)

        tk.Label(inner_right, text="Modificar parcialmente (PATCH /books/{isbn})",
                 bg=COLORS["surface"], fg=COLORS["text"], font=FONT_H3).pack(anchor="w")
        tk.Label(inner_right,
                 text="PATCH envía únicamente los atributos modificados: el resto del libro "
                      "queda como estaba. Es lo correcto para un cambio puntual, por ejemplo "
                      "ajustar la existencia.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, justify="left",
                 wraplength=620).pack(anchor="w", pady=(2, 6))

        patch_row = tk.Frame(inner_right, bg=COLORS["surface"])
        patch_row.pack(fill="x")
        self.patch_field = ttk.Combobox(patch_row, state="readonly", width=28,
                                        values=[f"{key} - {label}" for key, (label, _t) in PATCHABLE.items()])
        self.patch_field.current(3)
        self.patch_field.pack(side="left")
        self.patch_value = ttk.Entry(patch_row, width=18)
        self.patch_value.pack(side="left", padx=6)
        self.patch_value.bind("<KeyRelease>", lambda _e: self.update_patch_preview())
        self.patch_field.bind("<<ComboboxSelected>>", lambda _e: self.update_patch_preview())
        ttk.Button(patch_row, text="Enviar PATCH", style="Primary.TButton",
                   command=self.send_patch).pack(side="left")

        self.patch_preview = tk.Label(inner_right, text="", bg=COLORS["surface_alt"],
                                      fg=COLORS["text"], font=FONT_MONO, justify="left",
                                      anchor="w", padx=8, pady=6)
        self.patch_preview.pack(fill="x", pady=(6, 0))

        tk.Frame(inner_right, bg=COLORS["border"], height=1).pack(fill="x", pady=10)

        tk.Label(inner_right, text="Modificar completamente (PUT /books/{isbn})",
                 bg=COLORS["surface"], fg=COLORS["text"], font=FONT_H3).pack(anchor="w")
        tk.Label(inner_right,
                 text="PUT reemplaza la representación completa del libro: se envían todos los "
                      "atributos editables. Si falta alguno, el servicio responde 400 y no "
                      "modifica nada.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, justify="left",
                 wraplength=620).pack(anchor="w", pady=(2, 6))

        actions = tk.Frame(inner_right, bg=COLORS["surface"])
        actions.pack(anchor="w")
        ttk.Button(actions, text="Abrir formulario de reemplazo (PUT)", style="Ghost.TButton",
                   command=self.open_replace_form).pack(side="left")
        ttk.Button(actions, text="Eliminar libro (DELETE)", style="Danger.TButton",
                   command=self.delete_book).pack(side="left", padx=6)

        # --- conceptos --------------------------------------------------------
        tk.Frame(inner_right, bg=COLORS["border"], height=1).pack(fill="x", pady=10)
        tk.Label(inner_right, text="Conceptos y definiciones asociados",
                 bg=COLORS["surface"], fg=COLORS["text"], font=FONT_H3).pack(anchor="w")
        self.concepts_area = ScrollableFrame(inner_right, bg=COLORS["surface"], height=150)
        self.concepts_area.pack(fill="both", expand=True, pady=(4, 0))

    # ==========================================================================
    def on_show(self):
        if not self.isbn:
            self.notify("No se recibió el ISBN del libro a consultar.", kind="error")
            return
        self.load_detail()

    # ==========================================================================
    # Carga
    # ==========================================================================
    def load_detail(self):
        self.fields_text.configure(text="Consultando GET /books/" + str(self.isbn) + " ...")
        self.run_async(lambda: self.services.books.get_book(self.isbn),
                       on_done=self._on_loaded,
                       on_error=lambda error: self.handle_error(
                           error, f"consultar el libro {self.isbn}"),
                       busy=f"Consultando el libro {self.isbn}...")

    def _on_loaded(self, payload):
        self.detail = normalize_book(payload)
        self.book = self.detail
        self.images = self.detail["images"]
        self.image_index = 0

        self.title_label.configure(text=f"ISBN {self.detail['isbn']}")
        self.fields_text.configure(text=(
            f"Título: {self.detail['title']}\n"
            f"ISBN: {self.detail['isbn']}\n"
            f"Autor(es): {self.detail['authors']}\n"
            f"Género(s): {self.detail['genres']}\n"
            f"Año: {format_text(self.detail['year'])}\n"
            f"Precio: {format_money(self.detail['price'])}\n"
            f"Existencia: {format_text(self.detail['stock'])}\n"
            f"Formato: {format_text(self.detail['format_name'])}\n"
            f"Categoría: {format_text(self.detail['category_name'])}"
        ))
        self.render_images()
        self.render_concepts()
        self.update_patch_preview()
        self.app.set_status(f"Detalle cargado para {self.detail['isbn']} "
                            f"({len(self.images)} imagen(es), {len(self.detail['concepts'])} concepto(s)).")

    # ==========================================================================
    # Galería
    # ==========================================================================
    def render_images(self):
        if not self.images:
            self.cover.set_text("Este libro no tiene\nimágenes registradas")
            self.image_label.configure(text="0 imágenes")
            self.prev_image.configure(state="disabled")
            self.next_image.configure(state="disabled")
            return

        self.cover.set_text("Cargando imagen...")
        image = self.images[self.image_index]
        self.app.images.get(image["url"], (220, 300), self.cover.show_photo)
        self.image_label.configure(
            text=f"Imagen {self.image_index + 1} de {len(self.images)}"
                 + (" (portada)" if image.get("is_cover") else ""))
        self.prev_image.configure(state="normal" if len(self.images) > 1 else "disabled")
        self.next_image.configure(state="normal" if len(self.images) > 1 else "disabled")

    def change_image(self, delta):
        if not self.images:
            return
        self.image_index = (self.image_index + delta) % len(self.images)
        self.render_images()

    # ==========================================================================
    # Conceptos
    # ==========================================================================
    def render_concepts(self):
        for child in self.concepts_area.inner.winfo_children():
            child.destroy()

        concepts = self.detail["concepts"]
        if not concepts:
            tk.Label(self.concepts_area.inner,
                     text="El microservicio no tiene conceptos asociados a este libro.",
                     bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w")
            return

        for concept in concepts:
            block = tk.Frame(self.concepts_area.inner, bg=COLORS["surface"])
            block.pack(fill="x", pady=(0, 8), anchor="w")
            tk.Label(block, text=concept["name"], bg=COLORS["surface"], fg=COLORS["text"],
                     font=FONT_BOLD, anchor="w").pack(anchor="w")
            if concept["summary"]:
                tk.Label(block, text=concept["summary"], bg=COLORS["surface"],
                         fg=COLORS["muted"], font=FONT_SMALL, anchor="w", justify="left",
                         wraplength=700).pack(anchor="w")
            if concept["definition"]:
                tk.Label(block, text=concept["definition"], bg=COLORS["surface"],
                         fg=COLORS["text"], font=FONT_SMALL, anchor="w", justify="left",
                         wraplength=700).pack(anchor="w")
            if concept["page"]:
                tk.Label(block, text=f"Página / capítulo: {concept['page']}",
                         bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL,
                         anchor="w").pack(anchor="w")

    # ==========================================================================
    # PATCH
    # ==========================================================================
    def _selected_field(self):
        return self.patch_field.get().split(" - ")[0]

    def _patch_payload(self):
        field = self._selected_field()
        label, kind = PATCHABLE[field]
        raw = self.patch_value.get().strip()
        if not raw:
            return None, field
        if kind == "int":
            value = parse_int(raw, label)
        elif kind == "number":
            value = parse_number(raw, label)
        else:
            value = raw
        return {field: value}, field

    def update_patch_preview(self):
        try:
            payload, _field = self._patch_payload()
        except ValidationError as error:
            self.patch_preview.configure(text=f"Valor inválido: {error}")
            return
        if payload is None:
            self.patch_preview.configure(
                text=f"Se enviará PATCH /books/{self.isbn} con el atributo elegido y su nuevo valor.")
            return
        self.patch_preview.configure(
            text=f"PATCH /books/{self.isbn}\n{json.dumps(payload, ensure_ascii=False)}")

    def send_patch(self):
        try:
            payload, field = self._patch_payload()
        except ValidationError as error:
            self.notify(str(error), kind="error")
            return
        if not payload:
            self.notify("Escribe el nuevo valor del atributo a modificar.", kind="warning")
            return

        def done(result):
            modified = ", ".join(result.get("modified_fields") or [])
            self.notify(f"PATCH aplicado. Atributos modificados: {modified}. "
                        "Se recarga el libro con GET para comprobarlo.", kind="success")
            self.load_detail()

        self.run_async(lambda: self.services.books.patch(self.isbn, payload), on_done=done,
                       on_error=lambda error: self.handle_error(
                           error, f"modificar parcialmente el libro {self.isbn}"),
                       busy=f"Enviando PATCH de {field}...")

    # ==========================================================================
    # PUT y DELETE
    # ==========================================================================
    def open_replace_form(self):
        if not self.detail:
            self.notify("Todavía no se cargó el detalle del libro.", kind="warning")
            return
        self.app.show("book_form", book=self.detail, mode="put")

    def delete_book(self):
        if not confirm(self,
                       f"¿Eliminar el libro?\n\nTítulo: {self.detail['title'] if self.detail else self.isbn}\n"
                       f"ISBN: {self.isbn}\n\nSe enviará DELETE /books/{self.isbn}."):
            return

        def done(_result):
            # Primero se navega y despues se avisa: `show` limpia la franja de avisos.
            self.app.show("books" if self.app.user else "catalog")
            self.notify(f"Libro eliminado: {self.isbn}. Se regresó al catálogo.", kind="success")

        self.run_async(lambda: self.services.books.delete(self.isbn), on_done=done,
                       on_error=lambda error: self.handle_error(
                           error, f"eliminar el libro {self.isbn}"),
                       busy=f"Eliminando {self.isbn}...")

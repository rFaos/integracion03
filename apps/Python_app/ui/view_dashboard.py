"""Panel principal.

Aparece después de una autenticación correcta y separa con claridad los cinco
bloques que pide la actividad:

    1. Sesión y perfil
    2. Catálogo de libros
    3. Administración de libros
    4. Estado de los microservicios
    5. Configuración del servidor
"""

import tkinter as tk
from tkinter import ttk

from core.health_service import STATE_COLORS, STATE_LABELS

from .base_view import BaseView
from .theme import COLORS, FONT_H2, FONT_H3, FONT_SMALL, FONT_MONO


class DashboardView(BaseView):
    """Resumen operativo de la aplicación."""

    def build(self):
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="Panel principal", bg=COLORS["bg"], fg=COLORS["text"],
                 font=FONT_H2).pack(anchor="w")
        self.welcome = tk.Label(header, text="", bg=COLORS["bg"], fg=COLORS["muted"],
                                font=FONT_SMALL)
        self.welcome.pack(anchor="w")

        grid = tk.Frame(self, bg=COLORS["bg"])
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(1, weight=1)

        self._session_card(grid, 0, 0)
        self._catalog_card(grid, 0, 1)
        self._services_card(grid, 1, 0)
        self._admin_card(grid, 1, 1)
        self._settings_card(grid, 2, 0)

    # ------------------------------------------------------------------ tarjetas
    def _card(self, parent, row, column, title, subtitle):
        card = tk.Frame(parent, bg=COLORS["surface"], highlightthickness=1,
                        highlightbackground=COLORS["border"])
        card.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
        inner = tk.Frame(card, bg=COLORS["surface"])
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(inner, text=title, bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H3).pack(anchor="w")
        tk.Label(inner, text=subtitle, bg=COLORS["surface"], fg=COLORS["muted"],
                 font=FONT_SMALL, justify="left", wraplength=480).pack(anchor="w", pady=(2, 8))
        return inner

    def _session_card(self, parent, row, column):
        inner = self._card(parent, row, column, "Sesión y perfil",
                           "Datos de la sesión activa, vencimiento y cierre de sesión "
                           "contra el servidor.")
        self.session_text = tk.Label(inner, text="", bg=COLORS["surface"], fg=COLORS["text"],
                                     font=FONT_SMALL, justify="left", anchor="w")
        self.session_text.pack(anchor="w")

        buttons = tk.Frame(inner, bg=COLORS["surface"])
        buttons.pack(anchor="w", pady=(10, 0))
        ttk.Button(buttons, text="Ver perfil y sesión", style="Ghost.TButton",
                   command=lambda: self.app.show("profile")).pack(side="left")
        ttk.Button(buttons, text="Extender sesión", style="Ghost.TButton",
                   command=self.app.extend_session).pack(side="left", padx=6)
        ttk.Button(buttons, text="Cerrar sesión", style="Danger.TButton",
                   command=self.app.logout).pack(side="left")

    def _catalog_card(self, parent, row, column):
        inner = self._card(parent, row, column, "Catálogo de libros",
                           "Consulta del catálogo remoto con búsqueda por título o ISBN, autor, "
                           "género, año y rango de precio.")
        buttons = tk.Frame(inner, bg=COLORS["surface"])
        buttons.pack(anchor="w")
        ttk.Button(buttons, text="Abrir catálogo", style="Primary.TButton",
                   command=lambda: self.app.show("catalog")).pack(side="left")

    def _admin_card(self, parent, row, column):
        inner = self._card(parent, row, column, "Administración de libros",
                           "Alta, modificación total (PUT), modificación parcial (PATCH) y "
                           "eliminación (DELETE) de libros.")
        buttons = tk.Frame(inner, bg=COLORS["surface"])
        buttons.pack(anchor="w")
        ttk.Button(buttons, text="Nuevo libro", style="Primary.TButton",
                   command=lambda: self.app.show("book_form", book=None)).pack(side="left")
        ttk.Button(buttons, text="Administrar catálogo", style="Ghost.TButton",
                   command=lambda: self.app.show("books")).pack(side="left", padx=6)

    def _services_card(self, parent, row, column):
        inner = self._card(parent, row, column, "Estado de los microservicios",
                           "Comprobación periódica de GET /health en los dos servicios. "
                           "Un servicio que responde 503 aparece degradado, no caído: "
                           "está vivo pero su base de datos no.")
        self.service_rows = {}
        for service, label in (("login", "Microservicio de Login"),
                               ("books", "Microservicio de Libros")):
            line = tk.Frame(inner, bg=COLORS["surface"])
            line.pack(anchor="w", fill="x", pady=2)
            dot = tk.Canvas(line, width=14, height=14, highlightthickness=0, bg=COLORS["surface"])
            dot.create_oval(3, 3, 11, 11, fill=COLORS["muted"], outline="", tags="dot")
            dot.pack(side="left")
            text = tk.Label(line, text=f"{label}: sin comprobar", bg=COLORS["surface"],
                            fg=COLORS["text"], font=FONT_SMALL, anchor="w")
            text.pack(side="left", padx=(6, 0))
            self.service_rows[service] = (dot, text)

        legend = tk.Frame(inner, bg=COLORS["surface"])
        legend.pack(anchor="w", pady=(8, 0))
        for state in ("up", "degraded", "down"):
            item = tk.Frame(legend, bg=COLORS["surface"])
            item.pack(side="left", padx=(0, 12))
            dot = tk.Canvas(item, width=12, height=12, highlightthickness=0, bg=COLORS["surface"])
            dot.create_oval(2, 2, 10, 10, fill=STATE_COLORS[state], outline="")
            dot.pack(side="left")
            tk.Label(item, text=STATE_LABELS[state], bg=COLORS["surface"], fg=COLORS["muted"],
                     font=FONT_SMALL).pack(side="left", padx=(4, 0))

        self.last_check = tk.Label(inner, text="", bg=COLORS["surface"], fg=COLORS["muted"],
                                   font=FONT_SMALL)
        self.last_check.pack(anchor="w", pady=(6, 0))

        buttons = tk.Frame(inner, bg=COLORS["surface"])
        buttons.pack(anchor="w", pady=(8, 0))
        ttk.Button(buttons, text="Comprobar ahora", style="Primary.TButton",
                   command=self.app.check_services_now).pack(side="left")
        ttk.Button(buttons, text="Ver configuración", style="Ghost.TButton",
                   command=lambda: self.app.show("settings")).pack(side="left", padx=6)

    def _settings_card(self, parent, row, column):
        inner = self._card(parent, row, column, "Configuración del servidor",
                           "Direcciones de los dos microservicios, tiempos de espera e "
                           "intervalo de comprobación. Se guarda en disco y sobrevive "
                           "al cierre de la aplicación.")
        self.targets_text = tk.Label(inner, text="", bg=COLORS["surface"], fg=COLORS["text"],
                                     font=FONT_MONO, justify="left", anchor="w")
        self.targets_text.pack(anchor="w")
        buttons = tk.Frame(inner, bg=COLORS["surface"])
        buttons.pack(anchor="w", pady=(8, 0))
        ttk.Button(buttons, text="Abrir configuración", style="Primary.TButton",
                   command=lambda: self.app.show("settings")).pack(side="left")

    # ------------------------------------------------------------------- datos
    def on_show(self):
        user = self.app.user or {}
        name = " ".join(part for part in (user.get("nombre"), user.get("apellido_paterno"),
                                          user.get("apellido_materno")) if part) or "(sin nombre)"
        self.welcome.configure(text=f"Sesión iniciada como {name} <{user.get('email') or '-'}>")

        remaining = self.services.store.remaining_seconds()
        if remaining is None:
            remaining_text = "sin vencimiento registrado localmente"
        elif remaining <= 0:
            remaining_text = "vencida según el reloj local (se validará contra el servidor)"
        else:
            remaining_text = f"quedan {remaining // 60} min {remaining % 60} s"
        self.session_text.configure(
            text=f"Usuario: {name}\n"
                 f"Correo: {user.get('email') or '-'}\n"
                 f"Rol: {user.get('role') or '-'}\n"
                 f"Sesión: {remaining_text}\n"
                 f"Token de sesión: {'guardado localmente' if self.services.store.token() else 'no'} "
                 f"(cabecera X-Session-Token)")

        self.targets_text.configure(
            text=f"Login : {self.services.config.base_url('login')}\n"
                 f"Libros: {self.services.config.base_url('books')}")

        self.refresh_services()
        self.app.check_services_now()

    def refresh_services(self):
        results = self.app.last_health_results()
        for service, (canvas, label) in self.service_rows.items():
            result = results.get(service)
            if not result:
                label.configure(text=f"{service}: sin comprobar")
                continue
            canvas.itemconfigure("dot", fill=result.color)
            label.configure(
                text=f"{result.label}: {result.state_label} - {result.headline} "
                     f"(HTTP {result.http_status or '-'}, {result.checked_at_text()})")
        if results:
            newest = max(result.checked_at for result in results.values())
            self.last_check.configure(
                text=f"Última comprobación: {newest.strftime('%Y-%m-%d %H:%M:%S')} "
                     f"(automática cada {self.services.config.get('health_interval_seconds')} s)")
        else:
            self.last_check.configure(text="Todavía no hay resultados de comprobación.")

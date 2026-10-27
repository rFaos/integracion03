"""Configuración del servidor.

Permite cambiar las direcciones de los microservicios SIN tocar el código
fuente, probarlas antes de guardar y persistirlas en disco. El mismo programa
sirve así para los dos escenarios:

    Local   -> http://127.0.0.1:5000 ... :5005
    Remoto  -> http://<host>:5000     ... :5005  (instancia en GCloud)

Además hay un conmutador de **esquema** (http / https): por defecto http, pero
al elegir https se reescriben TODAS las direcciones y la preferencia queda
guardada en `runtime/config.json`, de modo que sobrevive al cierre.

El archivo se guarda en `runtime/config.json`, que está excluido en `.gitignore`
para no subir direcciones ni credenciales propias al repositorio.
"""

import tkinter as tk
from tkinter import ttk

from core.config import CONFIG_PATH, SERVICE_KEYS, SERVICE_LABELS, ConfigError

from .base_view import BaseView
from .theme import COLORS, FONT_BOLD, FONT_H2, FONT_H3, FONT_MONO, FONT_SMALL


class SettingsView(BaseView):
    """Pantalla de configuración de los seis microservicios."""

    # Dos columnas de campos. Los seis puertos remotos NO se editan aqui (usan
    # los valores 5000..5005 y viven en runtime/config.json): meterlos dejaba el
    # formulario mas alto que la ventana y empujaba los botones fuera de vista.
    FIELDS = tuple(
        [(f"{svc}_base_url", f"URL base · {SERVICE_LABELS[svc]}") for svc in SERVICE_KEYS]
        + [("remote_host", "Host de la instancia remota (GCloud), sin http://")]
        + [
            ("request_timeout", "Tiempo de espera por petición (segundos)"),
            ("health_interval_seconds", "Intervalo de comprobación de /health (segundos)"),
            ("session_warning_seconds", "Avisar cuando la sesión tenga menos de (segundos)"),
            ("page_size", "Libros por página en el catálogo"),
        ]
    )

    def build(self):
        head = tk.Frame(self, bg=COLORS["bg"])
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Configuración del servidor", bg=COLORS["bg"], fg=COLORS["text"],
                 font=FONT_H2).pack(side="left")

        tk.Label(self, text=f"Se guarda en: {CONFIG_PATH}", bg=COLORS["bg"], fg=COLORS["muted"],
                 font=FONT_MONO).pack(anchor="w")
        tk.Label(self, text="Este archivo está excluido del repositorio (.gitignore): puede "
                            "contener direcciones propias de tu equipo o de la instancia.",
                 bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w",
                                                                            pady=(0, 8))

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        form_card = tk.Frame(body, bg=COLORS["surface"], highlightthickness=1,
                             highlightbackground=COLORS["border"])
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = tk.Frame(form_card, bg=COLORS["surface"])
        form.pack(fill="both", expand=True, padx=16, pady=14)

        # Dos columnas de campos: 17 filas en una sola columna no caben en la
        # ventana (1200x780) y empujarian los botones fuera de la vista.
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        tk.Label(form, text="Direcciones y parámetros", bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H3).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        # --- conmutador de esquema (http / https), persistente -----------------
        tk.Label(form, text="Esquema (http por defecto; se aplica a TODAS las direcciones)",
                 bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SMALL).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.scheme = tk.StringVar(value="http")
        ttk.Combobox(form, textvariable=self.scheme, values=("http", "https"),
                     state="readonly", width=10).grid(row=1, column=2, sticky="w",
                                                      padx=(10, 0), pady=(4, 0))

        self.fields = {}
        for i, (key, label) in enumerate(self.FIELDS):
            r = 2 + i // 2
            c = 0 if i % 2 == 0 else 2
            tk.Label(form, text=label, bg=COLORS["surface"], fg=COLORS["text"],
                     font=FONT_SMALL).grid(row=r, column=c, sticky="w", pady=(4, 0))
            entry = ttk.Entry(form, width=22)
            entry.grid(row=r, column=c + 1, sticky="we", padx=(8, 14), pady=(4, 0))
            self.fields[key] = entry
        row = 2 + (len(self.FIELDS) + 1) // 2

        self.remember = tk.BooleanVar()
        ttk.Checkbutton(form, text="Recordar credenciales en este equipo al iniciar sesión",
                        variable=self.remember, style="Surface.TCheckbutton").grid(
            row=row, column=0, columnspan=4, sticky="w", pady=(10, 0))
        row += 1

        tk.Label(form, text="La contraseña recordada se guarda ofuscada en base64 dentro de "
                            "runtime/session.json. No es cifrado: cualquiera con acceso al "
                            "archivo puede recuperarla, por eso no se sube al repositorio.\n"
                            "Los puertos remotos son 5000..5005 (login, libros, usuarios, "
                            "autores, pedidos, pagos) y se editan en runtime/config.json.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, justify="left",
                 wraplength=560).grid(row=row, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # --- acciones ---------------------------------------------------------
        actions = tk.Frame(self, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Probar conexión (sin guardar)", style="Ghost.TButton",
                   command=self.test_connection).pack(side="left")
        ttk.Button(actions, text="Guardar", style="Primary.TButton",
                   command=self.save).pack(side="left", padx=6)
        ttk.Button(actions, text="Usar servicios locales", style="Ghost.TButton",
                   command=self.use_local).pack(side="left", padx=(18, 6))
        ttk.Button(actions, text="Usar instancia remota", style="Ghost.TButton",
                   command=self.use_remote).pack(side="left")
        ttk.Button(actions, text="Restaurar predeterminados", style="Danger.TButton",
                   command=self.reset).pack(side="right")

        # --- resultados de la prueba -----------------------------------------
        result_card = tk.Frame(body, bg=COLORS["surface"], highlightthickness=1,
                               highlightbackground=COLORS["border"])
        result_card.grid(row=0, column=1, sticky="nsew")
        inner = tk.Frame(result_card, bg=COLORS["surface"])
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(inner, text="Resultado de la prueba", bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H3).pack(anchor="w")
        tk.Label(inner, text="Prueba contra las direcciones escritas arriba, sin guardarlas. "
                             "Pon un puerto inexistente para ver el estado rojo.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, justify="left",
                 wraplength=200).pack(anchor="w", pady=(2, 8))

        self.results = {}
        for service in SERVICE_KEYS:
            label = SERVICE_LABELS[service]
            line = tk.Frame(inner, bg=COLORS["surface"])
            line.pack(anchor="w", fill="x", pady=3)
            dot = tk.Canvas(line, width=14, height=14, highlightthickness=0, bg=COLORS["surface"])
            dot.create_oval(3, 3, 11, 11, fill=COLORS["muted"], outline="", tags="dot")
            dot.pack(side="left")
            text = tk.Label(line, text=f"{label}: sin probar", bg=COLORS["surface"],
                            fg=COLORS["text"], font=FONT_SMALL, anchor="w", justify="left",
                            wraplength=200)
            text.pack(side="left", padx=(6, 0))
            self.results[service] = (dot, text)

        self.summary = tk.Label(inner, text="", bg=COLORS["surface"], fg=COLORS["muted"],
                                font=FONT_SMALL, justify="left", wraplength=200)
        self.summary.pack(anchor="w", pady=(10, 0))

        tk.Frame(inner, bg=COLORS["border"], height=1).pack(fill="x", pady=10)
        tk.Label(inner, text="Escenario local y remoto", bg=COLORS["surface"],
                 fg=COLORS["text"], font=FONT_BOLD).pack(anchor="w")
        tk.Label(inner, text="Es el mismo programa: no hay dos versiones. Solo cambian estas "
                             "direcciones, y quedan guardadas para el próximo arranque.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, justify="left",
                 wraplength=200).pack(anchor="w", pady=(2, 6))
        self.targets = tk.Label(inner, text="", bg=COLORS["surface_alt"], fg=COLORS["text"],
                                font=FONT_MONO, justify="left", anchor="w", padx=8, pady=6,
                                wraplength=210)
        self.targets.pack(fill="x")

    # ==========================================================================
    def on_show(self):
        self.load_values()

    def load_values(self):
        config = self.services.config
        self.scheme.set(str(config.get("scheme") or "http"))
        for key, _label in self.FIELDS:
            entry = self.fields[key]
            entry.delete(0, "end")
            entry.insert(0, str(config.get(key)))
        self.remember.set(bool(config.get("remember_credentials")))
        self.update_targets()

    def update_targets(self):
        config = self.services.config
        lines = [f"{svc + ':':<9} {config.base_url(svc)}" for svc in SERVICE_KEYS]
        self.targets.configure(text="\n".join(lines))

    def _collect(self):
        values = {key: entry.get().strip() for key, entry in self.fields.items()}
        values["scheme"] = self.scheme.get()
        values["remember_credentials"] = bool(self.remember.get())
        return values

    # ==========================================================================
    def test_connection(self):
        """Comprueba GET /health en las direcciones escritas, sin guardarlas."""
        values = self._collect()

        def work():
            health = self.services.health
            return {svc: health.check(svc, base_url=values.get(f"{svc}_base_url"), timeout=5)
                    for svc in SERVICE_KEYS}

        def done(results):
            lines = []
            for service, (canvas, label) in self.results.items():
                result = results[service]
                canvas.itemconfigure("dot", fill=result.color)
                label.configure(text=f"{result.label}: {result.state_label}\n"
                                     f"{result.headline}\n"
                                     f"{result.base_url} (HTTP {result.http_status or '-'})")
                lines.append(f"{result.label}: {result.state_label} ({result.checked_at_text()})")
            self.summary.configure(text="Prueba completada. " + " | ".join(lines))

        self.run_async(work, on_done=done,
                       on_error=lambda error: self.handle_error(error, "probar la conexión"),
                       busy="Probando la conexión con las direcciones escritas...")

    def save(self):
        try:
            self.services.config.update_from_form(self._collect())
        except ConfigError as error:
            self.notify(f"Revisa la configuración: {error}", kind="error")
            return
        self.services.config.save()
        self.services.apply_config()
        self.load_values()
        self.notify("Configuración guardada. Se aplica de inmediato y queda para el próximo "
                    "arranque.", kind="success")
        self.app.set_status("Configuración guardada.")

    def use_local(self):
        self.services.config.apply_local_preset()
        self.load_values()
        self.notify("Direcciones locales cargadas en el formulario. Pulsa 'Guardar' para "
                    "aplicarlas.", kind="info")

    def use_remote(self):
        self.services.config.apply_remote_preset()
        self.load_values()
        self.notify("Direcciones de la instancia remota cargadas en el formulario. Pulsa "
                    "'Guardar' para aplicarlas.", kind="info")

    def reset(self):
        self.services.config.reset()
        self.services.apply_config()
        self.load_values()
        self.notify("Valores predeterminados restaurados.", kind="success")

"""Perfil del usuario autenticado y control de la sesión.

Operaciones del microservicio de login que se ejercitan aquí:

    GET   /session         -> estado real de la sesión y datos del usuario
    PATCH /profile         -> modificación PARCIAL: solo los campos editados
    POST  /session/extend  -> extiende la vigencia
    GET   /users/<id>      -> recurso REST del usuario
    POST  /logout          -> cierre de sesión

La pantalla muestra el JSON exacto que se enviará con PATCH, de modo que se
pueda explicar que los campos no modificados no viajan al servidor.
"""

import json
import tkinter as tk
from tkinter import ttk

from core.validators import ValidationError, validate_email, validate_password

from .base_view import BaseView
from .theme import COLORS, FONT_BOLD, FONT_H2, FONT_H3, FONT_MONO, FONT_SMALL


class ProfileView(BaseView):
    """Datos de la cuenta y vigencia de la sesión."""

    def build(self):
        head = tk.Frame(self, bg=COLORS["bg"])
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text="Sesión y perfil", bg=COLORS["bg"], fg=COLORS["text"],
                 font=FONT_H2).pack(side="left")
        ttk.Button(head, text="Validar sesión (GET /session)", style="Ghost.TButton",
                   command=self.load_session).pack(side="right")
        ttk.Button(head, text="Recargar", style="Ghost.TButton",
                   command=self.load_session).pack(side="right", padx=6)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # --- sesión -----------------------------------------------------------
        session_card = tk.Frame(body, bg=COLORS["surface"], highlightthickness=1,
                                highlightbackground=COLORS["border"])
        session_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        inner = tk.Frame(session_card, bg=COLORS["surface"])
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(inner, text="Estado de la sesión", bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H3).pack(anchor="w")
        self.session_text = tk.Label(inner, text="Consultando...", bg=COLORS["surface"],
                                     fg=COLORS["text"], font=FONT_SMALL, justify="left",
                                     anchor="w")
        self.session_text.pack(anchor="w", pady=(6, 8))

        actions = tk.Frame(inner, bg=COLORS["surface"])
        actions.pack(anchor="w")
        ttk.Button(actions, text="Extender sesión (POST /session/extend)", style="Primary.TButton",
                   command=self.extend).pack(side="left")
        ttk.Button(actions, text="Cerrar sesión (POST /logout)", style="Danger.TButton",
                   command=self.app.logout).pack(side="left", padx=6)
        ttk.Button(actions, text="Ver GET /users/<id>", style="Ghost.TButton",
                   command=self.show_user_resource).pack(side="left")

        tk.Label(inner, text="El token de sesión viaja en la cabecera X-Session-Token. "
                             "Recordar la sesión localmente no la hace válida: la validez la "
                             "determina el servidor.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, justify="left",
                 wraplength=520).pack(anchor="w", pady=(10, 0))

        # --- edición ----------------------------------------------------------
        edit_card = tk.Frame(body, bg=COLORS["surface"], highlightthickness=1,
                             highlightbackground=COLORS["border"])
        edit_card.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
        edit_inner = tk.Frame(edit_card, bg=COLORS["surface"])
        edit_inner.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(edit_inner, text="Modificar datos (PATCH /profile)", bg=COLORS["surface"],
                 fg=COLORS["text"], font=FONT_H3).pack(anchor="w")
        tk.Label(edit_inner, text="Solo se envían los campos que cambies. Deja vacío lo que no "
                                  "quieras modificar.",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w",
                                                                                pady=(2, 8))

        self.fields = {}
        form = tk.Frame(edit_inner, bg=COLORS["surface"])
        form.pack(fill="x")
        for row, (key, label, secret) in enumerate((
                ("nombre", "Nombre(s)", False),
                ("apellido_paterno", "Apellido paterno", False),
                ("apellido_materno", "Apellido materno", False),
                ("email", "Correo electrónico", False),
                ("password", "Nueva contraseña", True),
                ("current_password", "Contraseña actual (obligatoria para cambiarla)", True))):
            tk.Label(form, text=label, bg=COLORS["surface"], fg=COLORS["muted"],
                     font=FONT_SMALL).grid(row=row * 2, column=0, sticky="w", pady=(6, 0))
            widget = ttk.Entry(form, width=42, show="*" if secret else "")
            widget.grid(row=row * 2 + 1, column=0, sticky="we")
            widget.bind("<KeyRelease>", lambda _e: self.update_preview())
            self.fields[key] = widget
        form.columnconfigure(0, weight=1)

        ttk.Button(form, text="Guardar cambios (PATCH)", style="Primary.TButton",
                   command=self.save).grid(row=12, column=0, sticky="w", pady=(12, 0))

        # --- vista previa del cuerpo -----------------------------------------
        preview_card = tk.Frame(body, bg=COLORS["surface"], highlightthickness=1,
                                highlightbackground=COLORS["border"])
        preview_card.grid(row=1, column=0, columnspan=2, sticky="nsew")
        inner_preview = tk.Frame(preview_card, bg=COLORS["surface"])
        inner_preview.pack(fill="both", expand=True, padx=16, pady=12)
        tk.Label(inner_preview, text="Cuerpo JSON que se enviará", bg=COLORS["surface"],
                 fg=COLORS["text"], font=FONT_BOLD).pack(anchor="w")
        self.preview = tk.Label(inner_preview, text="", bg=COLORS["surface_alt"],
                                fg=COLORS["text"], font=FONT_MONO, justify="left", anchor="w",
                                padx=8, pady=8)
        self.preview.pack(fill="x", pady=(6, 0))

    # ==========================================================================
    def on_show(self):
        self.prefill()
        self.load_session()

    def prefill(self):
        """Carga en el formulario los datos que ya conocemos del usuario."""
        user = self.app.user or {}
        for key in ("nombre", "apellido_paterno", "apellido_materno", "email"):
            widget = self.fields[key]
            widget.delete(0, "end")
            if user.get(key):
                widget.insert(0, str(user[key]))
        self.update_preview()

    def load_session(self):
        """GET /session: confirma contra el servidor que la sesión sigue vigente."""
        self.session_text.configure(text="Consultando GET /session ...")

        def done(result):
            user, session = result
            if not user:
                self.session_text.configure(
                    text="El servidor no reconoce la sesión actual.\n"
                         "Se regresó al inicio de sesión.")
                return
            self.app.set_user(user)
            self.prefill()
            remaining = session.get("remaining_seconds")
            minutes = f"{int(remaining) // 60} min {int(remaining) % 60} s" if remaining is not None else "-"
            self.session_text.configure(text=(
                f"Autenticado: sí\n"
                f"Usuario: {user.get('nombre') or '(sin nombre)'} "
                f"{user.get('apellido_paterno') or ''} {user.get('apellido_materno') or ''}\n"
                f"Correo: {user.get('email') or '-'}\n"
                f"Rol: {user.get('role') or '-'}\n"
                f"Identificador: {user.get('id') or '-'}\n"
                f"Vence: {session.get('expires_at') or '-'}\n"
                f"Tiempo restante según el servidor: {minutes}\n"
                f"Duración de la sesión: {session.get('duration_minutes') or '-'} minutos\n"
                f"Token local: {'presente' if self.services.store.token() else 'ausente'}"))
            self.app.set_status("Sesión validada contra el servidor.")

        self.run_async(lambda: self.services.auth.validate_session(), on_done=done,
                       on_error=lambda error: self.handle_error(error, "consultar la sesión"),
                       busy="Consultando GET /session ...")

    # ==========================================================================
    def extend(self):
        def done(session):
            self.notify(f"Sesión extendida. Nuevo vencimiento: {session.get('expires_at')}",
                        kind="success")
            self.load_session()

        self.run_async(lambda: self.services.auth.extend_session(), on_done=done,
                       on_error=lambda error: self.handle_error(error, "extender la sesión"),
                       busy="Extendiendo la sesión...")

    def show_user_resource(self):
        """GET /users/<id>: recurso REST real del microservicio."""
        user_id = (self.app.user or {}).get("id")
        if not user_id:
            self.notify("No se conoce el identificador del usuario.", kind="warning")
            return

        def done(user):
            self.notify("GET /users/%s devolvió: %s" % (user_id, json.dumps(user, ensure_ascii=False)),
                        kind="success")

        self.run_async(lambda: self.services.auth.get_user(user_id), on_done=done,
                       on_error=lambda error: self.handle_error(
                           error, f"consultar el usuario {user_id}"),
                       busy=f"Consultando GET /users/{user_id} ...")

    # ==========================================================================
    # PATCH del perfil
    # ==========================================================================
    def _changes(self):
        """Solo los campos que el usuario escribió (y que difieren de lo actual)."""
        user = self.app.user or {}
        values = {key: widget.get().strip() for key, widget in self.fields.items()}
        changes = {}

        for key in ("nombre", "apellido_paterno", "apellido_materno"):
            if values[key] and values[key] != (user.get(key) or ""):
                changes[key] = values[key]

        if values["email"]:
            email = validate_email(values["email"])
            if email != (user.get("email") or "").lower():
                changes["email"] = email

        if values["password"]:
            problem = validate_password(values["password"])
            if problem:
                raise ValidationError(f"La contraseña no cumple la política: {problem}")
            if not values["current_password"]:
                raise ValidationError("Escribe tu contraseña actual para poder cambiarla.")
            changes["password"] = values["password"]
            changes["current_password"] = values["current_password"]

        return changes

    def update_preview(self):
        try:
            changes = self._changes()
        except ValidationError as error:
            self.preview.configure(text=f"Revisa el formulario: {error}")
            return
        if not changes:
            self.preview.configure(text="PATCH /profile\n{}\n\n(sin cambios: no se enviará nada)")
            return
        shown = dict(changes)
        if "password" in shown:
            shown["password"] = "***"
            shown["current_password"] = "***"
        self.preview.configure(text=f"PATCH /profile\n{json.dumps(shown, indent=2, ensure_ascii=False)}")

    def save(self):
        try:
            changes = self._changes()
        except ValidationError as error:
            self.notify(str(error), kind="error")
            return
        if not changes:
            self.notify("No hay cambios que enviar.", kind="warning")
            return

        def done(result):
            user, fields = result
            self.app.set_user(user)
            self.prefill()
            self.fields["password"].delete(0, "end")
            self.fields["current_password"].delete(0, "end")
            self.notify(f"Perfil actualizado. El servidor confirmó los campos: {', '.join(fields)}.",
                        kind="success")
            self.load_session()

        self.run_async(lambda: self.services.auth.update_profile(changes), on_done=done,
                       on_error=lambda error: self.handle_error(error, "actualizar el perfil"),
                       busy="Enviando PATCH /profile ...")

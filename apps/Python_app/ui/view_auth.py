"""Inicio de sesión (vista 2.1) y registro de cuenta (vista 2.2).

Dos detalles del microservicio de login condicionan estas pantallas:

  - `/login` y `/register` exigen resolver un CAPTCHA (`captcha_id` +
    `captcha_answer`). Por eso ambas pantallas piden el desafío con
    `GET /captcha` y ofrecen un botón para pedir uno nuevo si expira.
  - El servicio no usa cookies: la sesión viaja en la cabecera
    `X-Session-Token`, que el cliente HTTP inyecta a partir de este punto.
"""

import tkinter as tk
from tkinter import ttk

from core.errors import ApiError
from core.validators import PASSWORD_RULES, ValidationError, validate_email, validate_registration

from .base_view import BaseView
from .theme import COLORS, FONT_BOLD, FONT_H2, FONT_SMALL, FONT_MONO


class CaptchaPanel(tk.Frame):
    """Desafío aritmético que el servicio exige antes de autenticar."""

    def __init__(self, master, view):
        super().__init__(master, bg=COLORS["surface_alt"], highlightthickness=1,
                         highlightbackground=COLORS["border"])
        self.view = view
        self.captcha_id = None

        inner = tk.Frame(self, bg=COLORS["surface_alt"])
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="Verificación CAPTCHA", bg=COLORS["surface_alt"],
                 fg=COLORS["text"], font=FONT_BOLD).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(inner, text="El microservicio rechaza /login y /register sin este desafío.",
                 bg=COLORS["surface_alt"], fg=COLORS["muted"], font=FONT_SMALL).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.question_label = tk.Label(inner, text="Pidiendo desafío...", bg=COLORS["surface_alt"],
                                       fg=COLORS["text"], font=FONT_BOLD)
        self.question_label.grid(row=2, column=0, sticky="w")

        self.answer_entry = ttk.Entry(inner, width=8)
        self.answer_entry.grid(row=2, column=1, sticky="w", padx=8)
        self.answer_entry.bind("<Return>", lambda _e: self.view.submit())

        ttk.Button(inner, text="Nuevo desafío", style="Ghost.TButton",
                   command=self.refresh).grid(row=2, column=2, sticky="w")

    def refresh(self):
        self.question_label.configure(text="Pidiendo desafío...")
        self.captcha_id = None
        self.answer_entry.delete(0, "end")

        def done(captcha):
            self.captcha_id = captcha.get("captcha_id")
            self.question_label.configure(text=captcha.get("question") or "(sin pregunta)")

        def failed(error):
            self.question_label.configure(text="No se pudo obtener el desafío")
            self.view.handle_error(error, "obtener el CAPTCHA")

        self.view.run_async(lambda: self.view.services.auth.fetch_captcha(),
                            on_done=done, on_error=failed)

    def values(self):
        """Devuelve (captcha_id, respuesta) validando que el usuario contestó."""
        answer = self.answer_entry.get().strip()
        if not self.captcha_id:
            raise ValidationError("No se ha obtenido el desafío CAPTCHA. Pulsa 'Nuevo desafío'.")
        if not answer:
            raise ValidationError("Escribe la respuesta del CAPTCHA.")
        try:
            return self.captcha_id, int(answer)
        except ValueError:
            raise ValidationError("La respuesta del CAPTCHA debe ser un número.")


class _AuthView(BaseView):
    """Base compartida por login y registro."""

    def build(self):
        wrapper = tk.Frame(self, bg=COLORS["bg"])
        wrapper.pack(expand=True, fill="both")

        card = tk.Frame(wrapper, bg=COLORS["surface"], highlightthickness=1,
                        highlightbackground=COLORS["border"])
        card.pack(pady=24, padx=40, fill="x", ipadx=8, ipady=8)
        card.columnconfigure(0, weight=1)

        self.body = tk.Frame(card, bg=COLORS["surface"])
        self.body.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(self.body, text=self.heading, bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H2).pack(anchor="w")
        tk.Label(self.body, text=self.subheading, bg=COLORS["surface"], fg=COLORS["muted"],
                 font=FONT_SMALL, justify="left", wraplength=620).pack(anchor="w", pady=(2, 4))

        self.targets = tk.Label(self.body, text="", bg=COLORS["surface"], fg=COLORS["muted"],
                                font=FONT_MONO, justify="left")
        self.targets.pack(anchor="w", pady=(0, 10))

        self.form = tk.Frame(self.body, bg=COLORS["surface"])
        self.form.pack(fill="x")
        self.build_form()

        self.captcha = CaptchaPanel(self.body, self)
        self.captcha.pack(fill="x", pady=(14, 0))

        self.actions = tk.Frame(self.body, bg=COLORS["surface"])
        self.actions.pack(fill="x", pady=(14, 0))
        self.build_actions()

    def on_show(self):
        self.targets.configure(
            text=f"Servidor de login: {self.services.config.base_url('login')}\n"
                 f"Servidor de libros: {self.services.config.base_url('books')}")
        self.captcha.refresh()

    # ------------------------------------------------------------------ ayudas
    def add_field(self, row, label, key, show=None, width=34, hint=None):
        tk.Label(self.form, text=label, bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_SMALL).grid(row=row * 2, column=0, sticky="w", pady=(8, 0))
        entry = ttk.Entry(self.form, width=width, show=show)
        entry.grid(row=row * 2 + 1, column=0, sticky="we", pady=(2, 0))
        if hint:
            tk.Label(self.form, text=hint, bg=COLORS["surface"], fg=COLORS["muted"],
                     font=FONT_SMALL, justify="left", wraplength=520).grid(
                row=row * 2 + 1, column=1, sticky="w", padx=(10, 0))
        self.form.columnconfigure(0, weight=1)
        self.fields[key] = entry
        return entry


class LoginView(_AuthView):
    """Vista 2.1: correo electrónico y contraseña."""

    heading = "Iniciar sesión"
    subheading = ("Autenticación contra POST /login. Si la sesión anterior sigue vigente, "
                  "la aplicación no vuelve a pedir credenciales.")

    def build_form(self):
        self.fields = {}
        self.add_field(0, "Correo electrónico", "email", width=40)
        self.add_field(1, "Contraseña", "password", show="*", width=40)

        # Prefill con lo recordado localmente: eso es el "local storage" del cliente.
        email, password = self.services.store.credentials()
        if email:
            self.fields["email"].insert(0, email)
        if password:
            self.fields["password"].insert(0, password)

        options = tk.Frame(self.form, bg=COLORS["surface"])
        options.grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.remember = tk.BooleanVar(value=bool(self.services.config.get("remember_credentials")))
        ttk.Checkbutton(options, text="Recordar credenciales en este equipo",
                        variable=self.remember, style="Surface.TCheckbutton").pack(side="left")

        self.fields["password"].bind("<Return>", lambda _e: self.submit())
        self.fields["email"].bind("<Return>", lambda _e: self.fields["password"].focus_set())

    def build_actions(self):
        self.submit_button = ttk.Button(self.actions, text="Entrar", style="Primary.TButton",
                                        command=self.submit)
        self.submit_button.pack(side="left")
        ttk.Button(self.actions, text="¿No tienes cuenta? Registrarse", style="SurfaceLink.TButton",
                   command=lambda: self.app.show("register")).pack(side="left", padx=10)
        ttk.Button(self.actions, text="Volver al catálogo", style="SurfaceLink.TButton",
                   command=lambda: self.app.show("catalog")).pack(side="right")

    def submit(self):
        email = self.fields["email"].get().strip()
        password = self.fields["password"].get()

        try:
            email = validate_email(email)
            if not password:
                raise ValidationError("Escribe tu contraseña.")
            captcha_id, captcha_answer = self.captcha.values()
        except ValidationError as error:
            self.notify(str(error), kind="error")
            return

        remember = bool(self.remember.get())

        def work():
            return self.services.auth.login(email, password, captcha_id, captcha_answer,
                                            remember=remember)

        def done(result):
            user, session = result
            self.app.set_user(user)
            self.app.set_status("Sesión iniciada.")
            # El aviso se muestra DESPUES de navegar: cambiar de pantalla limpia la
            # franja de avisos, asi que al reves el mensaje no llegaria a verse.
            self.app.show("dashboard")
            self.notify(
                f"Bienvenido, {user.get('nombre') or email}. Sesión iniciada y guardada "
                f"localmente (vence {session.get('expires_at', '')}).", kind="success")

        def failed(error):
            # Si el CAPTCHA se consumió o expiró, se pide otro automáticamente.
            if isinstance(error, ApiError) and error.code in (
                    "INVALID_CAPTCHA", "CAPTCHA_EXPIRED", "CAPTCHA_ALREADY_USED"):
                self.captcha.refresh()
            self.handle_error(error, "iniciar sesión")

        self.run_async(work, on_done=done, on_error=failed, busy="Autenticando...")


class RegisterView(_AuthView):
    """Vista 2.2: creación de cuenta."""

    heading = "Crear una cuenta"
    subheading = ("Alta contra POST /register. El servicio exige nombre, apellidos, correo y "
                  "contraseña, y responde 409 si el correo ya está registrado.")

    def build_form(self):
        self.fields = {}
        self.add_field(0, "Nombre(s)", "nombre")
        self.add_field(1, "Apellido paterno", "apellido_paterno")
        self.add_field(2, "Apellido materno", "apellido_materno")
        self.add_field(3, "Correo electrónico", "email")
        self.add_field(4, "Contraseña", "password", show="*",
                       hint="Política del servicio:\n" + "\n".join(PASSWORD_RULES))
        self.add_field(5, "Confirmar contraseña", "confirm", show="*")

    def build_actions(self):
        ttk.Button(self.actions, text="Crear cuenta", style="Primary.TButton",
                   command=self.submit).pack(side="left")
        ttk.Button(self.actions, text="Ya tengo cuenta: iniciar sesión",
                   style="SurfaceLink.TButton",
                   command=lambda: self.app.show("login")).pack(side="left", padx=10)

    def submit(self):
        values = {key: entry.get() for key, entry in self.fields.items()}

        try:
            clean = validate_registration(values["nombre"], values["apellido_paterno"],
                                         values["apellido_materno"], values["email"],
                                         values["password"], values["confirm"])
            captcha_id, captcha_answer = self.captcha.values()
        except ValidationError as error:
            self.notify(str(error), kind="error")
            return

        def work():
            return self.services.auth.register(
                clean["nombre"], clean["apellido_paterno"], clean["apellido_materno"],
                clean["email"], clean["password"], captcha_id, captcha_answer)

        def done(user):
            # Primero se navega y despues se avisa: `show` limpia la franja de avisos.
            view = self.app.show("login")
            self.app.banner.show(
                f"Cuenta creada para {user.get('email') or clean['email']}. "
                "Ya puedes iniciar sesión.", kind="success")
            # Se deja el correo precargado en el formulario de acceso.
            if view and hasattr(view, "fields"):
                view.fields["email"].delete(0, "end")
                view.fields["email"].insert(0, user.get("email") or clean["email"])
                view.fields["password"].focus_set()

        def failed(error):
            if isinstance(error, ApiError) and error.code in (
                    "INVALID_CAPTCHA", "CAPTCHA_EXPIRED", "CAPTCHA_ALREADY_USED"):
                self.captcha.refresh()
            self.handle_error(error, "registrar la cuenta")

        self.run_async(work, on_done=done, on_error=failed, busy="Creando la cuenta...")

"""Servicio de autenticacion: habla con el microservicio de login (puerto 5000).

Endpoints del servicio y uso que se les da en la aplicacion:

    GET   /health          -> semaforo de estado (lo usa health_service)
    GET   /captcha         -> desafio obligatorio antes de /login y /register
    POST  /register        -> alta de cuenta (201)
    POST  /login           -> inicio de sesion; devuelve access_token (JWT) + refresh_token
    POST  /refresh         -> canjea el refresh token por un par nuevo (rotacion)
    GET   /session         -> valida si la sesion sigue vigente (arranque)
    POST  /logout          -> revoca la sesion en el servidor
    POST  /session/extend  -> emite un access token nuevo
    PATCH /profile         -> modificacion parcial de los datos de la cuenta
    GET   /users/<id>      -> recurso REST de usuario

Notas del servicio que condicionan este cliente:
  - La credencial es un JWT que viaja en `Authorization: Bearer <access_token>`.
    (El header propio `X-Session-Token` del prompt anterior sigue siendo aceptado
    por el servidor, pero este cliente ya usa el esquema estandar.)
  - El access token vive poco (15 min). Cuando expira, el cliente lo renueva solo
    con el refresh token mediante POST /refresh: ver `refresh_session()`.
  - El formato predeterminado es XML; aqui se pide JSON con `?format=json`
    (y `http_client` sabe interpretar XML si el servicio respondiera asi).
  - `/login` y `/register` EXIGEN resolver un CAPTCHA (`captcha_id` +
    `captcha_answer`).
  - Politica de contrasena: minimo 8 caracteres con mayuscula, minuscula,
    digito y simbolo.
"""

from .errors import ApiError

# El servicio responde XML si no se le pide JSON explicitamente.
JSON = {"format": "json"}


class AuthService:
    """Operaciones de identidad y sesion contra el microservicio de login."""

    def __init__(self, http, config, store):
        self.http = http
        self.config = config
        self.store = store

    # ------------------------------------------------------------------ internos
    @property
    def base_url(self):
        return self.config.base_url("login")

    @staticmethod
    def _data(payload):
        """Extrae el bloque `data` del sobre de respuesta del servicio."""
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            if isinstance(data, list) and data:
                return data[0] if isinstance(data[0], dict) else {}
        return {}

    # ------------------------------------------------------------------ CAPTCHA
    def fetch_captcha(self):
        """Solicita un desafio aritmetico nuevo.

        Devuelve {'captcha_id': str, 'question': str, 'expires_in': int}.
        Es obligatorio: el servicio rechaza /login y /register sin el.
        """
        payload = self.http.get(self.base_url, "/captcha", params=JSON)
        data = self._data(payload)
        if not data.get("captcha_id"):
            raise ApiError("El servicio no devolvio un desafio CAPTCHA valido.",
                           kind="parse", url=self.base_url + "/captcha")
        return data

    # ------------------------------------------------------------------ registro
    def register(self, nombre, apellido_paterno, apellido_materno, email, password,
                 captcha_id, captcha_answer):
        """Crea la cuenta (POST /register). Devuelve el usuario creado."""
        body = {
            "nombre": nombre,
            "apellido_paterno": apellido_paterno,
            "apellido_materno": apellido_materno,
            "email": email,
            "password": password,
            "captcha_id": captcha_id,
            "captcha_answer": int(captcha_answer),
        }
        payload = self.http.post(self.base_url, "/register", body=body, params=JSON)
        return self._data(payload).get("user", {})

    # ------------------------------------------------------------------- sesion
    def login(self, email, password, captcha_id, captcha_answer, remember=True):
        """Inicia sesion y deja el token listo para el resto de las peticiones.

        Devuelve (usuario, sesion). Guarda en disco el token y, si se pidio,
        las credenciales para no volver a escribirlas.
        """
        body = {
            "email": email,
            "password": password,
            "captcha_id": captcha_id,
            "captcha_answer": int(captcha_answer),
        }
        payload = self.http.post(self.base_url, "/login", body=body, params=JSON)
        data = self._data(payload)
        session = data.get("session") or {}
        # El nuevo modelo devuelve `access_token` (JWT); se acepta tambien la
        # clave `token` que usaban los clientes anteriores.
        access_token = session.get("access_token") or session.get("token")
        if not access_token:
            raise ApiError("El servicio no devolvio el access token (JWT).",
                           kind="parse", url=self.base_url + "/login")
        refresh_token = session.get("refresh_token")

        self.http.set_tokens(access_token, refresh_token)
        self.store.set_session(access_token, session.get("expires_at"),
                               data.get("user") or {},
                               refresh_token=refresh_token,
                               refresh_expires_at=session.get("refresh_expires_at"))
        if remember:
            self.store.remember_credentials(email, password)
        else:
            self.store.forget_credentials()
        return data.get("user") or {}, session

    # ----------------------------------------------------------------- refresco
    def refresh_session(self):
        """Canjea el refresh token por un par nuevo (POST /refresh).

        Devuelve True si se pudieron renovar las credenciales. Se invoca de forma
        automatica desde el cliente HTTP cuando un servicio responde 401 (el
        access token expiro), de modo que la interfaz no tenga que enterarse.

        Se llama con `_retry=False` a proposito: si el propio /refresh falla con
        401 no debe intentar refrescarse a si mismo en un bucle.
        """
        refresh = self.store.refresh_token()
        if not refresh:
            return False

        try:
            payload = self.http.post(self.base_url, "/refresh",
                                     body={"refresh_token": refresh}, params=JSON,
                                     _retry=False, note="renovacion automatica del token")
        except ApiError:
            # El refresh ya no sirve (expiro, fue revocado o se detecto reuso):
            # se limpia la sesion y la interfaz pedira credenciales otra vez.
            self.http.clear_tokens()
            self.store.clear_session()
            return False

        session = self._data(payload).get("session") or {}
        access_token = session.get("access_token") or session.get("token")
        if not access_token:
            return False

        self.http.set_tokens(access_token, session.get("refresh_token"))
        self.store.set_session(access_token, session.get("expires_at"),
                               self.store.user(),
                               refresh_token=session.get("refresh_token"),
                               refresh_expires_at=session.get("refresh_expires_at"))
        return True

    def validate_session(self):
        """Comprueba contra el servidor si la sesion guardada sigue vigente.

        Se llama al arrancar la aplicacion. Devuelve (usuario, sesion) si el
        servidor confirma la sesion; si el servidor responde que expiro o fue
        revocada, limpia el token local y devuelve (None, None) para que la
        interfaz regrese de forma controlada a la pantalla de autenticacion.
        """
        token = self.store.token()
        if not token:
            return None, None

        self.http.set_session_token(token)
        try:
            payload = self.http.get(self.base_url, "/session", params=JSON)
        except ApiError as error:
            if error.is_session_problem:
                self.http.clear_session_token()
                self.store.clear_session()
                return None, None
            raise

        data = self._data(payload)
        user = data.get("user") or {}
        session = data.get("session") or {}
        self.store.set_session(token, session.get("expires_at"), user)
        return user, session

    def logout(self):
        """Cierra la sesion EN EL SERVIDOR (POST /logout) y olvida el token local.

        El token local se borra incluso si el servidor falla: la intencion del
        usuario es salir y no debe quedar una sesion utilizable en disco.
        """
        error = None
        try:
            # Se envia el refresh token para que el servidor lo revoque tambien:
            # asi el cierre de sesion es real y no solo local.
            body = {}
            if self.store.refresh_token():
                body["refresh_token"] = self.store.refresh_token()
            self.http.post(self.base_url, "/logout", body=body or None, params=JSON)
        except ApiError as exc:
            error = exc
        finally:
            self.http.clear_tokens()
            self.store.clear_session()
        return error

    def extend_session(self):
        """Emite un access token nuevo (POST /session/extend)."""
        payload = self.http.post(self.base_url, "/session/extend", params=JSON)
        data = self._data(payload)
        access_token = data.get("access_token") or data.get("token")
        if access_token:
            self.http.set_tokens(access_token)
            self.store.set_session(access_token,
                                   data.get("expires_at") or self.store.expires_at(),
                                   self.store.user())
        return data

    # ------------------------------------------------------------------ perfil
    def current_user(self):
        """Datos del usuario autenticado segun el servidor (GET /session)."""
        payload = self.http.get(self.base_url, "/session", params=JSON)
        return self._data(payload).get("user") or {}

    def get_user(self, user_id):
        """Recurso REST de usuario (GET /users/<id>)."""
        payload = self.http.get(self.base_url, f"/users/{int(user_id)}", params=JSON)
        return self._data(payload).get("user") or {}

    def update_profile(self, changes, current_password=None):
        """Modificacion PARCIAL del perfil (PATCH /profile).

        `changes` solo lleva los campos que el usuario edito: el servicio deja
        intactos los ausentes. Si se cambia la contrasena, el servicio exige
        `current_password` como confirmacion (se puede pasar como parametro o
        dentro de `changes`; lo que ya venga en `changes` tiene prioridad).
        """
        body = {key: value for key, value in changes.items() if value is not None}
        if body.get("password") and not body.get("current_password"):
            body["current_password"] = current_password or ""
        payload = self.http.patch(self.base_url, "/profile", body=body, params=JSON)
        data = self._data(payload)
        user = data.get("user") or {}
        self.store.set_user(user)
        # Si cambio la contrasena, lo recordado localmente debe seguir sirviendo.
        if body.get("password") and self.store.has_credentials():
            self.store.remember_credentials(user.get("email") or self.store.credentials()[0],
                                            body["password"])
        return user, data.get("updated_fields") or []

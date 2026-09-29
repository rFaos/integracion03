# Python_app — Cliente de escritorio de los microservicios de Login y Libros

Aplicación de escritorio en **Python + Tkinter** que consume, mediante HTTP y JSON,
los microservicios **Login** (`:5000`) y **Libros / SOAP** (`:5001`) del proyecto de
integración. La aplicación **nunca** accede a la base de datos: toda la información
entra y sale por los endpoints REST.

Esta es la implementación del cliente de escritorio pedido en la actividad: catálogo
público, registro, inicio de sesión, panel principal, semáforo de los dos servicios,
perfil del usuario, CRUD completo de libros (GET / POST / PUT / PATCH / DELETE),
configuración de servidores y persistencia local de la sesión.

---

## 0. Autorización por JWT (v1.1.0)

La aplicación envía **`Authorization: Bearer <access_token>` en cada operación**
contra los microservicios, y muestra en la **terminal** una bitácora de cada
petición con un encabezado de autenticación:

```
 [16:53:06] DELETE http://127.0.0.1:5001/books/TK-JWT-613504
   +-- AUTENTICACION ----------------------------------------------------------------
   | Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5...oEEwiEL0V7Ar2sqHmJeBfyIQ
   | JWT library-login  sub=37  rol=Usuario  sid=33  jti=f95ed1b4...
   | aud=library-api   expira en 14m 59s
   +-------------------------------------------------------------------------------
   <<< HTTP 200 en 97 ms   application/json
```

Ese encabezado se imprime **por cada petición**, con el token enmascarado y sus
claims (`sub`, `role`, `sid`, `jti`, `aud`, expiración). El payload del JWT se
decodifica **solo para mostrarlo**: el código lo dice explícitamente — mostrar no es
verificar.

### Refresco automático

Si una petición responde **401**, el cliente llama a `POST /refresh`, guarda el par
de tokens nuevo y **reintenta la petición original una sola vez** (con el encabezado
`X-Token-Refreshed` para que quede trazable). Si el refresco también falla, cierra la
sesión y avisa en la interfaz.

### Módulos relevantes

| Archivo | Qué hace |
|---|---|
| `core/trace.py` | La bitácora de terminal: encabezado de autenticación, claims, resumen |
| `core/http_client.py` | Envía el Bearer en todas las peticiones y dispara el refresco ante un 401 |
| `core/auth_service.py` | `login`, `refresh_session`, `logout`, `extend_session` |
| `core/session_store.py` | Persiste `access_token`, `refresh_token` y sus expiraciones |

### Nota sobre la latencia

La configuración usa `127.0.0.1` en vez de `localhost`. En Windows, `localhost`
resuelve primero a IPv6 (`::1`) mientras los servicios escuchan en IPv4, lo que
añade ~2 segundos **por petición** antes del fallback. Con `127.0.0.1` la respuesta
baja a ~100 ms. Está documentado en `core/config.py`.

### Prueba

`entrega_jwt/app_python_jwt_smoke.py` ejercita el cliente sin interfaz gráfica:
**16 aserciones, todas correctas**, incluyendo el refresco automático (fabrica un
access token expirado, hace un `PATCH` y comprueba que el cliente renueva y
reintenta con éxito).

---

## 1. Requisitos

| Concepto | Valor |
|---|---|
| **Python** | 3.10 o superior (probado en **3.13** y **3.14**) |
| **Biblioteca gráfica** | **Tkinter** (viene incluida en el instalador oficial de Windows) |
| **Sistema operativo** | Windows 11 (funciona igual en Linux/macOS) |
| **Dependencias obligatorias** | Ninguna (solo biblioteca estándar) |
| **Dependencia opcional** | `Pillow` — únicamente para mostrar las portadas del catálogo |

Si `Pillow` no está instalada, la aplicación **arranca y funciona igual**: en lugar de
la portada muestra un recuadro con la leyenda *"Sin imagen"*. Esto cubre también el
caso de libros que no tienen imágenes registradas.

---

## 2. Instalación

```bash
# 1. Situarse en la carpeta de la aplicación
cd apps/Python_app

# 2. (Recomendado) crear un entorno virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# 3. Instalar la dependencia opcional (Pillow)
pip install -r requirements.txt
```

> Si se omite el paso 3, la aplicación sigue funcionando: solo se pierden las portadas.

Verificar que Tkinter está disponible (si falta, reinstalar Python marcando
*tcl/tk and IDLE*):

```bash
python -c "import tkinter; print('Tkinter', tkinter.TkVersion)"
```

---

## 3. Configuración de los microservicios

La aplicación **no** lleva las direcciones escritas en el código: las lee de un archivo
de configuración que se edita desde la propia interfaz.

* **Pantalla:** `Configuración del servidor` (botón en la barra de navegación).
* **Archivo real:** `runtime/config.json` (se crea solo en el primer arranque).
* **Plantilla versionada:** `config.example.json` (solo documentación).

`runtime/` está excluido en `.gitignore`, igual que `session.json`, porque puede
contener credenciales recordadas. **No se sube ninguna credencial al repositorio.**

### Campos

| Campo | Significado | Valor predeterminado |
|---|---|---|
| `login_base_url` | Dirección base del microservicio de Login | `http://localhost:5000` |
| `books_base_url` | Dirección base del microservicio de Libros | `http://localhost:5001` |
| `remote_host` | IP o dominio de la instancia remota (GCloud) | — |
| `remote_login_port` / `remote_books_port` | Puertos en la instancia remota | `5000` / `5001` |
| `request_timeout` | Segundos de espera por petición | `8` |
| `health_interval_seconds` | Cada cuánto se comprueba `/health` | `30` |
| `session_warning_seconds` | Antelación con que se avisa que la sesión va a expirar | `300` |
| `page_size` | Libros por página del catálogo | `12` |
| `remember_credentials` | Recordar correo y contraseña en este equipo | `true` |

### Escenario 1 — Local

Los microservicios corriendo en la propia computadora:

```
http://localhost:5000     (Login)
http://localhost:5001     (Libros)
```

En la pantalla de configuración: botón **"Usar direcciones locales"**.

### Escenario 2 — Remoto (GCloud)

Los microservicios desplegados en la instancia:

1. Escribir la IP de la instancia en **Host remoto**.
2. Pulsar **"Usar direcciones remotas"** → construye
   `http://<host>:5000` y `http://<host>:5001` automáticamente.
3. **Probar conexión** y **Guardar**.

> **No se crean dos versiones del programa.** Es exactamente la misma aplicación;
> solo cambia la configuración, y el cambio persiste tras cerrar y volver a abrir.

---

## 4. Ejecución

```bash
cd apps/Python_app
python main.py
```

Antes de arrancar conviene tener los dos microservicios en marcha. Si alguno está
detenido, la aplicación **abre igual**: el semáforo correspondiente queda en rojo y
los avisos explican qué pasó.

---

## 5. Estructura del proyecto

```
apps/Python_app/
├── main.py                     # Punto de arranque único (valida Python/Tkinter y abre la ventana)
├── requirements.txt            # Dependencias (solo Pillow, opcional)
├── config.example.json         # Plantilla de configuración (documentación)
├── .gitignore                  # Excluye runtime/ (config y sesión) y __pycache__/
│
├── core/                       # Lógica: nada de Tkinter aquí
│   ├── config.py               # Lectura/validación/persistencia de las direcciones
│   ├── http_client.py          # Cliente HTTP (urllib): GET, POST, PUT, PATCH, DELETE
│   ├── errors.py               # Traducción de errores HTTP a mensajes comprensibles
│   ├── session_store.py        # "Almacén local": token, usuario y credenciales recordadas
│   ├── auth_service.py         # Registro, login, logout, sesión, perfil
│   ├── books_service.py        # Catálogo, búsqueda, detalle y CRUD de libros
│   ├── health_service.py       # Semáforo de 3 estados + comprobación periódica
│   ├── validators.py           # Validación previa en el cliente (correo, contraseña, ISBN…)
│   └── services.py             # Agrupa todo (ServiceHub) y lo entrega a la interfaz
│
├── ui/                         # Interfaz gráfica (Tkinter)
│   ├── app_window.py           # Ventana única: cabecera, semáforos, navegación, hilos
│   ├── theme.py                # Colores y tipografías
│   ├── widgets.py              # Semáforo, tarjetas, portadas, avisos y confirmaciones
│   ├── base_view.py            # Base común: respuestas seguras si la vista ya se cerró
│   ├── view_catalog.py         # Catálogo público y modo administración
│   ├── view_auth.py            # Login (2.1) y registro (2.2), con CAPTCHA
│   ├── view_dashboard.py       # Panel principal
│   ├── view_profile.py         # Sesión y perfil (PATCH /profile, extender sesión)
│   ├── view_book_detail.py     # Detalle, galería, conceptos, PATCH / PUT / DELETE
│   ├── view_book_form.py       # Alta (POST) y reemplazo completo (PUT)
│   └── view_settings.py        # Configuración del servidor
│
├── runtime/                    # (se crea al arrancar; NO se sube a git)
│   ├── config.json             # Direcciones activas
│   ├── session.json            # Token, usuario y credenciales recordadas
│   └── bitacora.log            # Registro de peticiones
│
└── evidencias/                 # Capturas de la aplicación en ejecución
```

**Dónde está cada responsabilidad** (lo que se puede pedir en la revisión):

| Responsabilidad | Archivo |
|---|---|
| GUI | `ui/*.py` |
| Configuración | `core/config.py` + `ui/view_settings.py` |
| Comunicación HTTP | `core/http_client.py` |
| Autenticación / sesión | `core/auth_service.py` + `core/session_store.py` |
| Libros | `core/books_service.py` |
| Comprobación de servicios | `core/health_service.py` |

---

## 6. Endpoints consumidos

### Microservicio de Login (`login_base_url`)

| Método | Endpoint | Uso en la aplicación |
|---|---|---|
| `GET` | `/health?format=json` | Semáforo (verde / amarillo / rojo) |
| `GET` | `/captcha` | Desafío obligatorio de `/login` y `/register` |
| `POST` | `/register` | Vista 2.2 — crear cuenta |
| `POST` | `/login` | Vista 2.1 — iniciar sesión (devuelve el token de sesión) |
| `POST` | `/logout` | Cerrar sesión y borrar el token local |
| `GET` | `/session` | Validar que la sesión guardada sigue vigente |
| `POST` | `/session/extend` | Extender la sesión próxima a expirar |
| `PATCH` | `/profile` | Modificar nombre, apellidos, correo o contraseña |

> **Detalle importante del servicio:** no usa cookies. La sesión viaja en la cabecera
> `X-Session-Token`, que el cliente inyecta en cada petición a partir del login.

### Microservicio de Libros (`books_base_url`)

| Método | Endpoint | Uso en la aplicación |
|---|---|---|
| `GET` | `/health` | Semáforo (verde / amarillo / rojo) |
| `GET` | `/books?format=json` | Catálogo |
| `GET` | `/books/search` | Búsqueda por texto, autor, género, año y rango de precio |
| `GET` | `/books/{isbn}` | Detalle (incluye conceptos e imágenes) |
| `GET` | `/catalogs` | Listas de apoyo para los formularios |
| `POST` | `/books` | Alta de libro (409 si el ISBN ya existe) |
| `PUT` | `/books/{isbn}` | **Reemplazo completo** del libro |
| `PATCH` | `/books/{isbn}` | **Modificación parcial** (solo los atributos enviados) |
| `DELETE` | `/books/{isbn}` | Baja de libro (404 si no existe) |

---

## 7. Persistencia de la sesión

1. Al iniciar sesión, el servicio devuelve un **token** y su fecha de expiración.
2. La aplicación guarda en `runtime/session.json` el token, los datos del usuario y
   (si el usuario marcó *"Recordar credenciales"*) el correo y la contraseña.
3. En el siguiente arranque **no se piden credenciales**: se llama a `GET /session`
   para comprobar contra el servidor si la sesión sigue siendo válida.
4. Si el servidor la rechaza, la aplicación borra el token local y **regresa de forma
   controlada** a la pantalla de inicio de sesión con un aviso claro.

> Guardar el token en disco no significa que la sesión siga viva: la validez siempre
> la confirma el servidor. Esa distinción es la que implementa `auth_service.validate_session()`.

---

## 8. Comportamiento ante fallos

La aplicación está diseñada para **no cerrarse nunca** por un problema de red:

* Toda petición se ejecuta en un **hilo aparte**; la ventana nunca se congela.
* Los errores se traducen a mensajes comprensibles (`core/errors.py`), **nunca** se
  muestra un *traceback* al usuario.
* Si un servicio deja de responder, su semáforo pasa a **rojo** y el resto de la
  aplicación sigue utilizable.
* Si el servidor rechaza la sesión, se vuelve al login de forma controlada.

Estados del semáforo:

| Estado | Significado |
|---|---|
| 🟢 Verde | El servicio responde y su base de datos está disponible |
| 🟡 Amarillo | El servicio responde, pero una dependencia está degradada (p. ej. PostgreSQL caído) |
| 🔴 Rojo | No hubo respuesta: servicio detenido, puerto incorrecto o dirección mal escrita |

---

## 9. Problemas conocidos

* **El CAPTCHA es obligatorio.** `/login` y `/register` rechazan la petición si no se
  envía `captcha_id` + `captcha_answer`. La aplicación lo pide automáticamente y ofrece
  un botón *"Nuevo desafío"* si expira.
* **El servicio de libros no filtra por ISBN en `/books/search`.** El criterio de
  búsqueda por ISBN se aplica como filtro local sobre el resultado de la búsqueda, y
  está documentado en `core/books_service.py`.
* **Las portadas necesitan `Pillow`.** Sin ella se muestra *"Sin imagen"*; no es un error.
* **`/health` puede tardar** hasta el *timeout* configurado cuando el servicio está
  caído. Durante ese tiempo la interfaz sigue respondiendo (la comprobación va en un hilo).

---

## 10. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| No aparece la ventana | Tkinter no está instalado | Reinstalar Python marcando *tcl/tk and IDLE* |
| `No se pudo conectar con http://localhost:5000` | El microservicio de Login está detenido | Levantarlo y pulsar *"Comprobar ahora"* |
| Semáforo en amarillo | El servicio responde pero no alcanza PostgreSQL | Revisar la base de datos del microservicio |
| `409 El correo ya está registrado` | La cuenta ya existe | Iniciar sesión en lugar de registrarse |
| `409 El ISBN ... ya existe` | Se intentó dar de alta un libro repetido | Usar otro ISBN o editar el existente |
| `404` al consultar un libro | El ISBN no existe | Revisar el ISBN en el catálogo |
| La sesión se pierde al reabrir | El servidor la expiró o se cerró sesión | Volver a iniciar sesión |
| Error al mostrar portadas | `Pillow` no instalada | `pip install -r requirements.txt` (opcional) |
| Las direcciones no cambian | No se pulsó **Guardar** en la configuración | Guardar y comprobar con **Probar conexión** |

---

## 11. Notas de seguridad

* **No se sube ninguna credencial al repositorio.** `runtime/` está en `.gitignore`.
* Las credenciales recordadas se guardan **ofuscadas en base64**, no en texto plano,
  y solo si el usuario lo pide expresamente.
* La aplicación no se conecta a PostgreSQL ni a ninguna base de datos: solo habla HTTP
  con los microservicios.

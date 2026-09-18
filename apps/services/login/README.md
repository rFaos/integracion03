# Microservicio de Autenticación y Gestión de Usuarios
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Institución:** Universidad de Monterrey (UDEM)  
**Puerto:** 5000

Microservicio independiente en **Python / Flask / Psycopg 3 / PostgreSQL** que reutiliza la base de datos `library` del proyecto y expone sus respuestas en **XML (predeterminado)** y **JSON**.

---

## 1. Archivos

| Archivo | Descripción |
| :--- | :--- |
| `app.py` | Microservicio Flask: endpoints, serialización dual, sesiones, CAPTCHA y Swagger. |
| `requirements.txt` | Dependencias de Python. |
| `.env.example` | Plantilla de configuración (sin secretos reales). |
| `sql/01_migration_auth.sql` | Migración de `users` y creación de `user_sessions`. |
| `sql/02_fix_seed_passwords.sql` | Corrige los hashes bcrypt inválidos de los usuarios sembrados. |
| `tests/smoke_test.py` | 39 aserciones del flujo completo sin necesidad de PostgreSQL. |
| `tests/e2e_test.py` | Prueba end-to-end contra una instancia desplegada. |
| `docs/EVIDENCIA.md` | Guía de Swagger, resultados de validación y reflexión. |
| `docs/evidencia_e2e.txt` | Salida cruda de la última validación end-to-end. |
| `docs/login-microservice.postman_collection.json` | Colección de Postman con aserciones y encadenamiento. |

---

## 2. Instalación y ejecución

```bash
cd apps/services/login
python3 -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 1) Aplicar la migración a la base de datos library
psql -U library_user -d library -f sql/01_migration_auth.sql

# 1b) Solo si la base ya tenía cargados los datos semilla: corrige los
#     hashes bcrypt inválidos de admin y usuario1..usuario10.
psql -U library_user -d library -f sql/02_fix_seed_passwords.sql

# 2) Configurar credenciales
cp .env.example .env               # y edita DB_PASSWORD / SECRET_KEY

# 3) Arrancar
python app.py
```

- **Servicio:** http://localhost:5000
- **Swagger UI:** http://localhost:5000/docs
- **Health check:** http://localhost:5000/health

> `GET /health` incluye un campo `schema` que vale `ready` o `migration_pending`. Si aparece `migration_pending`, falta aplicar `sql/01_migration_auth.sql`: sin esa migración `/login` y `/register` responden **500** porque las columnas de identidad y la tabla `user_sessions` todavía no existen.

---

## 3. Endpoints

| Método | Endpoint | Función | Sesión | CAPTCHA |
| :--- | :--- | :--- | :---: | :---: |
| `POST` | `/register` | Registrar un nuevo usuario | No | Sí |
| `POST` | `/login` | Autenticar e iniciar sesión | No | Sí |
| `POST` | `/logout` | Cerrar la sesión | Sí | No |
| `GET` | `/session` | Consultar si existe sesión autenticada | Sí | No |
| `GET` | `/health` | Estado del servicio y de PostgreSQL | No | No |
| `GET` | `/captcha` | Obtener el desafío CAPTCHA (sin GUI) | No | No |
| `GET` | `/` | Raíz del API (punto de entrada HATEOAS) | No | No |
| `GET` | `/users/<id>` | Datos públicos de un usuario | Sí | No |
| `GET` | `/docs` | Swagger UI | No | No |

### Formato de respuesta

| Petición | Respuesta |
| :--- | :--- |
| `POST /login` | **XML** (predeterminado) |
| `POST /login?format=xml` | **XML** |
| `POST /login?format=json` | **JSON** |
| `POST /login` con `Accept: application/json` | **JSON** |

> `Accept: */*` (lo que envían Postman y curl por defecto) **no** cambia el formato: se responde XML.

---

## 4. Sesión sin cookies

El servicio **no usa cookies**. La sesión vive del lado del servidor y el cliente la identifica con un token:

```
POST /login            -> devuelve data.session.token
GET  /session          -> header: X-Session-Token: <token>
POST /logout           -> header: X-Session-Token: <token>
```

- Duración: **30 minutos**.
- En `user_sessions` se guarda únicamente el **SHA-256 del token**, nunca el token en claro.
- `POST /logout` marca `revoked_at`, por lo que la revocación es inmediata.
- También se acepta `Authorization: Bearer <token>`.

---

## 5. CAPTCHA sin interfaz gráfica

`GET /captcha` devuelve una pregunta aritmética y un `captcha_id` que **contiene la respuesta firmada con HMAC**, no almacenada:

```json
{ "data": { "captcha_id": "eyJhIjo3...  .firma", "question": "¿Cuánto es 7 + 4?", "expires_in": 300 } }
```

- La firma HMAC impide que el cliente fabrique su propio desafío.
- Vigencia de 5 minutos y **un solo uso** (evita replay).
- Se envía de vuelta en `captcha_id` + `captcha_answer`.

> El CAPTCHA es una capa de **fricción**, no una defensa definitiva: al ser aritmético, un script puede resolverlo. La protección real contra fuerza bruta es el *rate limiting* y el bloqueo temporal por intentos fallidos, que están implementados.

---

## 6. Verificación con Postman

1. Importa `docs/login-microservice.postman_collection.json`.
2. Ejecuta la colección con el **Collection Runner**, de arriba hacia abajo.

Las variables (`captcha_id`, `captcha_answer`, `session_token`, `user_id`) se llenan solas: la petición de CAPTCHA lo resuelve y lo guarda, y el login guarda el token.

**Dos detalles importantes:**

- El CAPTCHA es de un solo uso, por eso la colección incluye varias peticiones `Captcha (nuevo desafío)` antes de cada registro o login.
- Como el formato predeterminado es XML, las peticiones sin `?format=json` se parsean con `xml2Json(pm.response.text())`; el resto usa `pm.response.json()`.

Para el registro se usa el correo único por corrida `usuario.<timestamp>@library.local` con la contraseña `S3gura!2026`. Para el login en XML se usa el usuario sembrado `usuario1@library.local` / `666`.

---

## 7. Prueba automatizada sin base de datos

```bash
./venv/Scripts/python.exe tests/smoke_test.py     # Windows
python tests/smoke_test.py                        # Linux/macOS
```

Reemplaza la capa de datos por un doble en memoria y valida 39 aserciones del flujo completo: formato dual, hipermedia, registro, unicidad del correo, política de contraseña, CAPTCHA (firma, un solo uso, respuesta incorrecta), login, sesión, revocación, anti-enumeración y expiración de los 30 minutos.

---

## 8. Nivel 3 de Richardson (HATEOAS)

Toda respuesta incluye un bloque de hipermedia:

```json
"_links": {
  "self":   { "href": "/session",  "method": "GET"  },
  "logout": { "href": "/logout",   "method": "POST" }
}
```

- `GET /` publica los 7 recursos disponibles (punto de entrada único).
- Los errores también devuelven enlaces: un `401` incluye `login` y `captcha`.
- Códigos de estado correctos (`201`, `400`, `401`, `403`, `409`, `429`, `503`) y encabezado `Location` al crear.

> **Nota:** `/login` y `/logout` son acciones (no recursos) porque así los fija el enunciado. Es la única desviación del REST puro; el Nivel 3 se sostiene sobre las representaciones.

---

## 9. Seguridad implementada

| Tema | Medida |
| :--- | :--- |
| Contraseñas | Hash **bcrypt** (costo 12). Nunca en texto plano. |
| `password_hash` | Permanece en `users`; no hay tabla de contraseñas ni doble almacenamiento. |
| Token de sesión | 256 bits (`secrets.token_urlsafe`), en BD solo su SHA-256. |
| Email | Validado por expresión regular y único con índice `LOWER(email)`. |
| Anti-enumeración | `/login` devuelve siempre `INVALID_CREDENTIALS`; se iguala el tiempo de respuesta. |
| Fuerza bruta | Rate limiting por IP + bloqueo temporal tras 5 intentos fallidos. |
| SQL | 100 % consultas parametrizadas. |
| CSRF | No aplica: sin cookies ni formularios HTML. |
| Auditoría | Se reutiliza la tabla existente `clientes_servidos`. |

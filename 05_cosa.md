# PROMPT 05: Microservicio de Autenticación y Gestión de Usuarios
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Institución:** Universidad de Monterrey (UDEM)  
**Semestre:** Primavera 2026  

**Esquema de referencia:** `data/db_schema.sql`, `data/db_design.md`, `data/library_data.sql`

---

## 1. Objetivo del Prompt
Desarrollar un **microservicio independiente de autenticación y gestión básica de usuarios** para la plataforma de librería en línea existente, con **Python, Flask, Psycopg 3 y PostgreSQL**, reutilizando la base de datos actual (`library`) y exponiendo cada recurso tanto en **XML** como en **JSON**.

El propósito es practicar integración entre aplicaciones, diseño de API, persistencia en PostgreSQL, normalización, autenticación, sesiones, protección de contraseñas y representación de un mismo recurso en diferentes formatos.

---

## 2. Restricciones Técnicas

1. **Ubicación:** `apps/services/login/`.
2. **Framework:** Flask plano (**sin Blueprints**), consistente con `apps/services/soap/app.py`.
3. **Driver PostgreSQL:** exclusivamente **`psycopg` (v3)** con `psycopg.rows.dict_row`.
4. **Base de datos:** la existente **`library`**; solo se modifican las tablas necesarias.
5. **Formato:** **XML predeterminado**; JSON con `?format=json`. Todos los endpoints aceptan `?format=xml` y `?format=json`.
6. **Sesión:** del lado de Flask, **30 minutos** y **sin cookies** → token opaco en el encabezado `X-Session-Token`.
7. **Contraseñas:** nunca en texto plano; solo **hash bcrypt** en `users.password_hash` (sin tabla de contraseñas ni doble almacenamiento).
8. **CAPTCHA:** obligatorio en `/login` y `/register`, resoluble **sin interfaz gráfica**.
9. **CORS:** con `flask-cors`.
10. **Swagger:** con `flasgger` en `/docs`, documentando XML y JSON.
11. **Puerto:** **5000**.
12. **Credenciales:** vía `python-dotenv` desde `.env` (`DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`, `SECRET_KEY`).
13. **REST:** el diseño debe situarse en el **Nivel 3 del Modelo de Madurez de Richardson (HATEOAS)**.
14. **Negociación de contenido:** se acepta `?format=` **y** el encabezado `Accept`. Un `Accept: */*` (el valor por defecto de Postman) **no** cambia el formato: se responde XML.

---

## 3. Endpoints Obligatorios

| Método | Endpoint | Función | Sesión | CAPTCHA |
| :--- | :--- | :--- | :---: | :---: |
| `POST` | `/register` | Registrar un nuevo usuario | No | Sí |
| `POST` | `/login` | Autenticar al usuario e iniciar sesión | No | Sí |
| `POST` | `/logout` | Cerrar la sesión | Sí | No |
| `GET` | `/session` | Consultar si existe una sesión autenticada | Sí | No |
| `GET` | `/health` | Verificar el estado del microservicio y PostgreSQL | No | No |
| `GET` | `/captcha` | Obtener el desafío CAPTCHA (sin GUI) | No | No |
| `GET` | `/` | Raíz del API: punto de entrada HATEOAS | No | No |
| `GET` | `/docs` | Documentación Swagger UI | No | No |

`POST /login` y `POST /login?format=xml` responden **XML**; `POST /login?format=json` responde **JSON**.

---

## 4. Nivel 3 de Richardson (HATEOAS)

| Nivel | Nombre | Característica |
| :--- | :--- | :--- |
| 0 | The Swamp of POX | Un URI, un verbo; el protocolo viaja en el *payload*. |
| 1 | Resources | Muchos URIs, un solo verbo. |
| 2 | HTTP Verbs | Verbos correctos + códigos de estado. |
| 3 | Hypermedia Controls | **HATEOAS**: la respuesta incluye enlaces de las siguientes acciones posibles. |

**Diagnóstico:** los endpoints exigidos son **orientados a acciones** (`/register`, `/login`, `/logout` llevan el verbo en el URI), así que el enunciado por sí solo aterriza en **Nivel 1**. Se alcanza el Nivel 3 conservando esos endpoints **exactamente** y agregando la capa de hipermedia:

1. Bloque `_links` (JSON) / `<links>` (XML) con `rel`, `href` y `method` en **toda** respuesta.
2. **`GET /`** como punto de entrada único que publica las rutas disponibles.
3. Enlaces **también en los errores**: un `401` devuelve enlace a `/login` y `/captcha`.
4. Códigos de estado correctos (`201`, `200`, `401`, `403`, `409`, `429`, `503`) y encabezado `Location` al crear.
5. Negociación de contenido real vía `Accept`.

**XML:**
```xml
<response>
  <status>success</status>
  <message>Autenticación exitosa</message>
  <data>
    <user><id>42</id><nombre>Fabián</nombre><email>azaedorta@hotmail.com</email><role>Usuario</role></user>
    <session><token>3xK9...q0</token><expires_in>1800</expires_in></session>
  </data>
  <links>
    <link rel="self"    href="/session"  method="GET"/>
    <link rel="logout"  href="/logout"   method="POST"/>
    <link rel="user"    href="/users/42" method="GET"/>
    <link rel="captcha" href="/captcha"  method="GET"/>
  </links>
</response>
```

**JSON:**
```json
{
  "status": "success",
  "message": "Autenticación exitosa",
  "data": { "user": { "id": 42, "email": "azaedorta@hotmail.com", "role": "Usuario" },
            "session": { "token": "3xK9...q0", "expires_in": 1800 } },
  "_links": {
    "self":    { "href": "/session",  "method": "GET"  },
    "logout":  { "href": "/logout",   "method": "POST" },
    "user":    { "href": "/users/42", "method": "GET"  },
    "captcha": { "href": "/captcha",  "method": "GET"  }
  }
}
```

**Error con hipermedia (401):** `{"error":{"code":"SESSION_EXPIRED"},"_links":{"login":{"href":"/login","method":"POST"}}}`

> **Nota crítica:** `/login` y `/logout` son **acciones, no recursos**, y el enunciado los fija con ese nombre. Es la única desviación del REST puro y debe declararse en la reflexión; el Nivel 3 se sostiene sobre las **representaciones**, no sobre esas dos rutas.

---

## 5. Reglas de Negocio y Seguridad

1. **Registro:** `nombre`, `apellido_paterno`, `apellido_materno`, `email`, `password`.
2. **Email:** validado y **único** (índice único sobre `LOWER(email)`).
3. **Contraseña:** mínimo 8 caracteres con mayúscula, número y símbolo; se guarda solo el **hash bcrypt**.
4. **Autenticación:** verifica credenciales contra PostgreSQL y crea la sesión de Flask que identifica al usuario en solicitudes posteriores.
5. **Sesión:** 30 min; en `user_sessions` se guarda solo el **SHA-256 del token**, nunca el token en claro. `/logout` la revoca de inmediato.
6. **Anti-enumeración:** error de login genérico (`INVALID_CREDENTIALS`); nunca se distingue correo inexistente de contraseña incorrecta.
7. **Fuerza bruta:** *rate limiting* por IP y email + bloqueo temporal (`locked_until`).
8. **CAPTCHA sin GUI:** desafío aritmético firmado con **HMAC** (*stateless*), expira en 5 min y es de un solo uso; sin navegador ni servicios externos.
9. **SQL:** 100 % consultas parametrizadas (`%s`).
10. **CORS:** al no usar cookies, `origins: "*"` es válido. **CSRF:** no aplica.
11. **Auditoría:** se reutiliza la tabla existente `clientes_servidos`.

---

## 6. Modificación de la Base de Datos

```sql
-- Identidad del usuario
ALTER TABLE users ADD COLUMN IF NOT EXISTS nombre            VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS apellido_paterno  VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS apellido_materno  VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS email             VARCHAR(150);
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active         BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login        TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts   INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until      TIMESTAMPTZ;

-- Los nuevos usuarios se identifican por email, no por username
ALTER TABLE users ALTER COLUMN username DROP NOT NULL;
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'Usuario';

-- Backfill de los 11 usuarios sembrados en library_data.sql (admin + usuario1..10)
UPDATE users SET email = username || '@library.local' WHERE email IS NULL;

-- Unicidad de email insensible a mayúsculas
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users (LOWER(email));

-- Almacén server-side de sesiones (no hay cookies)
CREATE TABLE IF NOT EXISTS user_sessions (
    id           BIGSERIAL PRIMARY KEY,
    token_hash   CHAR(64)    NOT NULL UNIQUE,
    user_id      INT         NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at   TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at   TIMESTAMPTZ,
    ip_origen    VARCHAR(45),
    user_agent   VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS idx_sessions_user    ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);
```

> `password_hash` permanece en `users`: no se crea tabla de contraseñas ni se almacena dos veces.

---

## 7. Entregables Esperados

En `apps/services/login/`: `app.py`, `requirements.txt`, `.env.example`, `README.md`, `sql/01_migration_auth.sql`, `docs/EVIDENCIA.md`.

Además: **colección de Postman** (`login-microservice.postman_collection.json` + environment), monorepo compactado en `.tar.gz` o `.zip`, screenshots de resultados y una breve reflexión de por qué se hace así.

---

## 8. Validación

| # | Caso | Esperado |
| :--- | :--- | :--- |
| T-01 | `GET /health` / `?format=json` | `200` con `application/xml` y `application/json` |
| T-02 | `GET /captcha` | `captcha_id` + `question` |
| T-03 | `POST /register` válido | `201` + `Location` + `_links` |
| T-04 | `POST /register` email repetido / inválido | `409` / `400` |
| T-05 | `POST /login` correcto XML y JSON | `200` + token + `_links` |
| T-06 | `POST /login` contraseña incorrecta | `401` + enlace a `/login` |
| T-07 | `POST /login` CAPTCHA erróneo | `400 INVALID_CAPTCHA` |
| T-08 | `GET /session` con / sin token | `200` / `401` |
| T-09 | `POST /logout` y reuso del token | `200` y luego `401` |
| T-10 | `GET /` y `Accept: application/json` | Raíz con `_links` / negociación |

**Evidencia mínima:** Swagger UI, `/health` en ambos formatos con su `Content-Type`, registro exitoso y duplicado, login en ambos formatos, login fallido, sesión activa e inválida, logout, `GET /` con hipermedia, y la tabla `users` mostrando el hash bcrypt (no texto plano).

---

## 9. Verificación con Postman

Postman es la herramienta de verificación y entrega del parcial: se revisa **qué envía** cada petición y **qué recibe** como respuesta.

### 9.1 Variables de la colección

| Variable | Valor inicial | Se llena con |
| :--- | :--- | :--- |
| `base_url` | `http://localhost:5000` | Manual |
| `captcha_id` | *(vacío)* | Script de test de `/captcha` |
| `captcha_answer` | *(vacío)* | Script de test de `/captcha` |
| `session_token` | *(vacío)* | Script de test de `/login` |
| `user_email` | `usuario.<timestamp>@library.local` | Pre-request de `/register` |
| `user_password` | `S3gura!2026` | Manual |
| `seed_email` / `seed_password` | `usuario1@library.local` / `666` | Manual |

La colección entregada es `apps/services/login/docs/login-microservice.postman_collection.json`.

### 9.2 El detalle crítico: XML es el predeterminado

Postman envía `Accept: */*` por defecto. Como el **XML es el predeterminado**, si no se agrega `?format=json` la respuesta llega en XML y `pm.response.json()` **falla**. Dos salidas:

1. Agregar `?format=json` a la URL → se trabaja con `pm.response.json()`.
2. Consumir XML convirtiéndolo con `xml2Json`:
```javascript
const xml = xml2Json(pm.response.text());
pm.test("status success", () => pm.expect(xml.response.status).to.eql("success"));
```

### 9.3 Script de test en `GET /captcha` (alimenta el login)

```javascript
pm.test("200 OK", () => pm.response.to.have.status(200));

const data = pm.response.json().data;
pm.test("Devuelve desafío", () => pm.expect(data).to.have.property("captcha_id"));
pm.test("La pregunta es aritmética", () => pm.expect(data.question).to.match(/\d+\s*[+\-]\s*\d+/));

// Se resuelve y se guarda para los siguientes requests
pm.collectionVariables.set("captcha_id", data.captcha_id);
pm.collectionVariables.set("captcha_answer", String(eval(data.question.match(/\d+\s*[+\-]\s*\d+/)[0])));
```

> El CAPTCHA es de **un solo uso**, así que la colección repite esta petición antes de cada registro o login.
> Se resuelve en un **request previo** y no en un `Pre-request Script`, porque `pm.sendRequest` es asíncrono y el request principal se dispararía antes de tener la respuesta.

### 9.4 Script de test en `POST /login` (extrae el token)

```javascript
pm.test("200 OK", () => pm.response.to.have.status(200));
pm.test("Responde JSON", () => pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json"));

const body = pm.response.json();
pm.test("Devuelve token de sesión", () => pm.expect(body.data.session.token).to.be.a("string"));

// Encadenar: el token alimenta /session, /users y /logout
pm.collectionVariables.set("session_token", body.data.session.token);

// Verificar HATEOAS (Nivel 3)
pm.test("Incluye _links (HATEOAS)", () => {
    pm.expect(body._links).to.have.property("logout");
    pm.expect(body._links.logout).to.have.property("href");
});
```

### 9.5 Qué envía y qué recibe cada request

| Request | Envía | Recibe |
| :--- | :--- | :--- |
| `GET /health?format=json` | URL | `200` · `application/json` |
| `GET /health` | URL sin `format` | `200` · `application/xml` |
| `GET /captcha?format=json` | URL | `200` · `captcha_id` + `question` |
| `POST /register?format=json` | JSON: 5 campos + `captcha_id` + `captcha_answer` | `201` · `Location` · `_links` |
| `POST /login?format=json` | JSON: `email`, `password`, `captcha_id`, `captcha_answer` | `200` · `token` · `_links` |
| `POST /login` | Mismo cuerpo | `200` · **XML** con `<session><token>` |
| `GET /session?format=json` | Header `X-Session-Token` | `200` · `authenticated: true` |
| `GET /session?format=json` | Header con token revocado | `401` · `SESSION_INVALID` |
| `POST /logout?format=json` | Header `X-Session-Token` | `200` · `LOGOUT_SUCCESS` |
| `GET /session` sin header | URL | `401` · `SESSION_REQUIRED` |

### 9.6 Orden de ejecución (Collection Runner)

`/` → `/health` (XML) → `/health?format=json` → `/captcha` → `/register` → `/captcha` → `/register` (409) → `/register` (400) → `/captcha` → `/login` → `/captcha` → `/login` (XML) → `/captcha` → `/login` (401) → `/session` → `/session` (401) → `/users/<id>` → `/logout` → `/session` (401).

El encadenamiento funciona porque `/captcha` guarda `captcha_id` + `captcha_answer` y `/login` guarda `session_token` y `user_id`. La colección incluye 19 peticiones con **39 aserciones** en total.

**Evidencia:** exportar la colección y el environment, y adjuntar screenshots de cada request mostrando el **Body** y los **Headers** tanto de envío como de respuesta.

---

## 10. Puntos a Confirmar

1. **Sesión:** ¿se acepta el token en `X-Session-Token` como "sesión de Flask sin cookies", o se exige la cookie firmada de `flask.session`?
2. **CAPTCHA:** ¿en `/register` y `/login`, o solo en `/login`?
3. **Contraseña:** política no especificada (propuesta: 8 caracteres, mayúscula, número y símbolo).
4. **RMM:** confirmar que el Nivel 3 se evalúa sobre las **representaciones con hipermedia** y no sobre el nombre de los endpoints de acción.
5. **Puerto 5000:** el servicio SOAP usa el **5001**; confirmar que no coinciden.
6. **Monolito:** `apps/web-monolito01` ya tiene login propio con bcrypt; definir si comparten `users` o son ejercicios independientes.

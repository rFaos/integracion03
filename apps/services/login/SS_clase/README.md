# Capturas de la clase — Evidencia del microservicio

Servicio desplegado en `http://34.51.29.27:5000` (instancia GCloud, PostgreSQL 16.14).

| Archivo | Qué muestra |
| :--- | :--- |
| `01-swagger-endpoints.png` | Swagger UI en `/docs` con los **8 endpoints** agrupados por etiqueta: **Auth** (`/register`, `/login`, `/logout`), **Session** (`/session`), **Users** (`/users/{user_id}`) y **System** (`/`, `/health`, `/captcha`). |
| `02-captcha-json.png` | `GET /captcha?format=json` ejecutado correctamente: **HTTP 200**, `captcha_id`, `question` (*"¿Cuánto es 7 + 5?"*) y `expires_in: 300`. Se ve el bloque `_links` de HATEOAS y los encabezados de respuesta (`content-type: application/json`). |
| `03-register-params.png` | Formulario de `POST /register` con el cuerpo JSON completo: `nombre`, `apellido_paterno`, `apellido_materno`, `email`, `password`, `captcha_id` y `captcha_answer: 12` (la respuesta correcta al desafío anterior). |

## Cómo se leen estas capturas en Swagger

Swagger UI **no muestra nada** en la sección *Responses* hasta que se pulsa el botón azul **Execute**. Una vez pulsado, la respuesta aparece debajo, en *Server response*:

- **Code** → el código HTTP (`200`, `201`, `400`, `401`…).
- **Response body** → el cuerpo en XML o JSON según el parámetro `format`.
- **Response headers** → los encabezados, incluido `Content-Type`.

Si el cuerpo sale vacío, casi siempre es una de estas tres:

1. **No se pulsó Execute** — el formulario solo se rellenó.
2. **El CAPTCHA caducó** (vida de 5 minutos) o **ya se usó** (es de un solo uso) → devuelve `400` con `INVALID_CAPTCHA` o `CAPTCHA_ALREADY_USED`. Solución: pedir uno nuevo en `GET /captcha` justo antes.
3. **El servicio no responde** → Swagger muestra *"Failed to fetch"*. Verificar con `GET /health`.

## El `Response content type` del desplegable

Ese desplegable es solo una preferencia de visualización. **El formato real lo decide el parámetro `format` de la URL**: sin `format` la respuesta es **XML** (predeterminado del enunciado), y con `?format=json` es JSON. Por eso la captura `02` muestra el desplegable en `application/xml` pero el cuerpo llega en JSON: la URL pedía `?format=json`.

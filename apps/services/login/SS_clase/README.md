# Capturas de la clase — Evidencia del microservicio

Servicio desplegado en `http://34.51.29.27:5000` (instancia GCloud, PostgreSQL 16.14).

| Archivo | Qué muestra |
| :--- | :--- |
| `01-swagger-endpoints.png` | Swagger UI en `/docs` con los **8 endpoints** agrupados por etiqueta: **Auth** (`/register`, `/login`, `/logout`), **Session** (`/session`), **Users** (`/users/{user_id}`) y **System** (`/`, `/health`, `/captcha`). |
| `02-captcha-json.png` | `GET /captcha?format=json` ejecutado correctamente: **HTTP 200**, `captcha_id`, `question` (*"¿Cuánto es 7 + 5?"*) y `expires_in: 300`. Se ve el bloque `_links` de HATEOAS y los encabezados de respuesta (`content-type: application/json`). |
| `03-register-params.png` | Formulario de `POST /register` con el cuerpo JSON completo: `nombre`, `apellido_paterno`, `apellido_materno`, `email`, `password`, `captcha_id` y `captcha_answer: 12` (la respuesta correcta al desafío anterior). |
| `04-despliegue-instancia-puerto-5000.png` | **Evidencia del despliegue.** Terminal de la instancia `maquina-03` con los comandos ejecutados (`cd /opt/udem/integracion03/apps/services/login`, `source venv/bin/activate`, `flask run --host=0.0.0.0 --port=5000`) y el arranque confirmado: *"Running on all addresses (0.0.0.0)"*, `http://127.0.0.1:5000` y `http://10.224.0.2:5000`. Detrás, el log de peticiones `200` a `/apispec.json`, `/flasgger_static/...` y `/captcha?format=json`, más la documentación Swagger de `POST /login` con sus códigos `200`, `401`, `403` y `429`. |
| `05-captcha-200-nuevo-desafio.png` | `GET /captcha?format=json` con **HTTP 200** y un desafío nuevo (*"¿Cuánto es 6 - 4?"*), su `captcha_id` firmado, `expires_in: 300`, el bloque `_links` de HATEOAS y los encabezados de respuesta (`content-type: application/json`). |

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

---

## Nota sobre los errores `400` que aparecen en el log

En la terminal se ven líneas como esta:

```
code 400, message Bad request version ('\x02h2\x08http/1.1...')
"\x16\x03\x01\x06¨\x01\x00\x06¤\x03\x03..."
```

**No son un fallo del microservicio.** Los bytes `\x16\x03\x01` son el inicio de un registro **TLS** y dentro viaja un *ClientHello* que ofrece ALPN `h2` y `http/1.1` — es decir, un navegador intentando hablar **HTTPS contra un puerto HTTP**. Werkzeug intenta leerlo como petición HTTP, no puede, y responde `400`.

La causa es el navegador, no un tercero: la propia terminal muestra `Last login: ... from 104.28.199.135`, que es la misma IP de origen de esas peticiones. Chrome con la opción **"Always use secure connections"** (HTTPS-First) intenta primero HTTPS, falla el handshake y reintenta por HTTP; los intentos fallidos quedan registrados como `400`.

Es inofensivo y no afecta a ningún endpoint. Si molesta en los logs, basta con desactivar esa opción para ese host o poner el servicio detrás de un proxy inverso con TLS.

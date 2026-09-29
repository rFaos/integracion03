# Módulo de Servicios SOAP, XML/XSLT y Microservicio RESTful (Flask)
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Institución:** Universidad de Monterrey (UDEM)  

---

## 0. Autorización por JWT (v1.1.0)

Este microservicio **protege sus operaciones de escritura con JWT** (RFC 7519,
HS256) emitidos por el microservicio de login. **La autorización se decide por
MÉTODO HTTP, no por ruta** — es lo único que permite que `GET /books` siga siendo
público mientras `POST /books` exige identidad, y que los alias de escritura
(incluido `POST /api/book/delete/{isbn}`, que es un `POST` que borra) no queden como
puerta trasera.

| Método | Autorización |
|---|---|
| `GET`, `HEAD`, `OPTIONS` | **Público** — cualquiera consulta el catálogo |
| `POST`, `PUT`, `PATCH`, `DELETE` | **`Authorization: Bearer <access_token>` obligatorio** |

Implementación: `jwt_auth.py` (verificador) + un guardia `@app.before_request`
(`enforce_jwt`) en `app.py`. El verificador es una **copia deliberada** del de login:
el contrato entre microservicios es el RFC 7519, no un módulo de Python compartido.

El verificador comprueba, en orden: formato de 3 segmentos → `alg` permitido
(`none` se **rechaza**) → firma HMAC-SHA256 en tiempo constante → `exp`/`nbf` con
`leeway` → `iss == library-login` → `aud == library-api`. Cada rechazo devuelve un
código distinto (`ALGORITHM_NONE_REJECTED`, `INVALID_SIGNATURE`, `TOKEN_EXPIRED`,
`INVALID_AUDIENCE`) en vez de un 401 mudo, y los 401 incluyen
`WWW-Authenticate: Bearer realm="library-books"`.

Los dos `/health` publican una **huella** del secreto compartido
(`secret_fingerprint`), para comprobar sin exponer la clave que login firma con la
misma clave con la que este servicio verifica.

Configuración en `.env`:

```
JWT_SECRET=<secreto compartido con el servicio de login>
JWT_ALGORITHM=HS256
JWT_ISSUER=library-login
JWT_AUDIENCE=library-api
LOGIN_BASE_URL=http://localhost:5000
PUBLIC_UNSAFE_PATHS=
```

> **Trade-off documentado:** al verificar por firma, este servicio **no consulta** al
> servicio de login ni a la base de datos (eso es lo que lo hace stateless y
> escalable). El precio es que un `logout` no llega aquí al instante: el token sigue
> siendo criptográficamente válido hasta que expire (≤ 15 minutos).

Evidencia completa, capturas y reflexión: `entrega_jwt/` (ver `entrega_jwt/README.md`).

---

## 1. Archivos en este Módulo

- `app.py`: Microservicio RESTful en Python Flask con conexión directa a PostgreSQL usando `psycopg` (v3) y documentación OpenAPI/Swagger en `/docs`.
- `requirements.txt`: Dependencias de Python (`flask`, `psycopg[binary]`, `python-dotenv`, `flask-cors`, `flasgger`, `gunicorn`).
- `library.xml` y `library02.xml`: Documentos XML con metadatos de libros y conceptos asociados a `estilo.css`.
- `estilo.css`: Hoja de estilos CSS pura para renderizado nativo de XML en el navegador.
- `library03.xml`: Documento XML estructurado para transformación XSLT con `library03.xsl`.
- `library03.xsl`: Plantilla de transformación declarativa XSLT con lógica de indicadores de stock condicionales (`in-stock`, `low-stock`, `out-stock`).
- `estilo03.css`: Sistema de diseño moderno Dark Mode Glassmorphism para la GUI HTML5 generada por XSLT.
- `.env.example` y `.env`: Configuración segura de credenciales de base de datos (`library_user` / `666`).

---

## 2. Instrucciones de Ejecución del Microservicio Flask

### 2.1 Instalación de Dependencias
```bash
python3 -m venv venv
source venv/bin/activate      # En Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2 Ejecución con Flask CLI (como en clase)
```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001
```

O directamente con Python:
```bash
python app.py
```

### 2.3 Acceso y Documentación Swagger
- **Swagger UI interactivo:** `http://localhost:5001/docs` (o `http://<IP_GCP>:5001/docs`)
- **API Endpoint Base:** `http://localhost:5001/books`
- **Health Check:** `http://localhost:5001/health`

---

## 3. Visualización Local de XML / XSLT
```bash
python3 -m http.server 8080
```
- XML con CSS puro: `http://localhost:8080/library.xml`
- GUI XSLT con Stock Condicional: `http://localhost:8080/library03.xml`

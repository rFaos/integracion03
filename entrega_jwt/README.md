# entrega_jwt — Autorización por JWT en los microservicios de la librería

**Integración de Aplicaciones Computacionales · SC-2236**
Fabián Azaed Orta Singlaterry · **613504** · Prof. Dr. Raúl Morales Salcedo

---

## La regla que se implementa

| Ruta | Método | Autorización |
|---|---|---|
| `/books`, `/api/books` | `GET`, `HEAD`, `OPTIONS` | **PÚBLICO** — cualquiera consulta el catálogo |
| `/books/{isbn}`, `/api/book/{isbn}` | `GET`, `HEAD`, `OPTIONS` | **PÚBLICO** |
| `/books`, `/api/book/insert` | `POST` | **JWT obligatorio** |
| `/books/{isbn}`, `/api/book/update/{isbn}` | `PUT` (y `POST` en el alias) | **JWT obligatorio** |
| `/books/{isbn}`, `/api/book/patch/{isbn}` | `PATCH` | **JWT obligatorio** |
| `/books/{isbn}`, `/api/book/delete/{isbn}` | `DELETE` (y `POST` en el alias) | **JWT obligatorio** |

**La autorización se decide por MÉTODO HTTP, no por ruta.** Es la única forma de que
`GET /books` siga siendo público mientras `POST /books` exige identidad, y de que
los alias de escritura —incluido `POST /api/book/delete/{isbn}`, que es un `POST` que
borra— no queden como puerta trasera.

---

## Contenido de esta carpeta

```
entrega_jwt/
├── README.md                  este archivo (índice)
├── REFLEXION.md               reflexión: integración del requerimiento, trampas
│                              del enunciado y por qué JWT importa en REST
├── EVIDENCIA.md               reporte con todas las capturas embebidas
├── Libreria_JWT_UDEM_613504.zip   entregable empaquetado (incluye los fuentes)
│
├── postman/
│   ├── Libreria_JWT_UDEM_613504.postman_collection.json   colección importable
│   └── Libreria_JWT_UDEM_613504.postman_environment.json  entorno con la IP
│
├── capturas/                  23 capturas de ejecuciones reales (PNG)
│
├── e2e_jwt_flow.py            prueba E2E de los 28 intercambios (41 aserciones)
├── app_python_jwt_smoke.py    prueba de la app Python con Bearer (16 aserciones)
│
├── evidencia_e2e.txt          bitácora literal petición/respuesta del E2E
├── evidencia_app_python.txt   bitácora de la app Python
├── flujo_e2e.json             el mismo flujo en JSON estructurado
├── newman_run.txt             corrida de la colección Postman con Newman
│
├── informes/                  los HTML que alimentan las capturas
├── tools/
│   ├── make_reports.py        genera los HTML desde la evidencia real
│   ├── capture_shots.py       captura los PNG con Playwright/Chromium
│   └── empaquetar.py          arma el .zip del entregable
└── runtime_demo/              config/sesión usados por la app Python en la prueba
```

---

## Cómo reproducirlo

Los dos microservicios tienen que estar levantados. Desde la raíz del monorepo:

```bash
# 1) Servicio de login (puerto 5000)
python apps/services/login/app.py

# 2) Servicio de libros (puerto 5001)
python apps/services/soap/app.py
```

Con los dos arriba:

```bash
# Prueba de humo del servicio de login (69 aserciones)
python apps/services/login/tests/smoke_test.py

# Flujo E2E completo: 28 intercambios, 41 aserciones
python entrega_jwt/e2e_jwt_flow.py

# La app Python con Bearer en cada CRUD y refresco automático (16 aserciones)
python entrega_jwt/app_python_jwt_smoke.py

# Regenerar los HTML de evidencia y las capturas
python entrega_jwt/tools/make_reports.py
python entrega_jwt/tools/capture_shots.py

# Correr la colección de Postman sin abrir Postman
npx newman run entrega_jwt/postman/Libreria_JWT_UDEM_613504.postman_collection.json \
  -e entrega_jwt/postman/Libreria_JWT_UDEM_613504.postman_environment.json
```

---

## Postman: cómo usarlo

1. Importar los **dos** archivos de `postman/`.
2. Seleccionar el entorno **"Librería JWT · local (613504)"**.
3. Verificar que `base_url_login` y `base_url_books` apunten a la IP de tu instancia
   (vienen con `172.32.132.174`; cambia solo el número si tu equipo tiene otra).
4. Correr las carpetas **en orden** (00 → 06), o toda la colección con el
   Collection Runner.

Las variables `access_token`, `refresh_token`, `captcha_id`, `isbn` y los cuatro
tokens maliciosos se llenan solas con los scripts de cada request: no hay que copiar
nada a mano.

> El secreto HS256 vive en el **entorno** (`{{jwt_secret}}`), no en la colección.
> Es el mismo principio que en producción: la clave va en variables de entorno o en
> un secret manager, nunca en el código fuente.
>
> **Pero un archivo de entorno de Postman sí es un archivo de código** (se versiona y
> se comparte), así que ahí el secreto queda expuesto de todos modos. Está puesto a
> propósito para que la colección corra sin configurar nada, y el razonamiento
> completo —incluida la alternativa correcta en un proyecto real (RS256)— está en
> **`postman/LEEME.md`**. Vale la pena leerlo antes de que alguien pregunte.

---

## Qué demuestra cada cosa

| Carpeta / archivo | Qué prueba |
|---|---|
| `capturas/01_publico_vs_protegido.png` | La misma ruta `/books`: `GET` → 200, `POST` → 401 |
| `capturas/02_login_emite_jwt.png` | `/login` devuelve `access_token` (JWT) + `refresh_token` |
| `capturas/03_crud_bearer.png` | `POST`/`PUT`/`PATCH` con `Authorization: Bearer` |
| `capturas/04_alias_book_insert.png` | El alias `POST /api/book/insert` con y sin token |
| `capturas/05_session_verify_refresh.png` | `/session`, `/verify` y la rotación de `/refresh` |
| `capturas/06_refresh_reuse.png` | Reutilizar un refresh token rotado → `REFRESH_REUSED` |
| `capturas/07_ataques_rechazados.png` | `alg:none`, firma ajena, expirado, audiencia ajena |
| `capturas/08_delete_logout.png` | `DELETE` sin token → 401; `logout` y token revocado |
| `capturas/09*_terminal_e2e_*.png` | Bitácora completa del flujo E2E |
| `capturas/10_terminal_app_python.png` | La app TK con Bearer y refresco automático |
| `capturas/11_instancia.png` | IP, puertos y los dos `/health` en vivo |
| `capturas/12/13_electron_*.png` | La app Electron sin token y con JWT |
| `capturas/14/15_swagger_*.png` | Swagger de los dos servicios |
| `capturas/16*_postman_newman_*.png` | La colección de Postman corrida con Newman: 28/28 peticiones, 45/45 aserciones |

El detalle de por qué cada una importa está en **`REFLEXION.md`**, sección 6.

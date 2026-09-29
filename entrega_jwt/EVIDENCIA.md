# Evidencia — Autorización por JWT en los microservicios de la librería

**Integración de Aplicaciones Computacionales · SC-2236**
Fabián Azaed Orta Singlaterry · matrícula **613504** · Prof. Dr. Raúl Morales Salcedo

**Instancia de la corrida:** equipo `Faos` · IPv4 `172.32.132.174`
**Servicio de login:** `http://172.32.132.174:5000` (también `127.0.0.1:5000`)
**Servicio de libros:** `http://172.32.132.174:5001` (también `127.0.0.1:5001`)
**Base de datos:** PostgreSQL 17.4 · base `library`
**Huella del secreto compartido:** `998b858a0b50` (idéntica en los dos servicios)

Toda la evidencia de este documento sale de ejecuciones **reales** contra los dos
microservicios levantados. Nada está escrito a mano.

---

## 0. La instancia

![Instancia en ejecución](capturas/11_instancia.png)

Los dos servicios y PostgreSQL corriendo en la misma máquina, con los dos `/health`
en vivo. Los dos reportan la **misma huella del secreto** (`998b858a0b50`), lo que
prueba que el servicio de login firma con la misma clave con la que el servicio de
libros verifica — sin exponer la clave.

---

## 1. La regla clave: la misma ruta, dos autorizaciones distintas

![Público vs protegido](capturas/01_publico_vs_protegido.png)

Las tres tarjetas de esta captura son el corazón del ejercicio:

| # | Petición | Resultado |
|---|---|---|
| 01 | `GET /books?format=json` **sin token** | **200** — catálogo público |
| 02 | `POST /books` **sin token** | **401** + `WWW-Authenticate: Bearer` |
| 03 | `POST /books?format=xml` **sin token** | **401**, negociado también en XML |

Fíjate en que la **ruta es la misma** (`/books`). Lo que cambia es el **método**.
Si la protección se hubiera puesto por ruta, el `GET` habría dejado de ser público;
si se hubiera puesto "todo `/books` abierto", el `POST` habría quedado sin
protección. La autorización se decide por método HTTP.

---

## 2. Dónde nace el token

![Login emite el JWT](capturas/02_login_emite_jwt.png)

`POST /login` (tras resolver el CAPTCHA y validar credenciales contra PostgreSQL)
devuelve:

- `access_token` — **JWT** de 3 segmentos, `algorithm: HS256`, `expires_in: 900` (15 min)
- `refresh_token` — **opaco**, `refresh_expires_in: 604800` (7 días)
- `token_type: Bearer`, `header: Authorization`, `refresh_endpoint: /refresh`
- `iss: library-login`, `aud: library-api`
- `_links` con `self`, `logout`, `user`, `refresh`, `verify`

El refresh token es **distinto** del access token y **no** es un JWT: es un valor
opaco de 48 bytes que el servidor guarda **solo como SHA-256**.

---

## 3. Escrituras protegidas con `Authorization: Bearer`

![CRUD con Bearer](capturas/03_crud_bearer.png)

- `POST /books` con Bearer → **201 Created**
- `PUT /books/{isbn}` con Bearer → **200** (reemplazo completo)
- `PATCH /books/{isbn}` con Bearer → **200** (modificación parcial)

---

## 4. Los alias: la puerta que no se ve

![Alias /api/book/insert](capturas/04_alias_book_insert.png)

El servicio expone las escrituras **por dos caminos**:

| Operación | Canónica | Alias |
|---|---|---|
| Crear | `POST /books` | `POST /api/book/insert` |
| Actualizar | `PUT /books/{isbn}` | `PUT /api/book/update/{isbn}` y **`POST`** |
| Parchear | `PATCH /books/{isbn}` | `PATCH /api/book/patch/{isbn}` |
| Borrar | `DELETE /books/{isbn}` | `DELETE /api/book/delete/{isbn}` y **`POST`** |

La captura muestra el alias `POST /api/book/insert`: **con** token → 201,
**sin** token → 401. Y nótese lo peligroso del último renglón de la tabla:
`POST /api/book/delete/{isbn}` es un **`POST` que borra**. Una lista de rutas
protegidas habría dejado ahí un agujero de borrado sin autenticación.

---

## 5. Sesión, introspección y rotación del refresh token

![Session, verify y refresh](capturas/05_session_verify_refresh.png)

- `GET /session` con Bearer → el servicio de login valida el JWT y responde
  `credential: "jwt"` con los claims (`sub`, `sid`, `jti`, `iss`, `aud`, `role`, `exp`).
- `POST /verify` → introspección **sin estado**: devuelve los claims del token.
- `POST /refresh` → **rota** el refresh token y emite un access token nuevo.

### Detección de reuso

![Reuso de refresh token](capturas/06_refresh_reuse.png)

Si alguien presenta un refresh token **ya rotado**, el servicio lo interpreta como
robo y responde **401 `REFRESH_REUSED`**, revocando **todas** las sesiones de ese
usuario. Un refresh token es de un solo uso.

---

## 6. Ataques contra el JWT: los cuatro rechazados

![Ataques rechazados](capturas/07_ataques_rechazados.png)

| Ataque | Token | Respuesta |
|---|---|---|
| `alg:none` | header `{"alg":"none"}`, sin firma | **401 `ALGORITHM_NONE_REJECTED`** |
| Firma ajena | HS256 firmado con `secreto-del-atacante` | **401 `INVALID_SIGNATURE`** |
| Expirado | HS256 correcto, `exp` en el pasado | **401 `TOKEN_EXPIRED`** |
| Audiencia ajena | HS256 correcto, `aud: otra-api` | **401 `INVALID_AUDIENCE`** |

El algoritmo lo decide **el servidor**, nunca el token: por eso `alg:none` se
rechaza explícitamente en vez de aceptarse "porque no hay firma que verificar".
La comparación de firma usa `hmac.compare_digest` (tiempo constante) para no
filtrar información por temporización.

Y un detalle importante: `GET /books` con un token basura **sigue respondiendo 200**.
Un token inválido no rompe la lectura pública; simplemente no autoriza escrituras.

---

## 7. Borrado y cierre de sesión

![Delete y logout](capturas/08_delete_logout.png)

- `DELETE /books/{isbn}` **con** Bearer → **200**
- `DELETE /books/{isbn}` **sin** token → **401**
- `POST /logout` → revoca la sesión
- `GET /session` con el token **ya revocado** → **401**

Aquí se ve el trade-off del modelo stateless: el servicio de login **sí** revoca de
inmediato (comprueba la sesión contra `user_sessions`), pero el servicio de libros
no puede enterarse hasta que el token expire — a lo sumo 15 minutos. Es un costo
consciente del JWT, mitigado con vidas cortas.

---

## 8. Bitácora completa del flujo E2E

![Apertura de la bitácora](capturas/09_terminal_e2e_apertura.png)

La corrida completa son **28 intercambios** y **41 aserciones, todas correctas**.
La bitácora vuelca cada petición y cada respuesta literales, encabezado por
encabezado.

![Público vs protegido en consola](capturas/09b_terminal_e2e_publico_vs_protegido.png)

![Login y JWT en consola](capturas/09c_terminal_e2e_login_jwt.png)

![Escritura con Bearer](capturas/09d_terminal_e2e_crud_bearer.png)

Nótese el `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpX...` en la
petición `POST /books` y el `[OK] POST /books con token responde 201`. Justo debajo,
`GET /books/{isbn} SIN token -> 200`: **la misma ruta** que el `PUT` protegido,
respondiendo sin credenciales.

![Sesión y refresco](capturas/09e_terminal_e2e_refresh.png)

![Ataques contra el JWT](capturas/09f_terminal_e2e_ataques.png)

![Resultado final](capturas/09g_terminal_e2e_resultado.png)

---

## 9. La app Python TK con `Bearer` en cada CRUD

![Bitácora de la app Python](capturas/10_terminal_app_python.png)

La aplicación de escritorio muestra en la **terminal**, por cada petición, un
encabezado de autenticación con el token y sus claims:

```
 [16:53:06] DELETE http://127.0.0.1:5001/books/TK-JWT-613504
   +-- AUTENTICACION ----------------------------------------------------------------
   | Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5...oEEwiEL0V7Ar2sqHmJeBfyIQ
   | JWT library-login  sub=37  rol=Usuario  sid=33  jti=f95ed1b4...
   | aud=library-api   expira en 14m 59s
   +-------------------------------------------------------------------------------
   <<< HTTP 200 en 97 ms   application/json
```

La corrida cubre 5 secciones y **16 aserciones, todas correctas**:

1. Registro y login (el login entrega `access_token` + `refresh_token`)
2. Lectura del catálogo **sin** token (endpoint público)
3. CRUD con `Authorization: Bearer <access_token>`
4. **Refresco automático**: la prueba fabrica un access token ya expirado, hace un
   `PATCH` y comprueba que el cliente recibe el 401, llama a `/refresh`, renueva y
   **reintenta una sola vez** con éxito
5. Borrado protegido y cierre de sesión

> El payload del JWT se decodifica **solo para mostrarlo** en pantalla. El código lo
> dice explícitamente: mostrar no es verificar.

---

## 10. La aplicación Electron

![Electron sin token](capturas/12_electron_publico.png)

La app Electron consume el catálogo en XML puro con `DOMParser`. Como `GET /books`
es público, funciona **sin token**: estado `Online: 10 libros (XML)` y el aviso
"Se cargaron 10 libros en formato XML".

![Electron con Bearer](capturas/13_electron_con_bearer.png)

Con el JWT pegado en el campo `🔐 JWT (opcional)`, el mismo renderer añade el
encabezado `Authorization: Bearer ...` y lo reporta en el estado:
`Online: 10 libros (XML) · con JWT`. La app demuestra así las **dos mitades** de la
regla: el catálogo se lee sin permiso, y el mismo cliente está listo para
autenticarse cuando la operación lo exige.

---

## 11. Documentación Swagger de los dos servicios

![Swagger login](capturas/14_swagger_login.png)

![Swagger libros](capturas/15_swagger_books.png)

Ambos servicios exponen su Swagger en `/docs`, con el esquema de seguridad
`BearerJWT` declarado y la respuesta `401` documentada en cada operación de
escritura.

---

## 12. Postman

La colección importable está en `postman/`:

- `Libreria_JWT_UDEM_613504.postman_collection.json` — 7 carpetas, 28 peticiones
- `Libreria_JWT_UDEM_613504.postman_environment.json` — entorno con la IP y las
  variables (`base_url_login`, `base_url_books`, `jwt_secret`, `access_token`, …)

El entorno apunta a la instancia real (`172.32.132.174`), así que basta con
seleccionarlo y correr las carpetas en orden. Las variables se llenan solas con los
scripts de cada petición: no hay que copiar ningún token a mano.

### La colección corrida con Newman

Para no dejar la colección "en el editor y ya", se ejecutó con **Newman**, el runner
oficial de Postman por línea de comandos, contra la instancia real:

![Colección con Newman](capturas/16_postman_newman_apertura.png)

![Resumen de Newman](capturas/16b_postman_newman_resultado.png)

```
requests   28   failed  0
assertions 45   failed  0
```

Se ve además que las dos comprobaciones de `/health` reportan la **misma huella del
secreto** (`998b858a0b50`) y que `GET /books` con un token basura **sigue
respondiendo 200**: un token inválido no rompe la lectura pública.

La salida completa está en `newman_run.txt`.

---

## 13. Resumen de las suites

| Suite | Archivo | Resultado |
|---|---|---|
| Servicio de login (smoke) | `apps/services/login/tests/smoke_test.py` | **69 / 69** aserciones |
| Flujo E2E de los dos servicios | `entrega_jwt/e2e_jwt_flow.py` | **41 / 41** aserciones, 28 intercambios |
| App Python TK con Bearer | `entrega_jwt/app_python_jwt_smoke.py` | **16 / 16** aserciones |
| Colección de Postman (Newman) | `entrega_jwt/postman/` | **28 / 28** peticiones, **45 / 45** aserciones |

El detalle de **por qué** cada cosa está hecha así —las cinco trampas del enunciado,
la decisión por método HTTP y el papel del JWT en REST— está en **`REFLEXION.md`**.

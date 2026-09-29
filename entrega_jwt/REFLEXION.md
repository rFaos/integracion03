# Reflexión — Autorización por JWT en los microservicios de la librería

**Integración de Aplicaciones Computacionales · SC-2236**
Fabián Azaed Orta Singlaterry · matrícula **613504** · Prof. Dr. Raúl Morales Salcedo

---

## 1. Qué se pidió (y qué se entregó)

El requerimiento era proteger **las operaciones de escritura** del microservicio de
libros (`POST`, `PUT`, `PATCH`, `DELETE`) exigiendo un **JWT válido emitido por el
microservicio de login**, dejando **públicas** las lecturas `GET /api/books` y
`GET /api/books/{isbn}`.

La forma ingenua de resolverlo es hacer una **lista de rutas protegidas**. Eso es
justo lo que el enunciado castiga. La solución entregada decide la autorización
**por método HTTP**, no por ruta: `GET`, `HEAD` y `OPTIONS` pasan siempre; todo lo
demás exige `Authorization: Bearer <access_token>`.

---

## 2. Las trampas del enunciado, una por una

El profesor advirtió que había "trampillas". Al leer el requerimiento con cuidado,
aparecen al menos cinco. Ninguna se resuelve escribiendo una lista de rutas.

### Trampa 1 — "protege `/books`" pero "`GET /books` es público"

Es la **misma URL**. Si se protege la ruta `/books`, se rompe la lectura pública
que el propio enunciado exige conservar. Si no se protege, cualquiera puede
insertar libros.

**Resolución:** la regla no vive en la ruta, vive en el **método**.

```python
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

@app.before_request
def enforce_jwt():
    if request.method == "OPTIONS" or request.method in SAFE_METHODS:
        return None          # lectura pública
    if is_public_request(request.method, request.path):
        return None
    # a partir de aquí: escritura -> JWT obligatorio
```

La evidencia está en la captura `01_publico_vs_protegido.png`:
`GET /books` → **200**, `POST /books` → **401**. Misma ruta, distinta autorización.

### Trampa 2 — los alias: la puerta que no se ve

El servicio de libros expone **cuatro escrituras por dos caminos distintos**:

| Operación | Ruta canónica | Alias |
|---|---|---|
| Crear | `POST /books` | `POST /api/book/insert` |
| Reemplazar | `PUT /books/{isbn}` | `PUT /api/book/update/{isbn}` **y `POST`** |
| Modificar | `PATCH /books/{isbn}` | `PATCH /api/book/patch/{isbn}` |
| Borrar | `DELETE /books/{isbn}` | `DELETE /api/book/delete/{isbn}` **y `POST`** |

Fíjate en lo peligroso: `POST /api/book/delete/{isbn}` **es un `POST` que borra**.
Quien protegiera "las rutas `/books`" y dejara los alias abiertos, tendría un
borrado sin autenticación. Y quien protegiera solo `POST /books` por ruta, también.

**Resolución:** como la decisión es por **método**, cualquier alias presente o
futuro queda cubierto automáticamente. No hay que enumerar nada. La evidencia está
en `04_alias_book_insert.png`: `POST /api/book/insert` **con** token → 201, **sin**
token → 401.

### Trampa 3 — el servicio de login NO se protege

Si se aplicara el guardia "a todo lo que sea escritura" en el servicio de login, se
cerrarían `POST /register` y `POST /login`… y **nadie podría obtener un token**.
Es una dependencia circular: para pedir el token hay que poder pedir el token.

**Resolución:** el guardia vive **solo en el servicio de libros**. El servicio de
login mantiene abiertos `POST /register`, `POST /login` y `GET /captcha`
(este último es además la defensa contra automatización). El propio `/` del
servicio de libros lo declara en su bloque `security`, y `PUBLIC_UNSAFE_PATHS`
queda vacío porque no hay ninguna escritura pública legítima.

### Trampa 4 — "tener un token" no es "tener un token válido"

Un `Authorization: Bearer ...` con cualquier cosa dentro no debe abrir la puerta.
El verificador comprueba, en este orden:

1. Formato: 3 segmentos separados por punto.
2. **`alg` permitido**: `none` se **rechaza explícitamente** (ataque clásico), y el
   algoritmo lo decide el **servidor**, nunca el token.
3. **Firma** HMAC-SHA256 con el secreto compartido, comparada en **tiempo
   constante** (`hmac.compare_digest`) para no filtrar información por temporización.
4. `exp` y `nbf` (con `leeway` de 5 s).
5. `iss == "library-login"` y `aud == "library-api"`.

Cada rechazo devuelve un **código distinto** — `ALGORITHM_NONE_REJECTED`,
`INVALID_SIGNATURE`, `TOKEN_EXPIRED`, `INVALID_AUDIENCE` — para que el error sea
diagnosticable en vez de un 401 mudo. Evidencia: `07_ataques_rechazados.png`.

### Trampa 5 — el payload se lee

El payload de un JWT va **codificado en Base64URL, no cifrado**. Cualquiera con el
token puede leerlo. Por eso el payload de este proyecto solo lleva identificadores y
metadatos (`sub`, `sid`, `jti`, `email`, `role`, `iss`, `aud`, `iat`, `nbf`, `exp`)
y **jamás** la contraseña, el hash de la contraseña ni datos personales sensibles.

La bitácora de la app Python (`10_terminal_app_python.png`) muestra esto en
pantalla: decodifica el payload **solo para mostrarlo** y lo dice explícitamente —
mostrar no es verificar.

---

## 3. Cómo se integró el requerimiento a lo que ya existía

La integración fue **incremental y compatible**: los clientes viejos siguen
funcionando, y el modelo nuevo convive con el viejo.

### 3.1 El token: access corto + refresh rotativo

| | Access token | Refresh token |
|---|---|---|
| Formato | **JWT** firmado HS256 | **Opaco** (`secrets.token_urlsafe(48)`) |
| Duración | 15 minutos | 7 días |
| Se guarda en el servidor | **No** (stateless) | Sí, **solo su SHA-256** |
| Para qué sirve | Autorizar cada petición | Pedir un access token nuevo |
| Si lo roban | Caduca solo en ≤ 15 min | Se detecta el reuso y se revocan **todas** las sesiones |

El refresh token **rota en cada uso**: al llamar `POST /refresh` se emite un par
nuevo y el anterior queda marcado como rotado. Si alguien presenta un refresh token
ya rotado, el servicio asume robo y revoca la sesión completa
(`REFRESH_REUSED`). Evidencia: `06_refresh_reuse.png`.

### 3.2 Verificación sin estado, con la puerta abierta a revocar

El servicio de libros verifica el JWT **con la firma**, sin consultar PostgreSQL ni
al servicio de login. Esa es la gracia del modelo stateless: la identidad viaja
firmada dentro del token.

El precio de eso es que un `logout` en el servicio de login **no llega
instantáneamente** al servicio de libros: el token sigue siendo criptográficamente
válido hasta que expire (≤ 15 minutos). Es un trade-off consciente y documentado.

Para el caso en que sí se necesita corte inmediato, el servicio de login tiene
`JWT_CHECK_SESSION=true`: además de la firma, comprueba contra `user_sessions` que
la sesión siga viva. Por eso `GET /session` con el token revocado responde 401
inmediatamente (evidencia `08_delete_logout.png`), mientras el servicio de libros
habría seguido aceptándolo hasta su expiración.

### 3.3 Una sola clave, dos servicios, verificada por huella

Ambos servicios comparten el secreto por variable de entorno (nunca en el código).
Los dos `/health` publican una **huella** del secreto (`secret_fingerprint`), que en
esta corrida es la misma en los dos: `998b858a0b50`. Es una comprobación barata de
que login firma con la misma clave con la que libros verifica — sin imprimir la
clave.

El verificador del servicio de libros es una **copia deliberada** del de login, no
un `import` compartido. La razón: el contrato entre microservicios es el **RFC 7519**,
no un módulo de Python. Un servicio de libros en Java o Go tendría que implementar
lo mismo leyendo el RFC. Compartir código entre servicios despliega acoplamiento;
compartir un **estándar** no.

### 3.4 Compatibilidad hacia atrás

El servicio de login sigue aceptando el `X-Session-Token` opaco de la versión
anterior (`credential: "opaque"` en `GET /session`), y `POST /logout` acepta tanto
un JWT como un refresh token. La respuesta de `/login` incluye `access_token`
(nuevo) y `token` (alias del anterior), así que ningún cliente existente se rompió.

### 3.5 Los clientes

- **App Python TK:** manda `Authorization: Bearer <access_token>` en **cada**
  operación CRUD. Al recibir un 401 intenta **una** renovación con
  `POST /refresh` y reintenta la petición original una sola vez (con el encabezado
  `X-Token-Refreshed` para que quede trazable). En la terminal imprime, por cada
  petición, un **encabezado de autenticación** con el token enmascarado y los claims
  del JWT (`sub`, `role`, `sid`, `jti`, `aud`, expiración).
- **App Electron:** el catálogo es un `GET`, así que funciona **sin token**. Se
  añadió un campo opcional de JWT que, si se llena, agrega el encabezado Bearer y lo
  reporta en el estado (`Online: 10 libros (XML) · con JWT`). Así el mismo renderer
  demuestra las dos mitades de la regla.

---

## 4. Por qué JWT importa en la arquitectura REST

### 4.1 REST pide un servidor sin estado, y la sesión clásica lo contradice

El estilo REST (Fielding, 2000) tiene en la ausencia de estado en el servidor uno de
sus seis constraints. La sesión tradicional lo rompe: el servidor guarda un
`session_id → usuario` en memoria o en base de datos. Consecuencias prácticas:

- **Escalar horizontalmente es un problema.** Si hay tres réplicas del servicio de
  libros, cada petición tiene que llegar a la réplica que conoce esa sesión, o todas
  tienen que compartir el almacén de sesiones. Eso es un punto único de fallo y un
  viaje extra a la base en **cada** petición.
- **Cada petición cuesta una consulta.** Con sesión en base: un `SELECT` por
  request solo para averiguar quién eres. Con JWT: cero consultas, solo una
  verificación de firma, que es aritmética local.

El JWT mueve la identidad **al cliente**, firmada. El servidor no recuerda nada, y
cualquier réplica puede atender cualquier petición.

### 4.2 Un token, varios servicios

Este es el punto que justifica el JWT en una arquitectura de microservicios como la
de este proyecto. El token lo emite **login** y lo verifica **libros** sin que
ninguno de los dos hable con el otro. Si mañana se agrega un servicio de préstamos o
de reseñas, verifica el mismo token con la misma clave y funciona: **no hay que
construir una base de sesiones compartida** ni pedirle permiso al servicio de login
en cada petición.

Sin JWT, ese tercer servicio tendría que consultar el almacén de sesiones del
primero. Con JWT, los servicios quedan **desacoplados en tiempo de ejecución**: se
conocen por un contrato criptográfico, no por una llamada de red.

### 4.3 Autenticación ≠ autorización

Conviene separar dos cosas que el token permite separar limpiamente:

- **Autenticación** (¿quién eres?): la resuelve el servicio de login validando
  credenciales contra PostgreSQL y firmando el token.
- **Autorización** (¿qué puedes hacer?): la resuelve **cada** servicio. En este
  proyecto el servicio de libros no pregunta "¿es válido este usuario?" sino "¿este
  método HTTP requiere identidad?" y, si la requiere, "¿la firma es buena y el token
  es para mí?".

Esa separación es la que permite que el catálogo sea público y las escrituras
privadas **en el mismo endpoint**, sin duplicar lógica de autenticación.

### 4.4 El costo: lo que el JWT no resuelve

Ser honesto sobre las limitaciones es parte de elegirlo bien:

- **Revocación inmediata.** Un JWT es válido hasta que expira; no se puede "retirar"
  sin consultar algo. Se mitiga con vidas cortas (15 min) y refresh tokens
  revocables.
- **El payload es público.** Nunca datos sensibles dentro.
- **Rotación de claves.** Cambiar el secreto invalida **todos** los tokens vivos.
  En producción esto se resuelve con `kid` (identificador de clave en el header) y
  varias claves válidas a la vez, o con RS256 y un JWKS público.
- **Un secreto compartido se multiplica.** HS256 con clave compartida entre N
  servicios significa N lugares donde la clave puede filtrarse. Para equipos grandes
  se prefiere asimétrico (RS256/ES256): el emisor firma con la privada y los demás
  verifican con la pública. **Con HS256, cualquier servicio que verifique puede
  también firmar** — es el precio de la simetría.

> En esta entrega, el valor real del secreto aparece en la variable de entorno de la
> colección de Postman. Es deliberado (para que la carpeta de ataques pueda firmar
> tokens válidos y la colección corra sin configurar nada), pero un archivo de
> entorno de Postman **es** un archivo de código que se versiona. El razonamiento
> completo y las alternativas correctas están en `postman/LEEME.md`. Los `.env` del
> repositorio sí están en `.gitignore`, y los `.env.example` llevan placeholder.

---

## 5. Conclusión

La lección del ejercicio no es "poner un JWT", es que **el modelo de autorización
tiene que ser una regla, no una lista**. Una lista de rutas protegidas se rompe en
cuanto alguien agrega un alias, y este servicio ya tenía cuatro escrituras por dos
caminos cada una —incluido un `POST` que borra—.

La regla correcta cabe en una frase: *el catálogo se lee sin permiso, se modifica
con identidad*. Al expresarla como "los métodos seguros son públicos, los inseguros
exigen un JWT válido", la implementación cubre los alias de hoy y los de mañana,
mantiene la lectura abierta como pide el enunciado y deja el servicio de login
accesible para que el token pueda existir.

Y el JWT es la pieza que hace que esa regla funcione **entre** servicios: la
identidad viaja firmada con el usuario, se verifica localmente en cada servicio y
REST conserva lo que lo hace escalable — un servidor que no recuerda a nadie.

---

## 6. Evidencia

Todas las capturas están en `entrega_jwt/capturas/` y todas salen de ejecuciones
reales contra los servicios levantados en `172.32.132.174` (login en `:5000`,
libros en `:5001`).

| Captura | Qué demuestra |
|---|---|
| `01_publico_vs_protegido.png` | Misma ruta `/books`: `GET` → 200 público, `POST` → 401 con `WWW-Authenticate` |
| `02_login_emite_jwt.png` | `/login` devuelve `access_token` (JWT) + `refresh_token`, `expires_in: 900`, `algorithm: HS256` |
| `03_crud_bearer.png` | `POST`/`PUT`/`PATCH` con `Authorization: Bearer` → 201/200/200 |
| `04_alias_book_insert.png` | El alias `POST /api/book/insert`: con token 201, sin token 401 |
| `05_session_verify_refresh.png` | `/session`, `/verify` y `/refresh` (rotación) |
| `06_refresh_reuse.png` | Reutilizar un refresh token rotado → 401 `REFRESH_REUSED` |
| `07_ataques_rechazados.png` | `alg:none`, firma ajena, expirado y audiencia ajena → 401 cada uno |
| `08_delete_logout.png` | `DELETE` sin token → 401; `logout` y token revocado → 401 |
| `09*_terminal_e2e_*.png` | Bitácora completa de los 28 intercambios (41 aserciones OK) |
| `10_terminal_app_python.png` | La app TK con Bearer en cada CRUD y refresco automático (16 aserciones OK) |
| `11_instancia.png` | IP `172.32.132.174`, puertos y los dos `/health` en vivo |
| `12_electron_publico.png` / `13_electron_con_bearer.png` | La app Electron funcionando sin token y con JWT |
| `14_swagger_login.png` / `15_swagger_books.png` | Documentación Swagger de ambos servicios |
| `16_postman_newman_*.png` | La colección de Postman corrida con Newman: 28/28 peticiones, 45/45 aserciones |

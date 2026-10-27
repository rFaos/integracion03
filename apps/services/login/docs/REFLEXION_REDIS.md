# Reflexión: Redis en los microservicios de Library

**Proyecto:** INTEGRACION03 — Microservicios de la librería en línea
**Autor:** Fabián Azaed Orta Singlaterry (Matrícula 613504)
**Curso:** SC-2236 — Universidad de Monterrey (UDEM)
**Fecha:** 6 de octubre de 2026

---

## 1. Por qué usar Redis

PostgreSQL es la **fuente de verdad**: guarda usuarios, libros, autores, pedidos y
pagos, y garantiza ACID. Pero hay tres necesidades que PostgreSQL resuelve mal por
su propia naturaleza:

| Necesidad | Por qué PostgreSQL no es la herramienta |
|---|---|
| **Sesiones y refresh tokens** | Se consultan en *cada* petición. Eso es una escritura (o al menos una lectura + `UPDATE last_seen_at`) por request. Con 6 microservicios hablando de sesiones, la base se convierte en el cuello de botella. |
| **Revocación de JWT** | El access token es **sin estado** por diseño: cualquier servicio lo valida sin consultar nada. Ese es su mérito y su defecto — al hacer `/logout`, los demás servicios no se enteran hasta que el token expira. Sin un almacén compartido, la revocación inmediata es imposible. |
| **Caché del catálogo** | `GET /books` es la consulta más repetida y la más cara (JOINs con autores, géneros, formatos, imágenes y conceptos). Es lectura pura y cambia poco: el caso ideal para cachear. |

Redis aporta exactamente lo que falta:

- **Latencia sub-milisegundo** en memoria, en vez de una consulta con JOINs.
- **TTL nativo**: una clave puede *nacer con fecha de muerte*. No hace falta un
  `cron` que borre sesiones expiradas: Redis lo hace solo. Eso es justamente lo
  que pide el enunciado ("TTL coherentes").
- **Estado compartido entre procesos**: es lo que permite que el login revoque un
  token y que el servicio de libros lo respete al instante, sin que uno llame al otro.

La frase que resume el diseño: **PostgreSQL guarda la verdad; Redis guarda el
estado vivo y lo efímero.**

---

## 2. Qué endpoints son los adecuados para Redis y JWT

### 2.1 Endpoints que escriben estado en Redis (sesión / revocación)

| Servicio | Endpoint | Uso de Redis | TTL |
|---|---|---|---|
| login | `POST /login` | Guarda `session:<sid>` y `refresh:<sha256>` | 7 días (`JWT_REFRESH_DAYS`) |
| login | `POST /refresh` | Rotación atómica del refresh (`rotate_refresh`) | 7 días |
| login | `POST /session/extend` | Renueva el TTL de la sesión | 7 días |
| login | `POST /logout` | Escribe `jwt:revoked:<jti>` y borra sesión + refresh | vida restante del token |
| login | `PATCH /profile` | Refresca el espejo de la sesión | 7 días |
| **todos** | cualquier `POST/PUT/PATCH/DELETE` | **Lee** `jwt:revoked:<jti>` antes de autorizar | — |

### 2.2 Endpoints que se cachean (lecturas públicas)

| Servicio | Endpoint | Clave | TTL |
|---|---|---|---|
| books | `GET /books` | `books:list:<filtros>` | corto (30 s) |
| books | `GET /books/<isbn>` | `books:<isbn>` | corto (30 s) |
| users | `GET /users` | `users:list:<filtros>` | corto |
| autores | `GET /autores` | `autores:list:<filtros>` | corto |
| pedidos | `GET /pedidos/<id>` | `pedidos:<id>` | corto |

**La regla de invalidación** es la parte que más se olvida: después de cualquier
`POST`, `PUT`, `PATCH` o `DELETE`, hay que **borrar** las claves de caché
afectadas. En este proyecto se decidió hacerlo **por método HTTP** en el hook
`after_request`: si el método no es seguro (`GET/HEAD/OPTIONS`) y la respuesta fue
exitosa, se invalida todo el caché del catálogo. Así queda cubierto de una sola
vez cada alias (`/api/book/insert`, `/api/book/update`, `/api/book/patch`,
`/api/book/delete`) sin enumerar rutas — y sin riesgo de olvidar una.

### 2.3 Endpoints que NO deben cachearse

Todo lo que devuelve **datos de un usuario autenticado** (`/session`, `/profile`,
`/users/<id>`) o que depende de un `Authorization`. Cachear ahí sería un agujero
de seguridad: la respuesta de un usuario podría servirse a otro. Redis, en esos
casos, se usa como **almacén de estado**, nunca como caché de respuesta.

---

## 3. Cómo debe implementarse

### 3.1 Una sola URL, un solo contrato

Todos los servicios se conectan a la **misma instancia** con la misma variable:

```
REDIS_URL=redis://:password@host:6379/0
```

Lo compartido no es código, es **contrato** (igual que con el JWT): los mismos
prefijos de clave y los mismos TTL. Cada servicio lleva su propia copia de
`redis_layer.py` — es una **copia deliberada**, no un paquete importado, porque
cada microservicio se despliega por separado y no debe acoplarse al repositorio
de otro.

### 3.2 Contrato de claves

```
session:<sid>                 -> JSON de la sesión
refresh:<sha256(refresh)>     -> JSON con sid/user_id   (NUNCA el token en claro)
jwt:revoked:<jti>             -> "1"
books:list:<filtros>          -> JSON de la lista
books:<isbn>                  -> JSON del libro
```

Dos detalles que evitan bugs silenciosos:

- Los **filtros se ordenan** antes de formar la clave, para que
  `/books?autor=1&tema=2` y `/books?tema=2&autor=1` compartan la misma entrada.
- El **refresh token se guarda hasheado** (SHA-256), con el mismo criterio que las
  contraseñas: si Redis se filtra, lo guardado no sirve para autenticarse.

### 3.3 TTL coherentes

El TTL no se inventa en cada servicio: lo define el emisor y los demás lo heredan
de la configuración. La sesión en Redis vive exactamente lo mismo que la fila en
`user_sessions`, y la entrada de revocación vive **solo la vida restante del
token** — cuando el token caduca por sí solo, la entrada sobra y Redis la
descarta. Así la lista de revocación no crece sin control.

### 3.4 La parte crítica: política de fallo **asimétrica**

El enunciado lo pide de forma explícita y es la trampa más fácil de cometer:

> Redis debe ser opcional para lecturas cacheadas, pero las operaciones de
> sesión, revocación y autorización deben fallar de forma segura si Redis no está.

```
Caché (GET)        ->  fail-OPEN   : si Redis cae, se va a PostgreSQL y la
                                      petición sigue funcionando.
Autorización       ->  fail-CLOSED : si Redis cae, NO se autoriza (503).
```

La clave está en un detalle de implementación que parece menor y no lo es:

```python
def is_revoked(jti):
    # ...
    client = _critical("is_revoked")   # LANZA RedisUnavailable si Redis no responde
```

`is_revoked()` **lanza una excepción** en vez de devolver `False` cuando no puede
consultar. Devolver `False` sería un fallo abierto disfrazado: significaría tratar
*"no pude comprobar la revocación"* como *"no está revocado"*, que es exactamente
el agujero que la lista de revocación venía a cerrar. Por eso el fallo se traduce
a **503**, nunca a un "acceso concedido".

### 3.5 Seguridad adicional

- La contraseña de Redis viaja **solo** por `REDIS_URL` (variable de entorno) y
  nunca se imprime: `mask_url()` la tapa para los logs y para `/health`.
- No se guardan contraseñas ni tokens en claro, ni en Redis ni en los logs.
- Timeouts explícitos (`REDIS_SOCKET_TIMEOUT=0.5`) para que un Redis colgado no
  cuelgue a su vez a los microservicios.
- El secreto JWT (`JWT_SECRET_KEY`) también va por variable de entorno, es el
  mismo en todos los servicios y **nunca** se escribe en el código.
- 401 para token ausente o inválido, 403 para rol insuficiente, 503 para fallo de
  infraestructura.

---

## 4. Qué quedó implementado y qué falta

**Implementado y verificado en esta sesión** (login + books):

- Capa `redis_layer.py` con el contrato de claves, TTL, métricas y política
  asimétrica de fallo → **36/36 comprobaciones** (`tests/redis_selftest.py`).
- JWT de **20 minutos** (antes 15), sesión y refresh en Redis con TTL, y
  `jwt:revoked:<jti>` en `/logout`.
- Verificación de la revocación **en los dos servicios**, caché de `GET /books` y
  `GET /books/<isbn>`, e invalidación por método en `after_request`.
- Prueba end-to-end contra PostgreSQL real: **30/30 comprobaciones**
  (`tests/e2e_redis_jwt.py`), incluida la prueba clave — tras `/logout`, el
  servicio de **libros** rechaza el token con `TOKEN_REVOKED` sin esperar a que
  expire.

**Pendiente** (fuera del alcance de la ventana de tiempo):

- Los cuatro microservicios nuevos (**users, autores, pedidos, pagos**) deben
  heredar `redis_layer.py` y aplicar el mismo guardián de revocación.
- Cliente Tk: integración de los servicios nuevos con semáforos de estado y
  conmutador HTTP/HTTPS persistente.
- Animación del flujo completo y evidencias de Postman/curl por servicio.

---

## Conclusión

Redis no reemplaza a PostgreSQL: lo **complementa**. PostgreSQL responde *qué es
verdad*; Redis responde *qué está pasando ahora* — quién tiene sesión, qué token
fue revocado, qué consulta ya se calculó. En una arquitectura de microservicios,
donde los procesos no comparten memoria, Redis es la pieza que convierte un
conjunto de servicios aislados en un sistema con estado coherente. Y el detalle
que separa una implementación correcta de una peligrosa no es el `GET`/`SET`:
es **decidir, servicio por servicio, si un fallo de Redis debe cerrar la puerta o
dejar pasar**.

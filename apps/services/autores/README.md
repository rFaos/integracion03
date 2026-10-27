# Microservicio de Autores (`autores`)

**Puerto:** 5003 · **Ruta:** `apps/services/autores` · **Autor:** Fabián Azaed Orta Singlaterry (613504) · **UDEM SC-2236**

Administra **autores y su relación con los libros** (tabla puente `book_authors`).

## Seguridad

A diferencia del servicio de usuarios, aquí las **lecturas son públicas**: un
autor y su bibliografía son metadatos de catálogo, no datos personales. Es justo
lo que pide el enunciado: *"las lecturas GET pueden mantenerse públicas si solo
consultan información; las lecturas administrativas deberían exigir JWT"*.

- `GET` sobre `/autores` → **público**, sin token.
- Cualquier escritura → exige JWT **y** rol Administrador.
- El token se comprueba contra `jwt:revoked:<jti>` en Redis (503 si Redis cae).

## Endpoints

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/` | público | Información e hipermedia |
| GET | `/health` | público | Sonda: base, JWT, Redis |
| GET | `/autores` | público | Lista con filtros (`name`, `country`, `limit`, `offset`) — **cacheada** |
| GET | `/autores/<id>` | público | Detalle + sus libros — **cacheado** |
| GET | `/autores/<id>/libros` | público | Libros del autor |
| POST | `/autores` | Administrador | Crear |
| PUT | `/autores/<id>` | Administrador | Reemplazo completo |
| PATCH | `/autores/<id>` | Administrador | Modificación parcial |
| DELETE | `/autores/<id>` | Administrador | Eliminar (409 si todavía tiene libros) |
| POST | `/autores/<id>/libros` | Administrador | Asociar libros (`book_ids: [1,2]`) |
| DELETE | `/autores/<id>/libros/<book_id>` | Administrador | Quitar la relación (no borra el libro) |

Documentación interactiva en `/docs`.

## Caché en Redis

`GET /autores` y `GET /autores/<id>` se cachean con TTL corto bajo las claves
`autores:list:<filtros>` y `autores:<id>`. Toda escritura exitosa invalida el
caché completo del recurso en `after_request`, decidido **por método**: así quedan
cubiertos de una sola vez el alta, el reemplazo, el parche, el borrado y las dos
rutas de relación, sin poder olvidar ninguna.

El caché es **opcional por diseño** (fail-open): si Redis no responde, la lectura
se sirve desde PostgreSQL. Lo que no se degrada es la autorización.

## Relación con libros

La relación se modela como **recurso propio** (`/autores/<id>/libros`) y no como
un campo `books: [...]` dentro del autor. La razón: la relación tiene identidad
propia, y así el endpoint dice exactamente qué se está creando o destruyendo.
Asociar es idempotente (`ON CONFLICT DO NOTHING`): si la relación ya existía, se
informa en `already_linked` en vez de fallar.

## Configuración y arranque

Ver `.env.example`: `DB_*`, `PORT=5003`, `JWT_SECRET` compartido,
`ADMIN_ROLE_ID=1`, `CORS_ORIGINS`, `REDIS_URL`, `REDIS_CACHE_TTL`.

```bash
cp .env.example .env
pip install -r requirements.txt
../../scripts/servicios.sh start
```

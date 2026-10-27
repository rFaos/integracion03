# Microservicio de Usuarios (`users`)

**Puerto:** 5002 · **Ruta:** `apps/services/users` · **Autor:** Fabián Azaed Orta Singlaterry (613504) · **UDEM SC-2236**

Administra **usuarios, roles, correos y contraseñas**. Es lo que el servicio de
login solo hace a medias: allí uno se registra y se autentica; aquí se administra
(crear cuentas, cambiar roles, activar/desactivar, corregir correos, resetear
contraseñas).

## Seguridad

Todas las operaciones exigen `Authorization: Bearer <JWT>` (HS256, emitido por el
servicio de login). Además:

- **Listar usuarios y roles** (`GET /users`, `GET /roles`) es lectura
  administrativa: exige **rol Administrador**.
- **Toda escritura** exige rol Administrador.
- Un usuario normal solo puede leer **su propio** registro (`GET /users/<id>` con
  `id == sub`); si intenta leer otro, recibe 403.
- El token se comprueba contra la lista de revocación `jwt:revoked:<jti>` en
  Redis. Si Redis no responde → **503** (fail-closed).
- `password_hash` **nunca** aparece en una respuesta ni en un log.

| Código | Cuándo |
|---|---|
| 401 | Token ausente, inválido, expirado o revocado |
| 403 | Rol insuficiente, o intentar leer el registro de otro usuario |
| 409 | El correo ya existe / el usuario tiene registros asociados |
| 503 | Redis no permite comprobar la revocación |

## Endpoints

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/` | público | Información e hipermedia |
| GET | `/health` | público | Sonda: base, esquema, JWT, Redis |
| GET | `/roles` | Administrador | Catálogo de roles |
| GET | `/users` | Administrador | Lista con filtros (`role_id`, `is_active`, `email`, `limit`, `offset`) |
| GET | `/users/<id>` | Administrador o el propio usuario | Detalle |
| POST | `/users` | Administrador | Crear (`email` y `password` obligatorios) |
| PUT | `/users/<id>` | Administrador | Reemplazo completo (400 si falta un campo editable) |
| PATCH | `/users/<id>` | Administrador | Modificación parcial; acepta `password` para resetear |
| DELETE | `/users/<id>` | Administrador | Eliminar (no puede borrarse a sí mismo) |

Documentación interactiva en `/docs`.

## Configuración

Ver `.env.example`. Lo esencial: `DB_*`, `PORT=5002`, `JWT_SECRET` (idéntico al de
los demás servicios), `ADMIN_ROLE_ID=1`, `CORS_ORIGINS` (lista explícita, nunca
`*`) y `REDIS_URL`.

## Arranque

```bash
cp .env.example .env     # y editar los valores reales
pip install -r requirements.txt
../../scripts/servicios.sh start
```

Prueba: `python tests/smoke_users.py` — 28 comprobaciones que cubren la matriz de
autorización, el CRUD completo, el aislamiento entre usuarios, la revocación del
token y el comportamiento fail-closed cuando Redis no responde.

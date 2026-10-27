# Microservicio de Pagos (`pagos`)

**Puerto:** 5005 · **Ruta:** `apps/services/pagos` · **Autor:** Fabián Azaed Orta Singlaterry (613504) · **UDEM SC-2236**

Registra **pagos** y, cuando el pago queda aprobado, **actualiza el estado del
pedido**. Su razón de ser es que el cobro y el cambio de estado ocurran **en una
sola transacción**: no puede existir un pago cobrado con el pedido todavía sin
marcar, ni un pedido marcado como `Pagado` sin su pago.

## Seguridad

- **Todas** las operaciones exigen `Authorization: Bearer <JWT>`.
- **Aislamiento por dueño:** un usuario solo ve los pagos de **sus** pedidos
  (`pedidos.user_id == sub`). Tocar el pago de un pedido ajeno → **403**.
- El rol **Administrador** (`role_id = 1`) ve todos y es el único que puede
  **cambiar el estado de un pago** (aprobar, rechazar, reembolsar).
- El token se comprueba contra `jwt:revoked:<jti>` en Redis (503 si Redis cae).

| Código | Cuándo |
|---|---|
| 400 | Falta `pedido_id`, método o estado de pago no válidos, monto ≤ 0 |
| 401 | Token ausente, inválido, expirado o revocado |
| 403 | El pedido/pago pertenece a otro usuario |
| 404 | No existe el pago o el pedido |
| 409 | El pedido no admite pago en su estado actual, o el pago ya está en ese estado |
| 503 | Redis no permite comprobar la revocación |

## Endpoints

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/` | público | Información e hipermedia |
| GET | `/health` | público | Sonda: base, esquema, JWT, Redis |
| GET | `/pagos` | autenticado | Lista los pagos visibles (`pedido_id`, `estado`, `metodo`, `limit`, `offset`) |
| GET | `/pagos/<id>` | dueño o Administrador | Detalle del pago |
| GET | `/pedidos/<id>/pagos` | dueño o Administrador | Pagos de un pedido |
| POST | `/pagos` | autenticado | Registrar pago y marcar el pedido (201) |
| PATCH | `/pagos/<id>/estado` | **Administrador** | Cambiar estado del pago (aprobar / rechazar / reembolsar) |

Documentación interactiva en `/docs`.

### Cuerpo de `POST /pagos`

```jsonc
{
  "pedido_id": 7,                 // obligatorio
  "metodo": "Tarjeta",            // obligatorio: Tarjeta | Transferencia | Efectivo | PayPal
  "monto": 349.90,                // opcional: si se omite, se usa el total del pedido
  "estado": "Aprobado",           // opcional (default Aprobado): Pendiente | Aprobado | Rechazado
  "referencia": "AUTH-88213"      // opcional: folio o número de autorización
}
```

Catálogos: `METODOS_PAGO = (Tarjeta, Transferencia, Efectivo, PayPal)`,
`ESTADOS_PAGO = (Pendiente, Aprobado, Rechazado, Reembolsado)`.

## La transacción: cobrar y marcar el pedido

`POST /pagos` con `estado = "Aprobado"` hace, **en la misma transacción**:

1. Inserta la fila en `pagos`.
2. Si el pedido está en `Pendiente`, lo pasa primero a `Confirmado`.
3. Si desde ahí la transición a `Pagado` es legal, actualiza el pedido a `Pagado`.

Si algo falla, **no queda ni el pago ni el cambio de estado**. La respuesta incluye
`pedido_estado` y `pedido_actualizado_a` para que el cliente vea el efecto completo
de una sola llamada, sin tener que consultar el servicio de pedidos.

**Validaciones que evitan estados imposibles:**

- Un pedido en `Cancelado`, `Pagado`, `Enviado` o `Entregado` **no admite un pago
  nuevo** → 409 `ORDER_NOT_PAYABLE`.
- La transición se valida contra la **misma máquina de estados** que el servicio de
  pedidos (`TRANSICIONES_PEDIDO`, copiada aquí a propósito). Este servicio no puede
  saltarse las reglas que el otro aplica.

## Por qué no hay llamada HTTP entre servicios

`pagos` **no le pide nada por HTTP a `pedidos`**: lee y escribe la tabla `pedidos`
directamente, porque comparten base de datos. Eso permite envolver ambas escrituras
en **una sola transacción de PostgreSQL**, algo imposible si cada servicio tuviera
su propia base. La separación sigue siendo real —código, proceso, puerto y
responsabilidad distintos— pero el dato compartido se coordina con el motor de base
de datos, que es el lugar correcto para hacerlo.

El acoplamiento se mantiene honesto: la máquina de estados vive **duplicada** en
los dos servicios (mismo criterio que `redis_layer.py`), y un cambio de regla obliga
a tocar ambos. Es el precio de la atomicidad, y está anotado en el código.

## Redis: solo revocación, sin caché

Como en `pedidos`, aquí **no se cachea**: un pago es privado, sensible y cambia con
cada operación. Redis solo responde *«¿este `jti` está revocado?»*, y si no responde
el servicio devuelve **503** en vez de arriesgarse a aceptar un token revocado.

## Configuración y arranque

Ver `.env.example`: `DB_*`, `PORT=5005`, `JWT_SECRET` compartido, `ADMIN_ROLE_ID=1`,
`LOGIN_BASE_URL`, `CORS_ORIGINS` y `REDIS_URL`.

```bash
cp .env.example .env
pip install -r requirements.txt
../../scripts/servicios.sh start
```

Migración de esquema: `sql/01_migration_pagos.sql` (tabla `pagos`, con FK a
`pedidos`).

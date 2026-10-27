# Microservicio de Pedidos (`pedidos`)

**Puerto:** 5004 · **Ruta:** `apps/services/pedidos` · **Autor:** Fabián Azaed Orta Singlaterry (613504) · **UDEM SC-2236**

Crea y administra **pedidos, sus líneas, el stock y los estados**. Es el único
servicio que **mueve inventario**: cada alta o cancelación toca la columna
`books.stock`, y lo hace dentro de una transacción para que no exista un estado
intermedio observable.

## Seguridad

Aquí **no hay nada público salvo la sonda**. Un pedido es un documento privado:
pertenece a un usuario y contiene precios.

- **Todas** las operaciones exigen `Authorization: Bearer <JWT>` (HS256, del
  servicio de login).
- **Aislamiento por dueño:** un usuario normal solo ve y opera **sus** pedidos
  (`pedidos.user_id == sub`). Si toca el de otro → **403**.
- El rol **Administrador** (`role_id = 1`) ve y opera todos.
- El token se comprueba contra la lista de revocación `jwt:revoked:<jti>` en
  Redis. Si Redis no responde → **503** (fail-closed).
- Crear un pedido **a nombre de otro** (`user_id` en el cuerpo) solo lo permite el
  administrador; para un usuario normal ese campo se ignora.

| Código | Cuándo |
|---|---|
| 400 | Cuerpo inválido (falta `lineas`, cantidades ≤ 0, transición mal escrita) |
| 401 | Token ausente, inválido, expirado o revocado |
| 403 | Pedido de otro usuario |
| 404 | No existe el pedido, el libro o el usuario |
| 409 | Stock insuficiente o transición de estado no permitida |
| 503 | Redis no permite comprobar la revocación |

## Endpoints

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/` | público | Información e hipermedia |
| GET | `/health` | público | Sonda: base, esquema, JWT, Redis |
| GET | `/pedidos` | autenticado | Lista los pedidos visibles (`estado`, `user_id`, `limit`, `offset`) |
| GET | `/pedidos/<id>` | dueño o Administrador | Detalle con sus líneas |
| POST | `/pedidos` | autenticado | Crear con líneas y **descontar stock** (201) |
| POST | `/pedidos/<id>/lineas` | dueño o Administrador | Añadir libro o subir cantidad (solo si `Pendiente`) |
| DELETE | `/pedidos/<id>/lineas/<line_id>` | dueño o Administrador | Quitar línea y **devolver stock** (solo si `Pendiente`) |
| PATCH | `/pedidos/<id>/estado` | dueño o Administrador | Cambiar de estado (valida la transición) |
| DELETE | `/pedidos/<id>` | dueño o Administrador | **Cancelar** el pedido y devolver stock |

Documentación interactiva en `/docs`.

### Cuerpos de petición

```jsonc
// POST /pedidos
{
  "lineas": [ { "book_id": 3, "cantidad": 2 } ],   // obligatorio, ≥ 1 renglón
  "user_id": 12,        // opcional; SOLO el administrador puede usarlo
  "notas": "Entrega en biblioteca"
}

// PATCH /pedidos/<id>/estado
{ "estado": "Confirmado" }
```

## Máquina de estados

```
Pendiente ──▶ Confirmado ──▶ Pagado ──▶ Enviado ──▶ Entregado
     │              │           │
     └──────────────┴───────────┴──▶ Cancelado
```

- `Entregado` y `Cancelado` son **terminales**: no admiten más transiciones.
- Las líneas solo se pueden **añadir o quitar mientras el pedido está `Pendiente`**;
  una vez confirmado, el documento queda congelado (para eso existe el servicio de
  pagos).
- El estado se valida contra `TRANSICIONES`; un salto ilegal devuelve **409**
  `INVALID_TRANSITION`, no un 400 genérico.

## Reglas de negocio (lo que hace que esto no sea un CRUD)

**El stock se descuenta de forma condicional, no con un `SELECT` + `UPDATE`.**
Comprobar y escribir es una sola operación atómica:

```sql
UPDATE books SET stock = stock - %s
 WHERE id = %s AND stock >= %s        -- si el WHERE falla, rowcount = 0
```

Si `rowcount == 0`, no había existencias y se lanza `INSUFFICIENT_STOCK` (409)
incluyendo en la respuesta el **stock disponible** y lo **solicitado**. Un
`SELECT stock` seguido de un `UPDATE` tendría una condición de carrera entre dos
pedidos concurrentes; así no.

**El precio se congela en la línea** (`pedido_lineas.precio_unitario`). El pedido es
un documento histórico: si mañana sube el precio del libro, el pedido de ayer no
cambia. El total se recalcula en SQL con `NUMERIC`, nunca en Python con `float`.

**Cancelar devuelve stock, pero solo si el pedido no había salido de almacén.**
Se devuelve inventario si el pedido estaba en `Pendiente`, `Confirmado` o `Pagado`
(`ESTADOS_CON_STOCK_COMPROMETIDO`). Un pedido `Enviado` o `Entregado` ya no se
cancela.

**Todo o nada.** La cabecera del pedido, cada línea y cada descuento de stock viven
en la **misma transacción** (`with get_db_connection() as conn:`). Si el tercer
libro no tiene stock, el pedido entero se revierte: no queda un pedido a medias ni
stock descontado de más.

## Redis: solo revocación, sin caché

Este servicio **no cachea** sus respuestas, a propósito:

- Un pedido es **privado y muy volátil** (stock y estados cambian a cada
  operación). Un caché daría una ventana de datos obsoletos a cambio de casi nada.
- La única pregunta que este servicio le hace a Redis es *«¿este `jti` está
  revocado?»* — y esa respuesta **no se puede degradar**: si Redis cae, el servicio
  responde **503** en lugar de aceptar un token posiblemente revocado. Es el lado
  *fail-closed* de la política asimétrica.

## Configuración y arranque

Ver `.env.example`: `DB_*`, `PORT=5004`, `JWT_SECRET` compartido, `ADMIN_ROLE_ID=1`,
`CORS_ORIGINS` (lista explícita, nunca `*`) y `REDIS_URL`.

```bash
cp .env.example .env
pip install -r requirements.txt
../../scripts/servicios.sh start
```

Migración de esquema: `sql/01_migration_pedidos.sql` (tablas `pedidos` y
`pedido_lineas`, con `UNIQUE (pedido_id, book_id)` para que un mismo libro no se
duplique en un pedido).

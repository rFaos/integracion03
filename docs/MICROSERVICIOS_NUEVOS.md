# Microservicios nuevos: users, autores, pedidos y pagos

**Proyecto:** INTEGRACION03 — Microservicios de la librería en línea
**Autor:** Fabián Azaed Orta Singlaterry (Matrícula 613504)
**Curso:** SC-2236 — Universidad de Monterrey (UDEM)

---

## 1. Qué se agregó

| Servicio | Puerto | Ruta | Responsabilidad |
|---|---|---|---|
| **users** | 5002 | `apps/services/users` | Usuarios, roles, correos y contraseñas |
| **autores** | 5003 | `apps/services/autores` | Autores y su relación con libros |
| **pedidos** | 5004 | `apps/services/pedidos` | Pedidos, líneas de pedido, stock y estados |
| **pagos** | 5005 | `apps/services/pagos` | Registro de pagos y estado de los pedidos |

Los cuatro conviven con los dos que ya existían (login 5000, libros 5001) y se
levantan juntos con `scripts/servicios.sh`.

---

## 2. Lo compartido NO es el código: es el contrato

Cada servicio es un proceso independiente con su propio `app.py`, su propio
`.env` y su propio despliegue. Lo que comparten es exactamente tres cosas:

1. **La base de datos** `library` — sigue siendo la fuente de verdad única.
2. **El secreto JWT** (`JWT_SECRET`, por variable de entorno): con él cada
   servicio verifica la firma HMAC-SHA256 **sin llamar** al servicio de login.
3. **La instancia de Redis** (`REDIS_URL`): la lista de revocación compartida.

Por eso `jwt_auth.py` y `redis_layer.py` están **copiados** en cada servicio y no
importados de una librería común. Es una copia deliberada, con el mismo criterio
que ya usaba el servicio de libros: si mañana se cambia la implementación de
Redis, se cambia en un archivo y se copia; ningún servicio se rompe porque otro
cambie.

---

## 3. Autorización: por método y por ruta, nunca endpoint a endpoint

Los cuatro servicios comparten el mismo guardián en `before_request`. La política
depende de la naturaleza del dato:

| Servicio | `GET` (lectura) | Escritura (`POST`/`PUT`/`PATCH`/`DELETE`) |
|---|---|---|
| **users** | exige JWT; listar usuarios y roles exige **rol Administrador** | exige JWT + **rol Administrador** |
| **autores** | **público** (metadatos de catálogo) | exige JWT + **rol Administrador** |
| **pedidos** | exige JWT (un usuario solo ve **sus** pedidos) | exige JWT |
| **pagos** | exige JWT (un usuario solo ve los pagos de **sus** pedidos) | exige JWT |

Dos razones para decidir por método y por ruta en un solo lugar:

- **Protege por omisión.** Una ruta nueva queda protegida sin que nadie tenga que
  acordarse de añadirla. Si se olvida, el fallo es "deniega", no "expone".
- **Cubre los alias de una vez.** Igual que en el servicio de libros, la
  invalidación del caché y la autorización se deciden por método, así que añadir
  `/api/...` mañana no obliga a tocar el guardián.

Códigos: **401** para token ausente, inválido, expirado o revocado; **403** para
rol insuficiente; **503** si Redis no permite comprobar la revocación.

---

## 4. El JWT lleva `user_id` y `role_id`

El enunciado exige ambos. Hasta ahora el token solo llevaba `sub` (que es el
user_id) y `role` como **texto**. Se agregó:

- `apps/services/login/sql/04_migration_roles.sql` — crea el catálogo `roles`
  (1 = Administrador, 2 = Usuario) y enlaza `users.role_id`, con backfill desde
  el texto existente.
- `issue_access_token` en el servicio de login ahora incluye `role_id` en el
  payload.

Los servicios nuevos autorizan comparando **`role_id`**, no el texto del rol.
Así, renombrar un rol en la base no rompe la autorización de nadie.

---

## 5. Redis: la revocación se comprueba en los cuatro

Cada servicio consulta `jwt:revoked:<jti>` **antes de aceptar** un token. Es lo
que hace que un `/logout` en el servicio de login surta efecto inmediato en los
cuatro, sin esperar a que el JWT expire.

La política de fallo es la que exige el enunciado, y es **asimétrica**:

| Operación | Redis caído |
|---|---|
| Caché de lecturas (p. ej. `GET /autores`) | **fail-OPEN**: se va a PostgreSQL, la lectura sigue |
| Sesión, revocación, autorización | **fail-CLOSED**: se responde **503** |

`is_revoked()` **lanza** `RedisUnavailable` en vez de devolver `False`. Devolver
`False` sería un fallo abierto disfrazado: trataría *"no pude comprobar"* como
*"no está revocado"*, que es justo el agujero que la lista venía a cerrar.

---

## 6. Decisiones de diseño que vale la pena defender

### El stock se descuenta con un `UPDATE` condicional

```sql
UPDATE books SET stock = stock - %s WHERE id = %s AND stock >= %s
```

Si `rowcount` es 0, no había existencias y se aborta. **Comprobar con un `SELECT`
previo sería una condición de carrera**: dos pedidos simultáneos podrían leer
`stock = 1` y ambos venderlo. Aquí la comprobación y la escritura son la *misma*
operación atómica.

### El pago y el cambio de estado del pedido van en UNA transacción

El enunciado dice que el servicio de pagos "registra pagos y actualiza el estado
de los pedidos". La tentación es que llame por HTTP al servicio de pedidos. **No
se hace así**, y la razón es la atomicidad:

> Si se registrara el pago y después fallara la llamada al otro servicio, quedaría
> un cobro sin pedido pagado (o al revés), y nadie podría reconciliarlo sin
> intervención manual.

Como los dos servicios comparten la base `library`, ambas escrituras caben en una
transacción y PostgreSQL garantiza que ocurren juntas o no ocurren. El
desacoplamiento se mantiene donde importa —código, despliegue y contrato HTTP—;
lo compartido es la base de datos, que ya era el punto de verdad único.

### El precio se congela en la línea del pedido

`pedido_lineas.precio_unitario` guarda el precio del momento de la compra. Un
pedido es un documento histórico: si mañana el libro sube de precio, el pedido de
ayer debe seguir mostrando lo que costó ayer. Guardar solo el `book_id` y leer el
precio actual rompería el histórico.

### El total lo calcula PostgreSQL, no Python

`total` es `NUMERIC(10,2)` y la suma se hace en la base (`SUM(cantidad *
precio_unitario)`). Sumar en Python con flotantes introduciría errores de
redondeo en el dinero.

### Los estados son una máquina cerrada

```
Pendiente -> Confirmado -> Pagado -> Enviado -> Entregado
     \___________/___________/
              Cancelado
```

No se puede pasar de `Pendiente` a `Entregado` sin confirmar y pagar. Las
transiciones válidas están en `TRANSICIONES` y se validan antes de escribir; el
servicio de pagos **reutiliza la misma tabla**, así que no puede saltarse las
reglas que valida el de pedidos. Cancelar devuelve el stock, y solo se permite
mientras el pedido no se haya enviado.

---

## 7. CORS: se acabó el `*`

Los servicios nuevos leen los orígenes permitidos de `CORS_ORIGINS` (variable de
entorno) y por defecto **no** usan comodín:

```
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://34.51.29.27:3000
```

El cliente de escritorio Tk no envía `Origin`, así que CORS no le afecta; esto
protege a los clientes de navegador (monolito y Electron). **Nota:** los servicios
de login y libros todavía tienen `origins: "*"` y deberían alinearse con esta
misma variable.

---

## 8. Cómo se levantan y cómo se prueban

```bash
# 1. Migraciones (en orden; 04 y pedidos antes que pagos)
PGPASSWORD=666 psql -h localhost -U library_user -d library -f apps/services/login/sql/04_migration_roles.sql
PGPASSWORD=666 psql -h localhost -U library_user -d library -f apps/services/pedidos/sql/01_migration_pedidos.sql
PGPASSWORD=666 psql -h localhost -U library_user -d library -f apps/services/pagos/sql/01_migration_pagos.sql

# 2. Dependencias (redis es nueva)
pip install -r apps/services/users/requirements.txt   # (igual en los otros tres)

# 3. Los seis servicios a la vez
./scripts/servicios.sh start
./scripts/servicios.sh status

# 4. Prueba de integración completa (58 comprobaciones)
python tests/e2e_microservicios.py
```

La prueba de integración **no fabrica tokens**: inicia sesión de verdad contra
`POST /login` (resolviendo su CAPTCHA) y usa ese token contra los cuatro
servicios. Después revoca el token con `/logout` y comprueba que **los cuatro**
lo rechazan con `TOKEN_REVOKED`.

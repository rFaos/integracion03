-- ============================================================================
-- 01_migration_pedidos.sql
-- ============================================================================
-- PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
-- AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
-- UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
--
-- QUE HACE
-- --------
-- Crea las dos tablas del microservicio de pedidos:
--
--   pedidos        -> cabecera (quien compra, en que estado, cuanto total)
--   pedido_lineas  -> renglones (que libro, cuantas piezas, a que precio)
--
-- DECISIONES DE DISENO
-- --------------------
-- 1. `precio_unitario` se COPIA en la linea en vez de leerse de `books.price`.
--    Un pedido es un documento historico: si manana el libro sube de precio, el
--    pedido de ayer debe seguir mostrando lo que costo ayer. Guardar solo el
--    book_id y leer el precio actual romperia el historico.
--
-- 2. El STOCK vive en `books.stock` (ya existia) y NO se duplica aqui. El
--    servicio de pedidos lo descuenta dentro de la misma transaccion que crea
--    el pedido; para evitar sobreventa usa `UPDATE ... WHERE stock >= cantidad`
--    y comprueba las filas afectadas.
--
-- 3. `estado` es una maquina de estados cerrada por CHECK. Los estados validos
--    estan en el enunciado: se crea, se confirma, se paga, se envia, se
--    entrega... o se cancela.
--
-- Es IDEMPOTENTE. Aplicar con:
--   PGPASSWORD=666 psql -h localhost -U library_user -d library \
--       -f apps/services/pedidos/sql/01_migration_pedidos.sql
-- ============================================================================

BEGIN;

-- --- Cabecera del pedido ----------------------------------------------------
CREATE TABLE IF NOT EXISTS pedidos (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    estado     VARCHAR(20) NOT NULL DEFAULT 'Pendiente'
               CHECK (estado IN ('Pendiente', 'Confirmado', 'Pagado',
                                 'Enviado', 'Entregado', 'Cancelado')),
    total      NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    notas      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ
);

-- --- Renglones del pedido ---------------------------------------------------
CREATE TABLE IF NOT EXISTS pedido_lineas (
    id              SERIAL PRIMARY KEY,
    pedido_id       INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    book_id         INTEGER NOT NULL REFERENCES books(id),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    -- Precio congelado al momento de la compra (ver decision 1).
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    -- Un libro no puede repetirse en el mismo pedido: si se quiere mas, se sube
    -- la cantidad. Asi el total se calcula sin ambiguedad.
    UNIQUE (pedido_id, book_id)
);

CREATE INDEX IF NOT EXISTS idx_pedidos_user    ON pedidos (user_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado  ON pedidos (estado);
CREATE INDEX IF NOT EXISTS idx_lineas_pedido   ON pedido_lineas (pedido_id);
CREATE INDEX IF NOT EXISTS idx_lineas_book     ON pedido_lineas (book_id);

COMMIT;

-- ---------------------------------------------------------------------------
-- Comprobacion rapida:
--   SELECT id, user_id, estado, total FROM pedidos ORDER BY id DESC LIMIT 5;
-- ---------------------------------------------------------------------------

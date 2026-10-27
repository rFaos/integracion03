-- ============================================================================
-- 01_migration_pagos.sql
-- ============================================================================
-- PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
-- AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
-- UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
--
-- QUE HACE
-- --------
-- Crea la tabla `pagos`. Depende de que exista `pedidos`, asi que esta
-- migracion se aplica DESPUES de 01_migration_pedidos.sql.
--
-- DECISIONES DE DISENO
-- --------------------
-- 1. Un pedido puede tener VARIOS pagos (un intento rechazado y luego uno
--    aprobado, o un pago dividido). Por eso no hay UNIQUE sobre pedido_id:
--    el historial completo de intentos es informacion util.
--
-- 2. `monto` se guarda por separado del total del pedido a proposito. Asi se
--    puede detectar y registrar un pago parcial, y queda la evidencia de que
--    se cobro exactamente esa cantidad.
--
-- 3. El servicio de pagos NO toca `pedidos.estado` por HTTP hacia el servicio de
--    pedidos: lo actualiza en la MISMA transaccion. La razon es la atomicidad:
--    registrar el pago y marcar el pedido como pagado deben ocurrir juntos o no
--    ocurrir. Un salto de red entre dos servicios no puede garantizar eso.
--
-- Es IDEMPOTENTE. Aplicar con:
--   PGPASSWORD=666 psql -h localhost -U library_user -d library \
--       -f apps/services/pagos/sql/01_migration_pagos.sql
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS pagos (
    id         SERIAL PRIMARY KEY,
    pedido_id  INTEGER NOT NULL REFERENCES pedidos(id),
    monto      NUMERIC(10, 2) NOT NULL CHECK (monto > 0),
    metodo     VARCHAR(20) NOT NULL
               CHECK (metodo IN ('Tarjeta', 'Transferencia', 'Efectivo', 'PayPal')),
    estado     VARCHAR(20) NOT NULL DEFAULT 'Aprobado'
               CHECK (estado IN ('Pendiente', 'Aprobado', 'Rechazado', 'Reembolsado')),
    referencia VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pagos_pedido ON pagos (pedido_id);
CREATE INDEX IF NOT EXISTS idx_pagos_estado ON pagos (estado);

COMMIT;

-- ---------------------------------------------------------------------------
-- Comprobacion rapida:
--   SELECT id, pedido_id, monto, metodo, estado FROM pagos ORDER BY id DESC LIMIT 5;
-- ---------------------------------------------------------------------------

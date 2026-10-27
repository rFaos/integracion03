-- ============================================================================
-- 04_migration_roles.sql
-- ============================================================================
-- PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
-- AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
-- UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
--
-- QUE HACE
-- --------
-- Crea la tabla `roles` y enlaza `users.role_id` con ella.
--
-- POR QUE HACE FALTA (es un requisito, no una mejora)
-- ---------------------------------------------------
-- El enunciado pide que el JWT incluya `user_id` **y `role_id`**. Hasta ahora
-- `users.role` era un texto suelto ('Administrador' / 'Usuario') sin catalogo
-- detras, asi que no habia ningun `role_id` que poner en el token.
--
-- Se conserva la columna `role` (texto) por compatibilidad: el monolito y el
-- resto de servicios ya la usan. `role_id` es la referencia normalizada.
--
-- Es IDEMPOTENTE: se puede correr varias veces sin romper nada.
-- Aplicar con:
--   PGPASSWORD=666 psql -h localhost -U library_user -d library \
--       -f apps/services/login/sql/04_migration_roles.sql
-- ============================================================================

BEGIN;

-- --- 1. Catalogo de roles ---------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(30) UNIQUE NOT NULL,
    description TEXT
);

INSERT INTO roles (id, name, description) VALUES
    (1, 'Administrador', 'Acceso total: puede crear, modificar y borrar en todos los microservicios.'),
    (2, 'Usuario',       'Acceso de consulta y a sus propios pedidos y pagos.')
ON CONFLICT (name) DO NOTHING;

-- Los ids se insertaron a mano, asi que hay que reajustar la secuencia para que
-- el siguiente INSERT sin id explicito no choque con la PK.
SELECT setval(pg_get_serial_sequence('roles', 'id'),
              COALESCE((SELECT MAX(id) FROM roles), 1));

-- --- 2. Enlace en users -----------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(id);

-- Backfill: se traduce el texto existente al id del catalogo.
UPDATE users u
   SET role_id = r.id
  FROM roles r
 WHERE r.name = u.role
   AND u.role_id IS NULL;

-- Cualquier usuario con un rol de texto fuera del catalogo cae a 'Usuario'.
UPDATE users
   SET role_id = (SELECT id FROM roles WHERE name = 'Usuario')
 WHERE role_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_users_role_id ON users (role_id);

COMMIT;

-- ---------------------------------------------------------------------------
-- Comprobacion rapida (debe devolver 0 filas):
--   SELECT id, email, role, role_id FROM users WHERE role_id IS NULL;
-- ---------------------------------------------------------------------------

-- ==============================================================================
-- PROYECTO: INTEGRACION03 - AUTENTICACIÓN Y GESTIÓN DE USUARIOS
-- SCRIPT: 01_migration_auth.sql
-- BASE DE DATOS: library
-- AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
-- ==============================================================================

BEGIN;

-- 1. Atributos de identidad del usuario ---------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS nombre           VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS apellido_paterno VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS apellido_materno VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS email            VARCHAR(150);
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active        BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login       TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts  INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until     TIMESTAMPTZ;

-- 2. Los nuevos usuarios se identifican por email, no por username ------------
ALTER TABLE users ALTER COLUMN username DROP NOT NULL;
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'Usuario';

-- 3. Backfill de los 11 usuarios sembrados en library_data.sql ---------------
--    (admin + usuario1..usuario10) para que puedan iniciar sesión por email.
--    Se usa COALESCE por si algún usuario ya no tuviera username: si no, la
--    concatenación daría NULL y el correo quedaría vacío.
UPDATE users
   SET email = COALESCE(username, 'usuario' || id) || '@library.local'
 WHERE email IS NULL;

-- 4. Unicidad de email insensible a mayúsculas --------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users (LOWER(email));

-- 5. Almacén server-side de sesiones (el servicio NO usa cookies) -------------
CREATE TABLE IF NOT EXISTS user_sessions (
    id           BIGSERIAL   PRIMARY KEY,
    token_hash   CHAR(64)    NOT NULL UNIQUE,
    user_id      INT         NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at   TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at   TIMESTAMPTZ,
    ip_origen    VARCHAR(45),
    user_agent   VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user    ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

COMMIT;

-- ==============================================================================
-- NOTA: password_hash permanece en la tabla users.
-- No se crea una tabla exclusiva de contraseñas ni se almacena dos veces.
-- ==============================================================================

-- ============================================================================
-- 03_migration_jwt.sql
-- Soporte de JWT (RFC 7519) para el microservicio de autenticacion
-- ----------------------------------------------------------------------------
-- PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
-- AUTOR:    Fabian Azaed Orta Singlaterry (613504) - UDEM SC-2236
-- BASE:     library (PostgreSQL)
-- ============================================================================
-- CAMBIO DE MODELO
-- ---------------
-- Antes (prompt 05): `user_sessions` guardaba el SHA-256 del token OPACO de
--   sesion. Cada peticion costaba un SELECT y el token no decia nada por si
--   mismo: solo el servicio de login podia interpretarlo.
--
-- Ahora (nuevo requerimiento): el cliente recibe dos credenciales distintas:
--
--   1) ACCESS TOKEN  -> JWT firmado (HS256). Es AUTOCONTENIDO y SIN ESTADO:
--      cualquier microservicio que comparta el secreto puede validarlo sin
--      consultar la base de datos. Vive poco (15 min por omision).
--
--   2) REFRESH TOKEN -> token OPACO aleatorio, guardado en `user_sessions`
--      UNICAMENTE como SHA-256. Vive mas (7 dias) y su unico trabajo es
--      emitir access tokens nuevos. SI debe ser revocable, y por eso si vive
--      en la base de datos.
--
-- La tabla `user_sessions` se conserva (no se rompe nada de lo anterior) y
-- pasa a ser el registro del refresh token / sesion renovable.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Identificador del access token emitido (trazabilidad y auditoria)
-- ----------------------------------------------------------------------------
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS jti UUID;

-- Que tipo de credencial representa la fila ('refresh' es el valor nuevo).
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS token_type VARCHAR(20) NOT NULL DEFAULT 'refresh';

-- ----------------------------------------------------------------------------
-- 2. Rotacion de refresh tokens
-- ----------------------------------------------------------------------------
-- En cada POST /refresh el refresh token anterior se marca como rotado y se
-- enlaza con el que lo reemplaza. Si alguien reutiliza un token ya rotado se
-- detecta el robo (deteccion de reuso) y se revocan todas las sesiones del
-- usuario. Ese enlace es el que hace posible la deteccion.
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS rotated_at      TIMESTAMPTZ;
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS replaced_by_hash CHAR(64);

CREATE INDEX IF NOT EXISTS idx_sessions_jti     ON user_sessions(jti);
CREATE INDEX IF NOT EXISTS idx_sessions_revoked ON user_sessions(revoked_at);

-- ----------------------------------------------------------------------------
-- 3. Vista de apoyo para la evidencia
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_active_sessions AS
SELECT s.id,
       u.id    AS user_id,
       u.email,
       u.role,
       s.jti,
       s.token_type,
       s.created_at,
       s.expires_at,
       s.last_seen_at,
       s.rotated_at,
       s.revoked_at,
       s.ip_origen
  FROM user_sessions s
  JOIN users u ON u.id = s.user_id;

-- ============================================================================
-- Verificacion rapida despues de aplicar la migracion:
--   SELECT column_name, data_type FROM information_schema.columns
--    WHERE table_name = 'user_sessions' ORDER BY ordinal_position;
--
--   SELECT id, email, token_type, jti, expires_at, revoked_at
--     FROM v_active_sessions WHERE revoked_at IS NULL
--    ORDER BY created_at DESC LIMIT 10;
-- ============================================================================

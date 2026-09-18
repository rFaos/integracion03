-- ==============================================================================
-- PROYECTO: INTEGRACION03 - AUTENTICACIÓN Y GESTIÓN DE USUARIOS
-- SCRIPT: 02_fix_seed_passwords.sql
-- BASE DE DATOS: library
-- AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
-- ==============================================================================
-- CORRECCIÓN DE DATOS SEMILLA
--
-- El hash declarado en data/library_data.sql como bcrypt de '666':
--
--   $2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea
--
-- NO corresponde a '666' ni a ninguna contraseña común: es un placeholder
-- inválido. Se comprobó con bcrypt.checkpw() contra '666', '123456',
-- 'password', 'admin', 'usuario1', 'Admin123!' y 'library' -> todas False.
--
-- Consecuencia: los 11 usuarios sembrados (admin + usuario1..usuario10) NO
-- podían autenticarse en ningún servicio del proyecto, ni en este microservicio
-- ni en el monolito Node/Express, que también usa bcrypt.
--
-- Este script reemplaza el placeholder por un hash bcrypt VERIFICADO de '666'.
-- El valor correcto ya quedó también corregido en data/library_data.sql para
-- que una carga nueva de la base de datos no reproduzca el problema.
--
-- Ejecutar SOLO si la base de datos ya tenía cargados los datos semilla:
--   psql -U library_user -d library -f sql/02_fix_seed_passwords.sql
-- ==============================================================================

BEGIN;

UPDATE users
   SET password_hash = '$2b$10$7rs4lCRN9rI54x6zxQg6ieIVBGyIgIFV5kkRSiwycjQFuIdJKXle6'
 WHERE password_hash = '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea';

COMMIT;

-- ==============================================================================
-- VERIFICACIÓN: debe listar los 11 usuarios con su correo ya backfilleado.
-- Todos deben poder iniciar sesión con la contraseña '666'.
-- ==============================================================================
SELECT id, username, email, role, is_active
  FROM users
 ORDER BY id;

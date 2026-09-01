# PROMPT 01: Aplicación Web Monolítica Server-Side
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Institución:** Universidad de Monterrey (UDEM)  
**Semestre:** Primavera 2026  

---

## 1. Objetivo del Prompt
Construir una aplicación web monolítica basada en **Node.js, Express, EJS y PostgreSQL** para la consulta y administración integral del catálogo de la librería.

---

## 2. Restricciones Arquitectónicas Obligatorias

1. **Renderizado en Servidor (SSR):** Vistas HTML generadas exclusivamente en el servidor con plantillas EJS.
2. **Cero JSON / Cero APIs REST en Frontend:** Todos los formularios envían `application/x-www-form-urlencoded` o `multipart/form-data`, y el servidor responde con vistas HTML completas o redirecciones 302.
3. **Acceso Seguro a PostgreSQL:** Consultas SQL 100% parametrizadas (`$1, $2...`) mediante el driver nativo `pg` (Pool de conexiones).
4. **Montaje bajo `/library`:** Operar bajo el prefijo `/library` para compatibilidad directa con Reverse Proxy en Apache o NGINX.
5. **Autenticación y Autorización por Rol:** Control de sesiones con cookies `httpOnly`, contraseñas en hash `bcrypt` y protección de rutas administrativas `/library/admin/*`.
6. **Gestión de Imágenes:** Subida segura con Multer, validación de tipos MIME y nombres sanitizados guardados en `uploads/`.

---

## 3. Entregables Esperados
- Código fuente en `apps/web-monolito01/`:
  - `package.json`, `.env.example`, `app.js`
  - `config/db.js`
  - `routes/library.js`
  - `middleware/auth.js`
  - `views/` (login, index, detail, admin_book_form, admin_catalog, error, layout)
  - `public/styles.css`
  - `uploads/`

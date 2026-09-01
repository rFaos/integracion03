# Documento de Especificación de Requisitos de Software (SRS)
## Aplicación Web Monolítica para Gestión de Librería
**Curso:** Integración de Aplicaciones Computacionales (SC-2236-02)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  
**Fecha:** Agosto 2026  

---

## 1. Introducción y Alcance
El presente proyecto tiene como objetivo diseñar, desarrollar y validar una **Aplicación Web Monolítica Server-Side** construida sobre Node.js, Express, EJS y PostgreSQL. La aplicación está concebida para la gestión integral de un catálogo bibliográfico universitario especializado en Ciencias de la Computación y Cloud Computing, permitiendo asociar de manera normalizada (4FN) conceptos técnicos contextualizados por libro, múltiples autores, géneros e imágenes.

---

## 2. Actores del Sistema y Matriz de Permisos

| Actor | Descripción | Permisos Clave | Restricciones |
| :--- | :--- | :--- | :--- |
| **Visitante** | Usuario anónimo sin sesión activa. | Visualizar pantalla de inicio de sesión y formulario de registro. | No puede ver el catálogo, ni libros, ni conceptos, ni realizar operaciones de modificación. |
| **Usuario Registrado** | Alumno o docente autenticado en el sistema. | Iniciar/cerrar sesión, consultar catálogo general, buscar por título/ISBN, filtrar por categorías/formatos/géneros, y ver el detalle completo de libros con sus conceptos. | No puede acceder a rutas `/admin/*`, ni crear/editar/eliminar registros ni subir imágenes. |
| **Administrador** | Administrador único del sistema (rol protegido en base de datos). | Acceso total: CRUD completo de Libros, Autores, Géneros, Formatos, Categorías, Conceptos globales, asociación de conceptos específicos y gestión de imágenes con portada. | Sujeto a la restricción de que solo puede existir **uno** en todo el sistema. |

---

## 3. Requisitos Funcionales (RF)

- **RF-01: Autenticación de Usuarios:** El sistema debe permitir el inicio de sesión validando credenciales contra la base de datos mediante contraseñas cifradas con `bcrypt`.
- **RF-02: Registro de Usuarios Regulares:** Cualquier visitante puede registrar una cuenta nueva, la cual se creará forzosamente con rol `'Usuario'`.
- **RF-03: Cierre de Sesión:** Destrucción segura de la sesión HTTP en servidor y limpieza de la cookie de sesión en el cliente.
- **RF-04: Catálogo General de Libros:** Vista principal que renderiza tarjetas de libros mostrando portada, título, autores, formato, categoría, precio y estado de existencias (stock).
- **RF-05: Búsqueda y Filtrado Server-Side:** Motor de búsqueda por coincidencia parcial insensible a mayúsculas/minúsculas en título e ISBN, combinado con filtros por Categoría, Formato y Género mediante parámetros `GET`.
- **RF-06: Vista Detallada de Libro:** Presentación exhaustiva de los metadatos del libro, galería de imágenes en miniatura, biografías de autores vinculados, géneros y tabla de conceptos contextuales.
- **RF-07: Gestión de Conceptos 4FN:** Capacidad de registrar definiciones contextuales asociadas a un libro específico (con referencia a capítulo/página) sobre conceptos del catálogo global (e.g. IaaS, PaaS, SaaS, Serverless).
- **RF-08: CRUD de Libros (Admin):** Formulario para crear, modificar y dar de baja libros, gestionando relaciones multivaluadas con autores y géneros mediante transacciones SQL atómicas.
- **RF-09: CRUD de Catálogos Auxiliares (Admin):** Panel unificado para administrar Autores, Géneros, Formatos, Categorías y Conceptos Canónicos.
- **RF-10: Carga y Gestión de Imágenes (Admin):** Carga segura mediante `multipart/form-data` con Multer, guardado en disco con nombre sanitizado/aleatorio, y capacidad de fijar una imagen como portada principal.

---

## 4. Requisitos No Funcionales (RNF)

- **RNF-01: Arquitectura Monolítica Server-Side:** Todas las vistas HTML deben ser renderizadas en el servidor mediante el motor de plantillas EJS. Se prohíbe el uso de APIs REST, GraphQL o SPA.
- **RNF-02: Prohibición de Intercambio de Datos JSON:** Las transferencias de datos cliente-servidor se realizan exclusivamente mediante `application/x-www-form-urlencoded` o `multipart/form-data`, y las respuestas son documentos HTML o redirecciones HTTP 302.
- **RNF-03: Acceso Directo y Seguro a PostgreSQL:** Utilizar el controlador oficial `pg` mediante Pool de conexiones y **100% de consultas SQL parametrizadas** (`$1, $2...`) para neutralizar vectores de ataque por SQL Injection.
- **RNF-04: Restricción Estricta de Administrador Único:** La regla de negocio de máximo un administrador debe estar forzada tanto en la capa de aplicación como en el motor relacional mediante un índice único parcial:  
  `CREATE UNIQUE INDEX idx_single_admin ON users (role) WHERE role = 'Administrador';`
- **RNF-05: Operabilidad tras Reverse Proxy:** La aplicación debe estar montada bajo el prefijo de ruta base `/library` para coexistir con servidores web Apache / NGINX en despliegues institucionales.
- **RNF-06: Sanitización y Control de Archivos:** Las imágenes subidas deben restringirse a tipos MIME `image/jpeg`, `image/png`, `image/webp` con un tamaño máximo de 5MB y nombres generados en servidor para impedir ataques de Path Traversal.
- **RNF-07: Manejo Seguro de Errores:** Las respuestas de error (404, 403, 500) deben renderizar vistas amigables sin exponer trazas de pila (stack traces), consultas SQL internas ni rutas del servidor.
- **RNF-08: Normalización en Cuarta Forma Normal (4FN):** Eliminación total de dependencias multivaluadas en tablas puente independientes (`book_authors`, `book_genres`, `book_images`, `book_concepts`).

---

## 5. Criterios de Aceptación

1. El sistema inicia sin errores en `http://127.0.0.1:3000/library`.
2. Las rutas no autenticadas redirigen inmediatamente al formulario de login.
3. El intento de insertar un segundo usuario con rol `Administrador` falla a nivel de base de datos con un error de violación de índice único.
4. Las búsquedas complejas con caracteres especiales (e.g. `' OR '1'='1`) se ejecutan como literales sin provocar SQL Injection ni errores de sintaxis.
5. Las páginas EJS son responsivas en resoluciones móviles (360px) y de escritorio (1200px+).

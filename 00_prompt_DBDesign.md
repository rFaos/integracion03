# PROMPT 00: Diseño y Normalización de Base de Datos Relacional (4FN)
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Institución:** Universidad de Monterrey (UDEM)  
**Semestre:** Primavera 2026  

---

## 1. Objetivo del Prompt
Diseñar, normalizar y validar una base de datos relacional para la gestión de un catálogo bibliográfico universitario en **PostgreSQL**, garantizando el cumplimiento de la **Cuarta Forma Normal (4FN)**, integridad referencial estricta, consultas parametrizadas y la regla de negocio de **máximo un único Administrador**.

---

## 2. Requisitos y Dependencias Identificadas

1. **Entidad Central Libros:**
   - Atributos: ISBN (único), título, año de publicación, precio unitario, stock en almacén, clave foránea de formato (`format_id`) y clave foránea de categoría (`category_id`).
2. **Dependencias Multivaluadas Independientes (4FN):**
   - Un libro puede tener múltiples autores y un autor múltiples libros ($Libro \twoheadrightarrow Autor$).
   - Un libro puede pertenecer a múltiples géneros y un género a múltiples libros ($Libro \twoheadrightarrow Género$).
   - Un libro puede contener múltiples imágenes y una imagen pertenece a un libro ($Libro \twoheadrightarrow Imagen$).
   - Un libro define múltiples conceptos técnicos (ej. IaaS, PaaS, SaaS, Serverless) con definiciones y ubicaciones contextuales por libro ($Libro \twoheadrightarrow Concepto$).
3. **Catálogos Independientes (1FN, 2FN, 3FN):**
   - Formatos (`formats`): Físico Tapa Dura, Digital PDF, EPUB, etc.
   - Categorías (`categories`): Cloud Computing, Sistemas Distribuidos, etc.
   - Géneros (`genres`): Manual Técnico, Arquitectura, etc.
   - Autores (`authors`): Nombre, biografía, país.
   - Conceptos (`concepts`): Nombre canónico, resumen general.
4. **Regla de Negocio Crítica:**
   - Máximo un único usuario con rol `'Administrador'` protegido a nivel de motor relacional mediante un índice parcial único:
     ```sql
     CREATE UNIQUE INDEX idx_single_admin ON users (role) WHERE role = 'Administrador';
     ```

---

## 3. Entregables Esperados
- `data/db_design.md`: Documento metodológico de normalización y diccionario de datos.
- `data/db_schema.sql`: Script DDL con tablas, claves primarias compuestas, claves foráneas (`ON DELETE CASCADE / RESTRICT`), checks e índices.
- `data/library_data.sql`: Script DML con datos sintéticos (mínimo 30 registros por entidad) y usuario administrador con hash bcrypt.

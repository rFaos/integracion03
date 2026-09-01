# Diseño Relacional y Normalización de Base de Datos (4FN)
## Catálogo Bibliográfico Universitario - "INTEGRACION03"
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  

---

## 1. Justificación de la Normalización hasta 4FN

El modelo de datos fue diseñado siguiendo rigurosamente las reglas formales de normalización de bases de datos para garantizar consistencia lógica, integridad referencial y eliminar anomalías de inserción, actualización y borrado.

### Proceso de Normalización:
1. **Primera Forma Normal (1FN):**
   - Todos los atributos contienen valores atómicos indivisibles.
   - Se eliminan atributos multivaluados o listas de valores (ej. listas de autores o géneros separados por comas).
   - Se establece una clave primaria explícita en cada tabla.
2. **Segunda Forma Normal (2FN):**
   - Cumple 1FN.
   - Todos los atributos no primos dependen funcionalmente de la totalidad de la clave primaria, eliminando dependencias parciales en tablas con claves compuestas.
3. **Tercera Forma Normal (3FN / BCNF):**
   - Cumple 2FN.
   - Se eliminan dependencias transitivas: atributos no clave que dependían de otros atributos no clave (ej. formatos y categorías) se extraen a catálogos independientes con claves foráneas.
4. **Cuarta Forma Normal (4FN):**
   - Cumple 3FN/BCNF.
   - Se aíslan las dependencias multivaluadas no triviales e independientes ($X \twoheadrightarrow Y$).
   - Dado que un libro puede tener múltiples autores ($Libro \twoheadrightarrow Autor$), múltiples géneros ($Libro \twoheadrightarrow Género$), múltiples imágenes ($Libro \twoheadrightarrow Imagen$) y múltiples conceptos contextuales ($Libro \twoheadrightarrow Concepto$), y estas relaciones son mutuamente independientes, se modelan en 4 tablas puente separadas (`book_authors`, `book_genres`, `book_images`, `book_concepts`). De almacenarse juntas en una sola estructura, se generaría una explosión combinatoria (producto cartesiano) de registros redundantes.

---

## 2. Diccionario de Datos y Estructura Relacional

### 2.1 Tablas de Catálogo
- **`formats`**: Formatos físicos y digitales (`id`, `name`, `description`).
- **`categories`**: Categorías temáticas principales (`id`, `name`, `description`).
- **`genres`**: Géneros literarios/técnicos (`id`, `name`).
- **`authors`**: Autores de obras (`id`, `name`, `biography`, `country`).
- **`concepts`**: Glosario canónico de conceptos computacionales (`id`, `name`, `general_summary`).

### 2.2 Entidad Central y Usuarios
- **`books`**: Registro central de libros (`id`, `isbn` UNIQUE, `title`, `publication_year`, `price`, `stock`, `format_id` FK, `category_id` FK, `created_at`).
- **`users`**: Control de acceso y roles (`id`, `username` UNIQUE, `password_hash`, `role` CHECK IN ('Administrador', 'Usuario'), `created_at`).

### 2.3 Tablas de Relación 4FN
- **`book_authors`**: Relación N:M entre libros y autores (`book_id` FK, `author_id` FK, PK compuesta).
- **`book_genres`**: Relación N:M entre libros y géneros (`book_id` FK, `genre_id` FK, PK compuesta).
- **`book_images`**: Galería de imágenes 1:N (`id` PK, `book_id` FK, `image_url`, `alt_text`, `is_cover` BOOL).
- **`book_concepts`**: Relación N:M con atributos propios (`book_id` FK, `concept_id` FK, `definition` TEXT, `chapter_page` VARCHAR, PK compuesta).

---

## 3. Regla de Negocio: Administrador Único
La regla de negocio que prohíbe la existencia de más de un Administrador se implementa a nivel del motor de base de datos mediante un índice único condicional (parcial):
```sql
CREATE UNIQUE INDEX idx_single_admin ON users (role) WHERE role = 'Administrador';
```
Esto garantiza atomicidad e integridad absoluta contra condiciones de carrera concurrentes sin penalizar las inserciones de usuarios con rol `'Usuario'`.

# Registro de Decisiones de Ingeniería de Software (ADR)
## Proyecto: Aplicación Web Monolítica de Librería
**Curso:** Integración de Aplicaciones Computacionales (SC-2236-02)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  

---

### Esquema de Razonamiento Aplicado
Para cada decisión se aplicó el ciclo formal de ingeniería:
$$\text{Problema} \longrightarrow \text{Alternativas} \longrightarrow \text{Decisión} \longrightarrow \text{Justificación} \longrightarrow \text{Riesgos} \longrightarrow \text{Validación}$$

---

## Decisión 1: Macro-Arquitectura Monolítica Server-Side vs. Arquitectura Desacoplada (SPA + API REST)

- **Necesidad / Problema:** Diseñar una plataforma web integral para gestión bibliográfica e inventario con consistencia de datos estricta, alta cohesión y bajo costo operacional.
- **Alternativas Consideradas:**
  1. *Arquitectura Desacoplada:* Frontend en React/Vue consumiendo una API REST/GraphQL en Express con intercambio en JSON.
  2. *Arquitectura de Microservicios:* Módulos separados para Catálogo, Autenticación e Imágenes en contenedores independientes.
  3. *Arquitectura Monolítica Server-Side:* Aplicación única en Node.js/Express con renderizado HTML en servidor mediante EJS.
- **Decisión Tomada:** Adoptar la **Arquitectura Monolítica Server-Side**.
- **Justificación Técnica:**
  - Elimina la sobrecarga de sincronización de estado cliente-servidor y serialización/deserialización JSON.
  - Mayor seguridad inicial: la lógica de negocio, las sesiones y el acceso a base de datos residen en un único entorno de confianza.
  - Facilidad de despliegue y mantenimiento: una sola unidad ejecutable simplifica el ciclo de vida y la observabilidad en servidores Apache/NGINX.
- **Riesgos y Limitaciones:** Acoplamiento del ciclo de despliegue (cualquier cambio requiere reiniciar el proceso global) y mayor consumo de CPU en el servidor al generar HTML bajo alta concurrencia.
- **Evidencia de Validación:** Flujo HTTP estándar verificado con envío de formularios `application/x-www-form-urlencoded` y respuestas HTML completas sin peticiones asíncronas de fondo.

---

## Decisión 2: Acceso a Datos Directo con `pg` vs. Mapeador Objeto-Relacional (ORM)

- **Necesidad / Problema:** Conectar la aplicación Node.js a PostgreSQL garantizando máxima eficiencia, control granular del SQL y protección contra inyecciones SQL.
- **Alternativas Consideradas:**
  1. *ORM Pesado (Prisma / Sequelize / TypeORM):* Abstracción de modelos y generación automática de consultas.
  2. *Query Builder (Knex.js):* Constructor programático de SQL.
  3. *Driver Nativo `pg` (node-postgres) con Consultas Parametrizadas:* Control directo de sentencias SQL y pool de conexiones.
- **Decisión Tomada:** Utilizar el **Driver Nativo `pg` con Consultas SQL Parametrizadas y Pool**.
- **Justificación Técnica:**
  - Transparencia total del SQL ejecutado, permitiendo optimizar planes de ejecución (`EXPLAIN ANALYZE`), transacciones (`BEGIN/COMMIT/ROLLBACK`) e índices compuestos.
  - Desempeño superior al eliminar capas de abstracción e instanciación de objetos del ORM.
  - Las consultas parametrizadas (`$1, $2...`) separan el árbol sintáctico de los datos ingresados por el usuario, imposibilitando ataques de SQL Injection.
- **Riesgos y Limitaciones:** Requiere escritura manual de sentencias SQL y mapeo explícito de campos en código.
- **Evidencia de Validación:** Inyección de cargas maliciosas (`' OR 1=1 --`) en el buscador de libros, confirmando que se evalúan como literales sin alterar la lógica de la consulta.

---

## Decisión 3: Normalización en Cuarta Forma Normal (4FN) vs. Columnas Multivaluadas o JSONB

- **Necesidad / Problema:** Modelar entidades con dependencias multivaluadas independientes (un libro tiene múltiples autores, múltiples géneros, múltiples imágenes y múltiples conceptos contextuales).
- **Alternativas Consideradas:**
  1. *Modelo Desnormalizado / NoSQL (Document Store / JSONB):* Almacenar arreglos JSON dentro de la tabla `books`.
  2. *Tercera Forma Normal básica (3FN) con delimitadores:* Cadenas de texto separadas por comas.
  3. *Cuarta Forma Normal (4FN) con Tablas Puente:* Descomponer cada dependencia multivaluada ($X \twoheadrightarrow Y$) en tablas de relación independientes (`book_authors`, `book_genres`, `book_images`, `book_concepts`).
- **Decisión Tomada:** Implementar **Cuarta Forma Normal (4FN) Estricta**.
- **Justificación Técnica:**
  - Garantiza integridad referencial mediante claves foráneas (`ON DELETE CASCADE / RESTRICT`).
  - Previene anomalías de inserción, actualización y eliminación producidas por productos cartesianos de atributos multivaluados independientes.
  - Facilita consultas indexadas y agregaciones complejas (e.g. listar todos los libros de un autor o buscar qué libros definen el concepto *Serverless*).
- **Riesgos y Limitaciones:** Mayor número de uniones (`JOIN`) en consultas de lectura complejas.
- **Evidencia de Validación:** Estructura validada en `01_schema.sql` y `02_seed.sql` con claves primarias compuestas y claves foráneas operativas.

---

## Decisión 4: Restricción de Máximo un 'Administrador' a Nivel de Base de Datos

- **Necesidad / Problema:** Garantizar de forma infalible la regla de negocio que prohíbe la existencia de más de un usuario con privilegios de Administrador.
- **Alternativas Consideradas:**
  1. *Validación exclusiva en backend:* Consultar `SELECT COUNT(*) FROM users WHERE role = 'Administrador'` antes de cada registro.
  2. *Trigger / Procedimiento Almacenado:* Disparador `BEFORE INSERT` que lance una excepción.
  3. *Índice Único Parcial en PostgreSQL:* `CREATE UNIQUE INDEX idx_single_admin ON users (role) WHERE role = 'Administrador';`
- **Decisión Tomada:** Aplicar **Índice Único Parcial en el motor de base de datos** respaldado por validación en aplicación.
- **Justificación Técnica:**
  - Es atómico y previene condiciones de carrera (*Race Conditions*) donde dos solicitudes concurrentes intenten registrar un administrador simultáneamente.
  - No penaliza el rendimiento de inserción de usuarios regulares (`role = 'Usuario'`), ya que el índice solo indexa filas con rol `'Administrador'`.
- **Riesgos y Limitaciones:** Si se requiere permitir más administradores en el futuro, se debe ejecutar una migración de esquema (`DROP INDEX`).
- **Evidencia de Validación:** Intento de inserción de un segundo usuario administrador rechazado con error `23505 (unique_violation)`.

---

## Decisión 5: Montaje de la Aplicación bajo el Prefijo `/library`

- **Necesidad / Problema:** Permitir que la aplicación opere de manera transparente detrás de un Proxy Inverso (Apache Web Server o NGINX) en infraestructura compartida sin conflictos de enrutamiento raíz `/`.
- **Alternativas Consideradas:**
  1. *Montar en raíz `/`:* Requiere que el Proxy Inverso reescriba todas las rutas (*URL Rewriting*), introduciendo complejidad y errores en redirecciones 302 y rutas estáticas.
  2. *Montar explícitamente en `/library`:* Toda la aplicación (rutas, assets estáticos, formularios y cookies) se estructuran bajo `/library`.
- **Decisión Tomada:** Montaje nativo en **`/library`**.
- **Justificación Técnica:**
  - Alineación 1:1 entre las URLs generadas por el servidor Node.js y la URL pública expuesta por el servidor web (`http://IP_SERVIDOR/library`).
  - Las rutas de recursos estáticos (`/library/public/*`, `/library/uploads/*`) y las redirecciones `res.redirect('/library/...')` funcionan de forma determinista.
- **Riesgos y Limitaciones:** Todos los enlaces y formularios deben mantener el prefijo `/library`.
- **Evidencia de Validación:** Configuración de `app.js` montando `app.use('/library', libraryRoutes)` y redirección de conveniencia en raíz `GET / -> /library`.

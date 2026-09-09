# Documento de Decisiones de Ingeniería (Architecture Decision Records - ADR)

**Proyecto:** Catálogo Bibliográfico y Microservicio Cloud (INTEGRACION03)  
**Asignatura:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  

---

## Estructura Metodológica
Cada decisión técnica sigue el estándar:
$$\text{Necesidad} \longrightarrow \text{Decisión} \longrightarrow \text{Justificación} \longrightarrow \text{Ventajas} \longrightarrow \text{Limitaciones}$$

---

### Decisión 1: Normalización Relacional Estricta en Cuarta Forma Normal (4FN)
- **Necesidad:** El catálogo almacena relaciones independientes con multiplicidad: un libro tiene múltiples autores independientes de sus múltiples géneros, múltiples imágenes y múltiples conceptos de computación en la nube.
- **Decisión:** Descomponer las dependencias multivaluadas en tablas intermedias discretas (`book_authors`, `book_genres`, `book_images`, `book_concepts`) con claves primarias compuestas y restricciones foráneas `ON UPDATE CASCADE ON DELETE CASCADE`.
- **Justificación:** Prevenir anomalías de inserción, actualización y redundancia combinatoria cartesiana.
- **Ventajas:** Cumplimiento formal del estándar relacional 4FN, unicidad garantizada y flexibilidad para consultas complejas.
- **Limitaciones:** Incrementa la necesidad de sentencias `JOIN` para recomponer el objeto libro.

---

### Decisión 2: Restricción Relacional para Máximo un Único Administrador
- **Necesidad:** Cumplir la regla de negocio que prohíbe la existencia de más de un usuario con privilegios administrativos sin depender exclusivamente de validaciones en código frontend o backend.
- **Decisión:** Crear un índice único parcial a nivel del motor PostgreSQL:
  ```sql
  CREATE UNIQUE INDEX idx_single_admin ON users (role) WHERE role = 'Administrador';
  ```
- **Justificación:** La integridad relacional debe garantizarse en la base de datos (SSOT), protegiendo el sistema ante fallas de validación en la capa de aplicación o inserciones manuales por DBA.
- **Ventajas:** Imposible violar la regla de negocio sin que el motor lance un error `UniqueViolation`.
- **Limitaciones:** Específico de PostgreSQL; motores más simples como MySQL estándar no soportan índices únicos con cláusula `WHERE`.

---

### Decisión 3: Adopción del Driver Moderno `psycopg` (v3) en lugar de `psycopg2`
- **Necesidad:** Conectar el microservicio Python Flask a PostgreSQL con alto rendimiento, soporte asíncrono y mapeo directo a diccionarios.
- **Decisión:** Utilizar `psycopg` (versión 3) con `row_factory=dict_row`.
- **Justificación:** `psycopg2` se encuentra en modo de mantenimiento; `psycopg3` está reescrito en C y Python con soporte nativo para tipos compuestos, pools de conexiones modernos y compatibilidad con Python 3.10+.
- **Ventajas:** Mayor eficiencia en red, mapeo directo a JSON/XML sin wrappers adicionales.
- **Limitaciones:** Requiere sintaxis de conexión moderna y configuración precisa de librerías nativas en despliegues Linux.

---

### Decisión 4: Arquitectura de Microservicio en una Sola Aplicación Flask (Sin Blueprints)
- **Necesidad:** Implementar el microservicio de catálogo bajo las restricciones del Prompt 03 y la Sesión 04a, maximizando legibilidad y minimizando overhead.
- **Decisión:** Desarrollar `app.py` centralizando los endpoints CRUD, búsqueda avanzada, serialización dual y módulo SOAP en un solo archivo plano.
- **Justificación:** Para servicios de propósito específico con bajo acoplamiento, evitar la complejidad de capas intermedias de Blueprints reduce la curva de depuración y facilita el despliegue directo en máquinas virtuales de GCP.
- **Ventajas:** Inicio inmediato, trazabilidad directa de rutas en Swagger `/docs` y despliegue simple con un solo comando `flask run`.
- **Limitaciones:** Menor modularidad para proyectos de escala empresarial con cientos de rutas.

---

### Decisión 5: Serializador Dual Dinámico (JSON & XML)
- **Necesidad:** Soportar clientes web modernos (que requieren JSON) y clientes corporativos o de escritorio como Electron (que requieren XML).
- **Decisión:** Implementar detección del parámetro `?format=XML|JSON` o encabezado `Accept` en cada endpoint de lectura, despachando respuestas con `Content-Type: application/xml` o `application/json`.
- **Justificación:** Evita duplicar código de consulta SQL y unifica la lógica de negocio en una sola fuente de verdad.
- **Ventajas:** Interoperabilidad total sin alterar las URLs base del catálogo.
- **Limitaciones:** Sobrecarga ligera en el backend al construir el árbol `xml.etree` en cada petición XML.

---

### Decisión 6: Detección de Colisiones de Clasificación mediante SOAP Fault 409
- **Necesidad:** Impedir que un evaluador clasifique el mismo concepto dos veces y reportar el error conforme al estándar formal de SOAP (Sesión 04).
- **Decisión:** Definir una restricción única compuesta `CONSTRAINT uq_usuario_concepto UNIQUE (clasificador_id, concept_id)` en `clasificaciones_cloud` y capturar la excepción `UniqueViolation` para generar un sobre `<soap:Fault>` con código `soap:Client.DuplicateClassification` y código HTTP 409.
- **Justificación:** Demuestra la integración entre el motor transaccional de PostgreSQL y el estándar de manejo de excepciones en protocolos XML RPC.
- **Ventajas:** Notificación estandarizada y verificable en la GUI del cliente Electron.
- **Limitaciones:** Requiere captura explícita a nivel de transacción para no dejar la sesión de base de datos en estado de aborto.

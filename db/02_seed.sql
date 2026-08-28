-- ==============================================================================
-- PROYECTO: APLICACIÓN WEB MONOLÍTICA PARA GESTIÓN DE LIBRERÍA
-- SCRIPT: 02_seed.sql - Datos Iniciales Sintéticos y de Dominio (30+ registros por entidad)
-- AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
-- ==============================================================================

-- 1. Usuarios del Sistema
-- Nota: Hash bcrypt de '666' generado con salt factor 10
-- Hash de '666': $2b$10$L19wW5v5x5s7m0l5e0r1e.Q4V6Z7K8Y9X0W1V2U3T4S5R6Q7P8O9N
-- El usuario admin es el único con rol 'Administrador'
INSERT INTO users (username, password_hash, role) VALUES
('admin', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Administrador'),
('usuario1', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario2', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario3', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario4', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario5', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario6', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario7', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario8', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario9', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario10', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario11', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario12', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario13', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario14', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario15', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario16', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario17', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario18', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario19', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario20', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario21', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario22', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario23', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario24', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario25', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario26', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario27', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario28', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario29', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario'),
('usuario30', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario');

-- 2. Formatos (30 registros)
INSERT INTO formats (id, name, description) VALUES
(1, 'Físico Tapa Dura', 'Edición encuadernada de lujo con tapa rígida y cosido'),
(2, 'Físico Tapa Blanda', 'Edición rústica estándar pegada al lomo'),
(3, 'Digital PDF', 'Documento en formato portátil con maquetación fija'),
(4, 'Digital EPUB', 'Formato electrónico estándar redimensionable para e-readers'),
(5, 'Digital MOBI', 'Formato electrónico optimizado para dispositivos Kindle antiguos'),
(6, 'Audiolibro MP3', 'Grabación de audio en formato estéreo comprimido'),
(7, 'Audiolibro M4B', 'Grabación de audio con soporte de capítulos y marcadores'),
(8, 'Espiral / Wire-O', 'Encuadernación de anillas metálicas ideal para manuales de laboratorio'),
(9, 'Edición de Bolsillo', 'Versión compacta y económica para lectura portátil'),
(10, 'Fascículo Técnico', 'Publicación monográfica de pocas páginas encuadernada con grapas'),
(11, 'Digital Kindle AZW3', 'Formato KF8 propietario de Amazon con soporte de tipografía avanzada'),
(12, 'Edición Coleccionista', 'Incluye caja contenedora, marcapáginas de tela y papel libre de ácido'),
(13, 'Hoja Suelta / Binder', 'Páginas perforadas listas para archivar en carpeta de 3 aros'),
(14, 'Boxset Multi-volumen', 'Conjunto de múltiples tomos presentados en estuche protector'),
(15, 'Digital Web Interactive', 'Acceso online interactivo con terminales y playgrounds ejecutables'),
(16, 'Edición Facsímil', 'Reproducción fotográfica exacta de la edición original histórica'),
(17, 'Físico Gran Formato', 'Dimensiones superiores a 25x30 cm con esquemas y diagramas a color'),
(18, 'Mini-Book', 'Formato miniatura de lectura ultracompacta'),
(19, 'Audiolibro FLAC', 'Audio sin pérdida en alta fidelidad 24-bit/96kHz'),
(20, 'Digital Markdown / Git', 'Repositorio con contenido en Markdown sincronizable con Git'),
(21, 'Edición Crítica Anotada', 'Texto con notas al pie, comentarios de expertos y bibliografía extendida'),
(22, 'Edición Bilingüe', 'Texto en inglés y español en páginas enfrentadas'),
(23, 'Microficha Técnica', 'Registro microfilmado para archivo histórico de ingeniería'),
(24, 'Libro de Trabajo / Workbook', 'Incluye espacios en blanco para resolución de ejercicios y problemas'),
(25, 'Digital SCORM / LMS', 'Paquete para integración directa en plataformas universitarias Canvas/Moodle'),
(26, 'Edición Piel Auténtica', 'Encuadernación artesanal en cuero con estampación en pan de oro'),
(27, 'Digital HTML Offline', 'Sitio estático autónomo descargable en un archivo comprimido'),
(28, 'Audiolibro Multivoz', 'Narración dramatizada con elenco de actores para diálogos técnicos'),
(29, 'Edición para Docente', 'Incluye guías pedagógicas, solucionarios y transparencias para clase'),
(30, 'Edición Braille / Accesible', 'Transcripción táctil para personas con discapacidad visual');

-- Ajustar secuencia de formats
SELECT setval('formats_id_seq', (SELECT MAX(id) FROM formats));

-- 3. Categorías (30 registros)
INSERT INTO categories (id, name, description) VALUES
(1, 'Cloud Computing', 'Arquitecturas, servicios de nube, virtualización y modelos como IaaS, PaaS y SaaS'),
(2, 'Sistemas Distribuidos', 'Consenso, replicación, sincronización, particionamiento y tolerancia a fallos'),
(3, 'Inteligencia Artificial', 'Modelos generativos, redes neuronales, machine learning y procesamiento de lenguaje'),
(4, 'Bases de Datos', 'Modelado relacional, SQL, 4FN, bases NoSQL, motores de almacenamiento y ACID'),
(5, 'Seguridad Informática', 'Criptografía, autenticación, autorización, Zero Trust y hardening de servidores'),
(6, 'Redes y Comunicaciones', 'Protocolos TCP/IP, DNS, HTTP/2/3, enrutamiento, firewalls y proxies inversos'),
(7, 'DevOps y SRE', 'Automatización, integración continua, infraestructura como código y observabilidad'),
(8, 'Arquitectura de Software', 'Patrones de diseño, microservicios, monolitos modulares y domain-driven design'),
(9, 'Desarrollo Web Fullstack', 'Servidores HTTP, renderizado server-side, APIs, HTML5, CSS y JavaScript'),
(10, 'Ingeniería de Datos', 'Pipelines ETL, streaming con Kafka, data lakes, almacenes OLAP y batch processing'),
(11, 'Compiladores y Lenguajes', 'Análisis léxico, sintáctico, semántico, optimización y generación de bytecode'),
(12, 'Sistemas Operativos', 'Gestión de memoria, scheduling de procesos, llamadas al sistema y virtualización'),
(13, 'Criptografía y Blockchain', 'Algoritmos asimétricos, funciones hash criptográficas, firmas y libros distribuidos'),
(14, 'Aprendizaje Profundo (Deep Learning)', 'Convolución, transformers, retropropagación y entrenamiento a escala'),
(15, 'Algoritmos y Estructuras de Datos', 'Complejidad computacional Big O, árboles B+, grafos y programación dinámica'),
(16, 'Microservicios', 'Descomposición por dominios, saga pattern, event sourcing y service mesh'),
(17, 'Internet de las Cosas (IoT)', 'Sistemas embebidos, protocolos MQTT, microcontroladores y edge computing'),
(18, 'Computación Cuántica', 'Qubits, superposición, entrelazamiento y circuitos cuánticos'),
(19, 'Programación Funcional', 'Inmutabilidad, funciones puras, mónadas y evaluación perezosa'),
(20, 'Concurrencia y Paralelismo', 'Hilos, bloqueos, semáforos, paso de mensajes y memoria transaccional'),
(21, 'Ingeniería de Software y Métodos Ágiles', 'Scrum, Kanban, Extreme Programming, refactorización y testing automatizado'),
(22, 'Bioinformática Computacional', 'Alineamiento de secuencias genéticas y algoritmos para análisis de proteínas'),
(23, 'Visión por Computadora', 'Procesamiento de imágenes digitales, segmentación, detección y tracking'),
(24, 'Computación Gráfica y Motores de Videojuegos', 'Shaders, rasterización, trazado de rayos y renderizado 3D en tiempo real'),
(25, 'Robótica Autónoma', 'Cinemática, navegación SLAM, control en tiempo real y frameworks ROS'),
(26, 'Procesamiento de Lenguaje Natural (NLP)', 'Tokenización, embeddings, modelos de lenguaje y análisis de sentimiento'),
(27, 'Computación Móvil y Ubicua', 'Desarrollo nativo Android/iOS, sincronización offline y geolocalización'),
(28, 'Gobierno de TI y Auditoría', 'Normas ISO 27001, COBIT, cumplimiento regulatorio y gestión de riesgos'),
(29, 'Computación de Alto Rendimiento (HPC)', 'Clústeres MPI, CUDA, supercómputo y benchmarks científicos'),
(30, 'Interacción Humano-Computadora (HCI)', 'Diseño de interfaces, experiencia de usuario, ergonomía cognitiva y accesibilidad');

-- Ajustar secuencia de categories
SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories));

-- 4. Géneros (30 registros)
INSERT INTO genres (id, name) VALUES
(1, 'Manual Técnico de Referencia'),
(2, 'Libro de Texto Universitario'),
(3, 'Monografía Especializada'),
(4, 'Guía Práctica Paso a Paso'),
(5, 'Patrones y Mejores Prácticas'),
(6, 'Ensayo de Filosofía Tecnológica'),
(7, 'Casos de Estudio Empresariales'),
(8, 'Cookbook de Código y Recetas'),
(9, 'Tratado Teórico Formal'),
(10, 'Historia de la Computación'),
(11, 'Biografía de Pioneros'),
(12, 'Guía de Preparación para Certificación'),
(13, 'Manual de Laboratorio'),
(14, 'Colección de Artículos Clásicos'),
(15, 'Auditoría y Checklist de Seguridad'),
(16, 'Diccionario Enciclopédico'),
(17, 'Ficción Tecnológica / Hard Sci-Fi'),
(18, 'Reporte de Investigación Científica'),
(19, 'Compendio de Problemas Resueltos'),
(20, 'Manual de Despliegue en Producción'),
(21, 'Guía de Troubleshooting y Diagnóstico'),
(22, 'Tratado de Optimización de Rendimiento'),
(23, 'Manifiesto y Cultura de Ingeniería'),
(24, 'Manual de Estándares de Codificación'),
(25, 'Guía de Refactorización de Legado'),
(26, 'Colección de Algoritmos Clásicos'),
(27, 'Atlas de Arquitecturas de Software'),
(28, 'Manual de Seguridad Defensiva'),
(29, 'Guía de Arquitectura Empresarial'),
(30, 'Compendio de Buenas Prácticas SRE');

-- Ajustar secuencia de genres
SELECT setval('genres_id_seq', (SELECT MAX(id) FROM genres));

-- 5. Autores (30 registros)
INSERT INTO authors (id, name, biography, country) VALUES
(1, 'Martin Fowler', 'Científico de la computación, autor de cabecera en ThoughtWorks y pionero en Refactoring y microservicios', 'Reino Unido'),
(2, 'Andrew S. Tanenbaum', 'Profesor emérito y creador del sistema operativo MINIX, autor de textos seminales en redes y SO', 'Países Bajos'),
(3, 'Donald E. Knuth', 'Profesor emérito de Stanford, autor de The Art of Computer Programming y creador de TeX', 'Estados Unidos'),
(4, 'Eric Evans', 'Especialista en diseño de dominios y autor del concepto Domain-Driven Design (DDD)', 'Estados Unidos'),
(5, 'Robert C. Martin', 'Consultor conocido como Uncle Bob, firmante del Manifiesto Ágil y autor de Clean Architecture', 'Estados Unidos'),
(6, 'Brendan Gregg', 'Especialista de rendimiento en sistemas a gran escala en Netflix e Intel, creador de los Flame Graphs', 'Australia'),
(7, 'Michael T. Nygard', 'Arquitecto de software y autor pionero en patrones de resiliencia como Circuit Breaker en Release It!', 'Estados Unidos'),
(8, 'Sam Newman', 'Consultor independiente y referente mundial en diseño y migración de sistemas basados en Microservicios', 'Reino Unido'),
(9, 'Gregor Hohpe', 'Arquitecto técnico corporativo en AWS y coautor de Enterprise Integration Patterns', 'Alemania'),
(10, 'Gene Kim', 'Investigador en DevOps, fundador de Tripwire y coautor de The Phoenix Project y Accelerate', 'Estados Unidos'),
(11, 'Jez Humble', 'Pionero de Continuous Delivery e investigador del impacto de DevOps en la industria de software', 'Reino Unido'),
(12, 'Nicole Forsgren', 'Científica de datos e investigadora principal en métricas DORA y productividad de ingeniería', 'Estados Unidos'),
(13, 'Werner Vogels', 'Vicepresidente y Director de Tecnología (CTO) de Amazon.com, impulsor de arquitecturas Cloud y Serverless', 'Países Bajos'),
(14, 'Kelsey Hightower', 'Evangelista principal de Cloud Computing y Kubernetes en Google Cloud', 'Estados Unidos'),
(15, 'Joe Beda', 'Co-creador de Kubernetes y cofundador de Heptio, referente en computación nativa de la nube', 'Estados Unidos'),
(16, 'Brendan Burns', 'Co-creador de Kubernetes y Vicepresidente de Azure Control Plane en Microsoft', 'Estados Unidos'),
(17, 'Jeffrey D. Ullman', 'Premio Turing 2020 por sus contribuciones a la teoría de bases de datos y compiladores en Stanford', 'Estados Unidos'),
(18, 'Abraham Silberschatz', 'Profesor en la Universidad de Yale, autor clásico en conceptos de bases de datos y sistemas operativos', 'Israel'),
(19, 'Thomas H. Cormen', 'Profesor en Dartmouth College y coautor del libro de algoritmos más citado del mundo (CLRS)', 'Estados Unidos'),
(20, 'Stuart Russell', 'Profesor en UC Berkeley y pionero en inteligencia artificial y alineación de sistemas inteligentes', 'Reino Unido'),
(21, 'Peter Norvig', 'Director de Investigación en Google y coautor del texto de referencia Artificial Intelligence: A Modern Approach', 'Estados Unidos'),
(22, 'Brian W. Kernighan', 'Científico de Bell Labs, co-creador de AWK y coautor del libro clásico sobre el lenguaje de programación C', 'Canadá'),
(23, 'Dennis Ritchie', 'Premio Turing, creador del lenguaje C y cocreador del sistema operativo Unix en Bell Labs', 'Estados Unidos'),
(24, 'Bjarne Stroustrup', 'Catedrático e inventor del lenguaje de programación C++ en Bell Labs', 'Dinamarca'),
(25, 'Linus Torvalds', 'Ingeniero de software creador del kernel Linux y del sistema de control de versiones distribuido Git', 'Finlandia'),
(26, 'Ian Goodfellow', 'Investigador en IA e inventor de las Redes Generativas Antagónicas (GANs)', 'Estados Unidos'),
(27, 'Yoshua Bengio', 'Premio Turing 2018 por sus contribuciones fundamentales al Deep Learning y redes neuronales', 'Canadá'),
(28, 'Yann LeCun', 'Premio Turing 2018, pionero de las redes neuronales convolucionales y Chief AI Scientist en Meta', 'Francia'),
(29, 'Chris Richardson', 'Creador de CloudFoundry y autor de Microservices Patterns, referente en arquitectura distribuida', 'Reino Unido'),
(30, 'Martin Kleppmann', 'Investigador en la Universidad de Cambridge y autor de Designing Data-Intensive Applications', 'Reino Unido');

-- Ajustar secuencia de authors
SELECT setval('authors_id_seq', (SELECT MAX(id) FROM authors));

-- 6. Conceptos (30 registros clave de Cloud Computing y Computación)
INSERT INTO concepts (id, name, general_summary) VALUES
(1, 'IaaS (Infrastructure as a Service)', 'Modelo de servicio en la nube donde el proveedor suministra recursos de computación, red y almacenamiento bajo demanda.'),
(2, 'PaaS (Platform as a Service)', 'Entorno de ejecución y despliegue en la nube que abstrae la gestión del sistema operativo y hardware subyacente.'),
(3, 'SaaS (Software as a Service)', 'Entrega de aplicaciones completas accesibles a través de la web alojadas centralmente por el proveedor.'),
(4, 'FaaS (Function as a Service)', 'Ejecución de fragmentos de código sin estado en respuesta a eventos con escalabilidad automática y cobro por milisegundo.'),
(5, 'Serverless', 'Paradigma donde el desarrollador no gestiona servidores físicos ni virtuales, delegando aprovisionamiento y escalado al proveedor.'),
(6, 'Multicloud', 'Estrategia de arquitectura que distribuye cargas de trabajo entre dos o más proveedores de nube independientes para evitar vendor lock-in.'),
(7, 'Bucket', 'Contenedor lógico fundamental dentro de servicios de almacenamiento de objetos como Google Cloud Storage o Amazon S3.'),
(8, 'Public Cloud', 'Infraestructura de computación en la nube compartida entre múltiples organizaciones a través de Internet público.'),
(9, 'Private Cloud', 'Entorno de nube dedicado exclusivamente a una única organización alojado on-premise o por un tercero.'),
(10, 'Hybrid Cloud', 'Entorno integrado que combina nubes privadas y públicas con orquestación y portabilidad de datos entre ambas.'),
(11, 'Containers', 'Mecanismo de empaquetado de software a nivel de sistema operativo que comparte el kernel y aísla dependencias.'),
(12, 'Kubernetes', 'Sistema de orquestación de código abierto para automatizar el despliegue, escalado y manejo de contenedores.'),
(13, 'Virtualization', 'Tecnología que permite crear múltiples entornos simulados o recursos dedicados a partir de un solo hardware físico mediante un hipervisor.'),
(14, 'Microservices', 'Estilo arquitectónico que estructura una aplicación como una colección de servicios independientes, acoplados débilmente y desplegables.'),
(15, 'API Gateway', 'Punto de entrada único que gestiona peticiones de clientes hacia microservicios backend, manejando enrutamiento, seguridad y rate limiting.'),
(16, 'Load Balancer', 'Dispositivo o software que distribuye el tráfico entrante de red entre múltiples servidores para evitar sobrecargas y maximizar disponibilidad.'),
(17, 'Object Storage', 'Estructura de almacenamiento escalable y plana que manipula datos como objetos discretos acompañados de metadatos y un identificador único.'),
(18, 'IAM (Identity and Access Management)', 'Marco de políticas y tecnologías que garantiza que los usuarios e identidades de software tengan los roles y permisos adecuados.'),
(19, 'CDN (Content Delivery Network)', 'Red geográficamente distribuida de servidores proxy de caché que entregan contenido web con baja latencia.'),
(20, 'Edge Computing', 'Paradigma que procesa y analiza los datos cerca de la fuente de generación en lugar de depender exclusivamente de centros de datos lejanos.'),
(21, 'CI/CD (Continuous Integration / Continuous Delivery)', 'Conjunto de prácticas automatizadas para compilar, probar y desplegar cambios de código de forma frecuente y segura.'),
(22, 'Infrastructure as Code (IaC)', 'Gestión y aprovisionamiento de infraestructura mediante código declarativo y archivos legibles por máquina (e.g. Terraform).'),
(23, 'Observability', 'Capacidad de inferir los estados internos de un sistema complejo a partir de sus salidas externas: métricas, trazas y registros.'),
(24, 'Telemetry', 'Recolección y transmisión automática de datos operativos y mediciones desde ubicaciones remotas para su monitoreo.'),
(25, 'Fault Tolerance', 'Propiedad de un sistema para continuar funcionando correctamente ante la falla imprevista de uno o más de sus componentes.'),
(26, 'Disaster Recovery', 'Conjunto de políticas, herramientas y procedimientos para habilitar la recuperación de sistemas críticos tras desastres naturales o humanos.'),
(27, 'Elasticity', 'Capacidad de un sistema en la nube de adaptarse a la demanda agregando o liberando recursos de forma autónoma en tiempo real.'),
(28, 'Scalability', 'Propiedad de un sistema para manejar una cantidad creciente de trabajo mediante la adición de recursos (vertical u horizontalmente).'),
(29, 'High Availability (HA)', 'Diseño arquitectónico que garantiza un nivel de rendimiento operativo y accesibilidad superior al 99.9% del tiempo acordado.'),
(30, 'Zero Trust', 'Modelo de seguridad que asume que ninguna entidad es de confianza por defecto, requiriendo verificación continua para cada solicitud.');

-- Ajustar secuencia de concepts
SELECT setval('concepts_id_seq', (SELECT MAX(id) FROM concepts));

-- 7. Libros (30 registros)
INSERT INTO books (id, isbn, title, publication_year, price, stock, format_id, category_id) VALUES
(1, '978-1491973042', 'Designing Data-Intensive Applications', 2017, 850.00, 15, 1, 2),
(2, '978-0134494166', 'Clean Architecture: A Craftsman Guide to Software Structure', 2017, 720.00, 20, 2, 8),
(3, '978-1491950357', 'Building Microservices: Designing Fine-Grained Systems', 2021, 790.00, 12, 1, 16),
(4, '978-0132350884', 'Clean Code: A Handbook of Agile Software Craftsmanship', 2008, 680.00, 25, 2, 21),
(5, '978-0201633610', 'Design Patterns: Elements of Reusable Object-Oriented Software', 1994, 950.00, 8, 1, 8),
(6, '978-0321125217', 'Domain-Driven Design: Tackling Complexity in Software Heart', 2003, 890.00, 10, 1, 8),
(7, '978-1492043782', 'Kubernetes: Up and Running Dive into the Future of Infrastructure', 2022, 740.00, 18, 3, 1),
(8, '978-0134092669', 'Operating Systems: Design and Implementation', 2015, 1150.00, 5, 1, 12),
(9, '978-0131103627', 'The C Programming Language (2nd Edition)', 1988, 590.00, 30, 2, 11),
(10, '978-0262033848', 'Introduction to Algorithms (CLRS 3rd Edition)', 2009, 1400.00, 14, 1, 15),
(11, '978-0134685991', 'Effective Java (3rd Edition)', 2018, 760.00, 22, 2, 8),
(12, '978-1491985274', 'Database Internals: A Deep Dive into Distributed Systems', 2019, 880.00, 9, 3, 4),
(13, '978-1492056010', 'Cloud Native Patterns: Designing change-tolerant software', 2019, 810.00, 16, 4, 1),
(14, '978-1617294549', 'Microservices Patterns: With examples in Java', 2018, 830.00, 11, 2, 16),
(15, '978-1950538478', 'The Phoenix Project: A Novel about IT and DevOps', 2018, 550.00, 28, 9, 7),
(16, '978-1942788331', 'Accelerate: Building and Scaling High Performing Tech Orgs', 2018, 620.00, 19, 2, 7),
(17, '978-0137081073', 'The Clean Coder: A Code of Conduct for Professional Programmers', 2011, 640.00, 24, 2, 21),
(18, '978-1492052203', 'Systems Performance: Enterprise and the Cloud (2nd Ed)', 2020, 1100.00, 7, 1, 7),
(19, '978-0321127426', 'Patterns of Enterprise Application Architecture', 2002, 920.00, 13, 1, 8),
(20, '978-0321200686', 'Enterprise Integration Patterns: Designing and Connecting Solutions', 2003, 980.00, 6, 1, 8),
(21, '978-1491978238', 'Site Reliability Engineering: How Google Runs Production Systems', 2016, 870.00, 17, 3, 7),
(22, '978-0262035613', 'Deep Learning (Adaptive Computation and Machine Learning)', 2016, 1350.00, 10, 1, 14),
(23, '978-0136042594', 'Artificial Intelligence: A Modern Approach (4th Edition)', 2020, 1550.00, 8, 1, 3),
(24, '978-0321356680', 'The Mythical Man-Month: Essays on Software Engineering', 1995, 510.00, 21, 9, 21),
(25, '978-1449373320', 'Designing Evolvable Web APIs with ASP.NET', 2014, 690.00, 15, 4, 9),
(26, '978-1491904244', 'You Don''t Know JS: Scope & Closures', 2014, 430.00, 35, 2, 9),
(27, '978-1492032649', 'Kafka: The Definitive Guide (2nd Edition)', 2021, 820.00, 12, 3, 10),
(28, '978-0133492606', 'Computer Networks (5th Edition)', 2010, 1200.00, 10, 1, 6),
(29, '978-0073523323', 'Database System Concepts (7th Edition)', 2019, 1300.00, 11, 1, 4),
(30, '978-1492080510', 'Software Architecture: The Hard Parts', 2021, 860.00, 14, 2, 8);

-- Ajustar secuencia de books
SELECT setval('books_id_seq', (SELECT MAX(id) FROM books));

-- 8. Relación Libros - Autores (book_authors)
INSERT INTO book_authors (book_id, author_id) VALUES
(1, 30), -- Designing Data-Intensive Applications -> Martin Kleppmann
(2, 5),  -- Clean Architecture -> Robert C. Martin
(3, 8),  -- Building Microservices -> Sam Newman
(4, 5),  -- Clean Code -> Robert C. Martin
(5, 1),  -- Design Patterns -> Martin Fowler
(6, 4),  -- Domain-Driven Design -> Eric Evans
(7, 14), -- Kubernetes: Up and Running -> Kelsey Hightower
(7, 15), -- Kubernetes: Up and Running -> Joe Beda
(7, 16), -- Kubernetes: Up and Running -> Brendan Burns
(8, 2),  -- Operating Systems -> Andrew S. Tanenbaum
(9, 22), -- The C Programming Language -> Brian W. Kernighan
(9, 23), -- The C Programming Language -> Dennis Ritchie
(10, 19),-- Introduction to Algorithms -> Thomas H. Cormen
(11, 5), -- Effective Java -> Robert C. Martin
(12, 30),-- Database Internals -> Martin Kleppmann
(13, 8), -- Cloud Native Patterns -> Sam Newman
(14, 29),-- Microservices Patterns -> Chris Richardson
(15, 10),-- The Phoenix Project -> Gene Kim
(16, 10),-- Accelerate -> Gene Kim
(16, 11),-- Accelerate -> Jez Humble
(16, 12),-- Accelerate -> Nicole Forsgren
(17, 5), -- The Clean Coder -> Robert C. Martin
(18, 6), -- Systems Performance -> Brendan Gregg
(19, 1), -- Patterns of Enterprise Application Architecture -> Martin Fowler
(20, 9), -- Enterprise Integration Patterns -> Gregor Hohpe
(21, 10),-- Site Reliability Engineering -> Gene Kim
(22, 26),-- Deep Learning -> Ian Goodfellow
(22, 27),-- Deep Learning -> Yoshua Bengio
(22, 28),-- Deep Learning -> Yann LeCun
(23, 20),-- Artificial Intelligence -> Stuart Russell
(23, 21),-- Artificial Intelligence -> Peter Norvig
(24, 1), -- The Mythical Man-Month -> Martin Fowler
(25, 1), -- Designing Evolvable Web APIs -> Martin Fowler
(26, 5), -- You Don't Know JS -> Robert C. Martin
(27, 30),-- Kafka: The Definitive Guide -> Martin Kleppmann
(28, 2), -- Computer Networks -> Andrew S. Tanenbaum
(29, 18),-- Database System Concepts -> Abraham Silberschatz
(29, 17),-- Database System Concepts -> Jeffrey D. Ullman
(30, 1); -- Software Architecture: The Hard Parts -> Martin Fowler

-- 9. Relación Libros - Géneros (book_genres)
INSERT INTO book_genres (book_id, genre_id) VALUES
(1, 1), (1, 27), (1, 22),
(2, 5), (2, 27),
(3, 1), (3, 5), (3, 20),
(4, 5), (4, 24),
(5, 5), (5, 26),
(6, 5), (6, 29),
(7, 4), (7, 20),
(8, 2), (8, 9),
(9, 2), (9, 10),
(10, 2), (10, 26),
(11, 5), (11, 8),
(12, 1), (12, 3),
(13, 5), (13, 20),
(14, 5), (14, 7),
(15, 7), (15, 23),
(16, 18), (16, 23),
(17, 5), (17, 23),
(18, 1), (18, 22),
(19, 5), (19, 27),
(20, 5), (20, 27),
(21, 1), (21, 30),
(22, 2), (22, 18),
(23, 2), (23, 9),
(24, 6), (24, 10),
(25, 4), (25, 5),
(26, 4), (26, 8),
(27, 1), (27, 4),
(28, 2), (28, 9),
(29, 2), (29, 9),
(30, 5), (30, 7);

-- 10. Relación Libros - Conceptos Específicos (book_concepts)
-- Enriquecido especialmente con conceptos de Cloud Computing para el libro 13 (Cloud Native Patterns) y libro 7 (Kubernetes)
INSERT INTO book_concepts (book_id, concept_id, specific_definition, chapter_page) VALUES
(1, 23, 'La observabilidad en sistemas intensivos en datos requiere trazas distribuidas y agregación unificada de registros.', 'Capítulo 1, p. 18'),
(1, 25, 'Tolerancia a fallos mediante replicación sin líder y quórums de lectura y escritura.', 'Capítulo 5, p. 152'),
(1, 28, 'Escalabilidad horizontal particionando datos por rango de claves o mediante hash consistente.', 'Capítulo 6, p. 199'),
(2, 14, 'Los límites arquitectónicos aíslan la lógica central de negocio de las decisiones de infraestructura y base de datos.', 'Capítulo 17, p. 165'),
(3, 14, 'Definición de microservicios como unidades autónomas con almacenamiento de datos desacoplado.', 'Capítulo 1, p. 4'),
(3, 15, 'Uso de un API Gateway como fachada para mitigar el exceso de llamadas en redes móviles.', 'Capítulo 5, p. 102'),
(7, 11, 'Los contenedores proporcionan aislamiento de procesos mediante cgroups y namespaces del kernel Linux.', 'Capítulo 2, p. 25'),
(7, 12, 'Kubernetes gestiona el ciclo de vida de Pods mediante controladores declarativos y reconciliación continua.', 'Capítulo 3, p. 45'),
(7, 27, 'Autoescalado horizontal de Pods (HPA) en función del uso de CPU y métricas personalizadas.', 'Capítulo 11, p. 180'),
(7, 29, 'Garantía de alta disponibilidad distribuyendo réplicas a través de múltiples zonas de disponibilidad en la nube.', 'Capítulo 14, p. 230'),
(13, 1, 'IaaS permite aprovisionar infraestructura elástica mediante APIs y scripts declarativos.', 'Capítulo 1, p. 10'),
(13, 2, 'PaaS acelera el desarrollo proporcionando plataformas gestionadas de base de datos y middleware.', 'Capítulo 1, p. 15'),
(13, 3, 'SaaS entrega valor directo al cliente final sin necesidad de mantenimiento de infraestructura.', 'Capítulo 1, p. 20'),
(13, 4, 'FaaS ejecuta lógica efímera disparada por eventos con escalado a cero inmediato.', 'Capítulo 2, p. 38'),
(13, 5, 'El paradigma Serverless elimina la fricción operativa al delegar parches y capacidad al proveedor.', 'Capítulo 2, p. 42'),
(13, 6, 'Estrategia Multicloud para evitar dependencia de un solo proveedor y optimizar costos globales.', 'Capítulo 3, p. 65'),
(13, 7, 'Uso de Buckets como almacenamiento de objetos inmutables para assets y respaldos.', 'Capítulo 4, p. 88'),
(13, 8, 'La Nube Pública ofrece escalabilidad elástica multi-tenant accesible vía Internet.', 'Capítulo 1, p. 12'),
(13, 9, 'La Nube Privada ofrece control estricto de gobernanza y soberanía de datos dentro del datacenter propio.', 'Capítulo 1, p. 14'),
(13, 10, 'La Nube Híbrida conecta la infraestructura privada local con la nube pública mediante túneles VPN o interconexión dedicada.', 'Capítulo 1, p. 16'),
(13, 17, 'Object Storage proporciona durabilidad de 11 nueves (99.999999999%) para datos no estructurados.', 'Capítulo 4, p. 95'),
(13, 18, 'IAM define políticas de mínimo privilegio y roles temporales para servicios y usuarios.', 'Capítulo 5, p. 120'),
(13, 21, 'Pipelines CI/CD automatizan la integración continua y despliegue continuo con pruebas canarias.', 'Capítulo 6, p. 145'),
(13, 22, 'Infrastructure as Code permite versionar la topología de red y servidores en repositorios Git.', 'Capítulo 7, p. 170'),
(13, 30, 'Modelo Zero Trust implementando autenticación mutua TLS (mTLS) entre todos los servicios.', 'Capítulo 8, p. 210'),
(14, 15, 'Patrón API Gateway para enrutar tráfico externo hacia el cluster interno de microservicios.', 'Capítulo 8, p. 275'),
(18, 23, 'Observabilidad profunda utilizando eBPF para capturar trazas del kernel sin sobrecarga de CPU.', 'Capítulo 4, p. 112'),
(21, 24, 'Telemetría distribuida para recopilar SLOs (Service Level Objectives) y tasas de error en tiempo real.', 'Capítulo 6, p. 89'),
(27, 25, 'Tolerancia a fallos en Kafka mediante particiones replicadas y elección automática de réplica líder.', 'Capítulo 3, p. 62'),
(28, 16, 'Balanceadores de carga L4 y L7 distribuyendo peticiones TCP y HTTP hacia granjas de servidores.', 'Capítulo 4, p. 140');

-- 11. Imágenes de Libros (book_images)
INSERT INTO book_images (book_id, image_url, alt_text, is_cover) VALUES
(1, '/library/public/img/books/ddia.webp', 'Portada de Designing Data-Intensive Applications', TRUE),
(2, '/library/public/img/books/clean_arch.webp', 'Portada de Clean Architecture', TRUE),
(3, '/library/public/img/books/microservices.webp', 'Portada de Building Microservices', TRUE),
(4, '/library/public/img/books/clean_code.webp', 'Portada de Clean Code', TRUE),
(5, '/library/public/img/books/design_patterns.webp', 'Portada de Design Patterns Gang of Four', TRUE),
(6, '/library/public/img/books/ddd.webp', 'Portada de Domain-Driven Design', TRUE),
(7, '/library/public/img/books/k8s.webp', 'Portada de Kubernetes Up and Running', TRUE),
(8, '/library/public/img/books/os_tanenbaum.webp', 'Portada de Operating Systems Design and Implementation', TRUE),
(9, '/library/public/img/books/c_kr.webp', 'Portada de The C Programming Language', TRUE),
(10, '/library/public/img/books/clrs.webp', 'Portada de Introduction to Algorithms CLRS', TRUE),
(11, '/library/public/img/books/effective_java.webp', 'Portada de Effective Java', TRUE),
(12, '/library/public/img/books/db_internals.webp', 'Portada de Database Internals', TRUE),
(13, '/library/public/img/books/cloud_native.webp', 'Portada de Cloud Native Patterns', TRUE),
(14, '/library/public/img/books/microservices_patterns.webp', 'Portada de Microservices Patterns', TRUE),
(15, '/library/public/img/books/phoenix_project.webp', 'Portada de The Phoenix Project', TRUE),
(16, '/library/public/img/books/accelerate.webp', 'Portada de Accelerate', TRUE),
(17, '/library/public/img/books/clean_coder.webp', 'Portada de The Clean Coder', TRUE),
(18, '/library/public/img/books/systems_performance.webp', 'Portada de Systems Performance Brendan Gregg', TRUE),
(19, '/library/public/img/books/eaa.webp', 'Portada de Patterns of Enterprise Application Architecture', TRUE),
(20, '/library/public/img/books/eip.webp', 'Portada de Enterprise Integration Patterns', TRUE),
(21, '/library/public/img/books/sre.webp', 'Portada de Site Reliability Engineering Google', TRUE),
(22, '/library/public/img/books/deep_learning.webp', 'Portada de Deep Learning Goodfellow', TRUE),
(23, '/library/public/img/books/aima.webp', 'Portada de Artificial Intelligence A Modern Approach', TRUE),
(24, '/library/public/img/books/mythical_man_month.webp', 'Portada de The Mythical Man-Month', TRUE),
(25, '/library/public/img/books/web_api.webp', 'Portada de Designing Evolvable Web APIs', TRUE),
(26, '/library/public/img/books/ydkjs.webp', 'Portada de You Dont Know JS Scope and Closures', TRUE),
(27, '/library/public/img/books/kafka.webp', 'Portada de Kafka The Definitive Guide', TRUE),
(28, '/library/public/img/books/networks.webp', 'Portada de Computer Networks Tanenbaum', TRUE),
(29, '/library/public/img/books/db_concepts.webp', 'Portada de Database System Concepts', TRUE),
(30, '/library/public/img/books/arch_hard_parts.webp', 'Portada de Software Architecture The Hard Parts', TRUE);

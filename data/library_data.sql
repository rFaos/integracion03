-- ==============================================================================
-- PROYECTO: INTEGRACION03 - GESTIÓN INTEGRAL DE LIBRERÍA
-- SCRIPT: library_data.sql - Datos Iniciales Sintéticos y de Dominio (30+ por entidad)
-- AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
-- ==============================================================================

-- 1. Usuarios del Sistema
-- Hash de '666' con bcrypt: $2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea
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
('usuario10', '$2a$10$w8M19lF58d601X6Zz/o48eQ5.pGf5qGhyf1l9HkM08V536gX3Vvea', 'Usuario');

-- 2. Formatos
INSERT INTO formats (id, name, description) VALUES
(1, 'Físico Tapa Dura', 'Edición encuadernada de lujo con tapa rígida y cosido'),
(2, 'Físico Tapa Blanda', 'Edición rústica estándar pegada al lomo'),
(3, 'Digital PDF', 'Documento en formato portátil con maquetación fija'),
(4, 'Digital EPUB', 'Formato electrónico estándar redimensionable para e-readers'),
(5, 'Digital MOBI', 'Formato electrónico optimizado para dispositivos Kindle antiguos'),
(6, 'Audiolibro MP3', 'Grabación de audio en formato estéreo comprimido'),
(7, 'Audiolibro M4B', 'Grabación de audio con soporte de capítulos y marcadores'),
(8, 'Espiral / Wire-O', 'Encuadernación de anillas metálicas ideal para manuales'),
(9, 'Edición de Bolsillo', 'Versión compacta y económica para lectura portátil'),
(10, 'Fascículo Técnico', 'Publicación monográfica de pocas páginas encuadernada con grapas');

SELECT setval('formats_id_seq', (SELECT MAX(id) FROM formats));

-- 3. Categorías
INSERT INTO categories (id, name, description) VALUES
(1, 'Cloud Computing', 'Arquitecturas, servicios de nube, virtualización y modelos IaaS, PaaS, SaaS'),
(2, 'Sistemas Distribuidos', 'Consenso, replicación, sincronización y tolerancia a fallos'),
(3, 'Inteligencia Artificial', 'Modelos generativos, redes neuronales y machine learning'),
(4, 'Bases de Datos', 'Modelado relacional, SQL, 4FN, NoSQL y motores ACID'),
(5, 'Seguridad Informática', 'Criptografía, autenticación, autorización y Zero Trust'),
(6, 'Redes y Comunicaciones', 'Protocolos TCP/IP, DNS, HTTP/2/3 y proxies inversos'),
(7, 'DevOps y SRE', 'Automatización, CI/CD, infraestructura como código y observabilidad'),
(8, 'Arquitectura de Software', 'Patrones de diseño, microservicios, monolitos modulares y DDD'),
(9, 'Desarrollo Web Fullstack', 'Servidores HTTP, renderizado server-side, APIs y frameworks'),
(10, 'Ingeniería de Datos', 'Pipelines ETL, streaming con Kafka, data lakes y almacenes OLAP');

SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories));

-- 4. Géneros
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
(10, 'Historia de la Computación');

SELECT setval('genres_id_seq', (SELECT MAX(id) FROM genres));

-- 5. Autores
INSERT INTO authors (id, name, biography, country) VALUES
(1, 'Martin Fowler', 'Científico de la computación, autor en ThoughtWorks y pionero en Refactoring', 'Reino Unido'),
(2, 'Andrew S. Tanenbaum', 'Profesor emérito y creador de MINIX, autor clásico en redes y SO', 'Países Bajos'),
(3, 'Donald E. Knuth', 'Profesor emérito de Stanford, autor de The Art of Computer Programming', 'Estados Unidos'),
(4, 'Eric Evans', 'Especialista en diseño de dominios y creador de Domain-Driven Design (DDD)', 'Estados Unidos'),
(5, 'Robert C. Martin', 'Consultor conocido como Uncle Bob, firmante del Manifiesto Ágil y autor de Clean Architecture', 'Estados Unidos'),
(6, 'Brendan Gregg', 'Especialista de rendimiento a gran escala en Netflix e Intel, creador de Flame Graphs', 'Australia'),
(7, 'Michael T. Nygard', 'Arquitecto de software y pionero en patrones de resiliencia en Release It!', 'Estados Unidos'),
(8, 'Sam Newman', 'Consultor independiente y referente mundial en diseño de Microservicios', 'Reino Unido'),
(9, 'Gregor Hohpe', 'Arquitecto corporativo en AWS y coautor de Enterprise Integration Patterns', 'Alemania'),
(10, 'Gene Kim', 'Investigador en DevOps y coautor de The Phoenix Project y Accelerate', 'Estados Unidos'),
(11, 'Kelsey Hightower', 'Evangelista principal de Cloud Computing y Kubernetes en Google Cloud', 'Estados Unidos'),
(12, 'Martin Kleppmann', 'Investigador en Cambridge y autor de Designing Data-Intensive Applications', 'Reino Unido');

SELECT setval('authors_id_seq', (SELECT MAX(id) FROM authors));

-- 6. Conceptos
INSERT INTO concepts (id, name, general_summary) VALUES
(1, 'IaaS (Infrastructure as a Service)', 'Recursos fundamentales de computación, red y almacenamiento bajo demanda.'),
(2, 'PaaS (Platform as a Service)', 'Entorno de ejecución y despliegue que abstrae la gestión del SO y hardware.'),
(3, 'SaaS (Software as a Service)', 'Aplicaciones completas alojadas centralmente y accesibles vía web.'),
(4, 'FaaS (Function as a Service)', 'Ejecución de fragmentos de código sin estado en respuesta a eventos con escalado a cero.'),
(5, 'Serverless', 'Paradigma donde la gestión y escalado de servidores es totalmente delegada al proveedor.'),
(6, 'Multicloud', 'Estrategia de arquitectura que distribuye cargas entre múltiples proveedores de nube.'),
(7, 'Bucket', 'Contenedor lógico fundamental en servicios de almacenamiento de objetos (S3 / GCS).'),
(8, 'Public Cloud', 'Infraestructura compartida de nube accesible vía Internet público.'),
(9, 'Private Cloud', 'Entorno de nube dedicado exclusivamente a una única organización.'),
(10, 'Hybrid Cloud', 'Entorno integrado que combina nubes privadas y públicas con portabilidad de datos.'),
(11, 'Containers', 'Empaquetado de software a nivel de SO que comparte kernel y aísla dependencias.'),
(12, 'Kubernetes', 'Sistema de orquestación de código abierto para automatizar despliegue y escalado de contenedores.'),
(13, 'Microservices', 'Arquitectura modular de servicios desacoplados e independientes.'),
(14, 'API Gateway', 'Punto de entrada único que gestiona peticiones hacia microservicios backend.'),
(15, 'Zero Trust', 'Modelo de seguridad que asume desconfianza por defecto y verifica cada solicitud.');

SELECT setval('concepts_id_seq', (SELECT MAX(id) FROM concepts));

-- 7. Libros
INSERT INTO books (id, isbn, title, publication_year, price, stock, format_id, category_id) VALUES
(1, '978-1491973042', 'Designing Data-Intensive Applications', 2017, 45.00, 15, 1, 2),
(2, '978-0134494166', 'Clean Architecture: A Craftsman Guide', 2017, 39.99, 20, 2, 8),
(3, '978-1491950357', 'Building Microservices: Designing Fine-Grained Systems', 2021, 49.50, 12, 1, 8),
(4, '978-0132350884', 'Clean Code: A Handbook of Agile Software', 2008, 42.00, 25, 2, 8),
(5, '978-0321125217', 'Domain-Driven Design: Tackling Complexity', 2003, 55.00, 10, 1, 8),
(6, '978-1492043782', 'Kubernetes: Up and Running', 2022, 38.00, 18, 3, 1),
(7, '978-1492056010', 'Cloud Native Patterns: Designing Change-Tolerant Software', 2019, 44.00, 16, 4, 1),
(8, '978-1950538478', 'The Phoenix Project: A Novel about IT and DevOps', 2018, 28.00, 28, 9, 7),
(9, '978-0133492606', 'Computer Networks (5th Edition)', 2010, 85.00, 4, 1, 6),
(10, '978-0134092669', 'Operating Systems: Design and Implementation', 2015, 78.00, 0, 1, 6);

SELECT setval('books_id_seq', (SELECT MAX(id) FROM books));

-- 8. Relaciones Libro - Autores (book_authors)
INSERT INTO book_authors (book_id, author_id) VALUES
(1, 12), -- DDIA -> Martin Kleppmann
(2, 5),  -- Clean Architecture -> Robert C. Martin
(3, 8),  -- Building Microservices -> Sam Newman
(4, 5),  -- Clean Code -> Robert C. Martin
(5, 4),  -- DDD -> Eric Evans
(6, 11), -- Kubernetes -> Kelsey Hightower
(7, 8),  -- Cloud Native Patterns -> Sam Newman
(8, 10), -- Phoenix Project -> Gene Kim
(9, 2),  -- Computer Networks -> Andrew S. Tanenbaum
(10, 2); -- Operating Systems -> Andrew S. Tanenbaum

-- 9. Relaciones Libro - Géneros (book_genres)
INSERT INTO book_genres (book_id, genre_id) VALUES
(1, 1), (1, 5),
(2, 5),
(3, 1), (3, 5),
(4, 5),
(5, 5),
(6, 4),
(7, 5),
(8, 7),
(9, 2),
(10, 2);

-- 10. Relaciones Libro - Conceptos (book_concepts)
INSERT INTO book_concepts (book_id, concept_id, definition, specific_definition, chapter_page) VALUES
(1, 13, 'Sistemas distribuidos que procesan y almacenan grandes volúmenes con particionamiento y replicación.', 'Sistemas distribuidos que procesan y almacenan grandes volúmenes con particionamiento y replicación.', 'Capítulo 1, p. 18'),
(3, 13, 'Descomposición del sistema en servicios autónomos acoplados débilmente.', 'Descomposición del sistema en servicios autónomos acoplados débilmente.', 'Capítulo 1, p. 4'),
(3, 14, 'Fachada de entrada para unificar llamadas externas hacia microservicios.', 'Fachada de entrada para unificar llamadas externas hacia microservicios.', 'Capítulo 5, p. 102'),
(6, 11, 'Los contenedores proporcionan aislamiento de procesos mediante cgroups y namespaces.', 'Los contenedores proporcionan aislamiento de procesos mediante cgroups y namespaces.', 'Capítulo 2, p. 25'),
(6, 12, 'Orquestador declarativo para automatizar el ciclo de vida de Pods.', 'Orquestador declarativo para automatizar el ciclo de vida de Pods.', 'Capítulo 3, p. 45'),
(7, 1, 'Aprovisionamiento programático de recursos de computación y red.', 'Aprovisionamiento programático de recursos de computación y red.', 'Capítulo 1, p. 10'),
(7, 2, 'Plataformas gestionadas para acelerar el ciclo de desarrollo.', 'Plataformas gestionadas para acelerar el ciclo de desarrollo.', 'Capítulo 1, p. 15'),
(7, 3, 'Software empaquetado y entregado como servicio web.', 'Software empaquetado y entregado como servicio web.', 'Capítulo 1, p. 20'),
(7, 4, 'Funciones efímeras invocadas por eventos con autoescalado.', 'Funciones efímeras invocadas por eventos con autoescalado.', 'Capítulo 2, p. 38'),
(7, 5, 'Delegación de administración y aprovisionamiento al proveedor cloud.', 'Delegación de administración y aprovisionamiento al proveedor cloud.', 'Capítulo 2, p. 42'),
(7, 15, 'Autenticación y cifrado mutuo mTLS entre todos los servicios.', 'Autenticación y cifrado mutuo mTLS entre todos los servicios.', 'Capítulo 8, p. 210');

-- 11. Imágenes de Libros (book_images)
INSERT INTO book_images (book_id, image_url, alt_text, is_cover) VALUES
(1, 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400', 'Designing Data-Intensive Applications', TRUE),
(2, 'https://images.unsplash.com/photo-1532012164546-f432f2e3777a?w=400', 'Clean Architecture', TRUE),
(3, 'https://images.unsplash.com/photo-1512820790803-83ca734da794?w=400', 'Building Microservices', TRUE),
(4, 'https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=400', 'Clean Code', TRUE),
(5, 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=400', 'Domain-Driven Design', TRUE),
(6, 'https://images.unsplash.com/photo-1667372393119-3d4c48d07fc9?w=400', 'Kubernetes Up and Running', TRUE),
(7, 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=400', 'Cloud Native Patterns', TRUE),
(8, 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=400', 'The Phoenix Project', TRUE),
(9, 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=400', 'Computer Networks', TRUE),
(10, 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=400', 'Operating Systems', TRUE);

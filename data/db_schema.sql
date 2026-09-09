-- ==============================================================================
-- PROYECTO: INTEGRACION03 - GESTIÓN INTEGRAL DE LIBRERÍA
-- SCRIPT: db_schema.sql - Esquema Relacional Normalizado en 4FN
-- AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
-- ==============================================================================

-- 1. Limpieza de tablas previas (en orden inverso de dependencias)
DROP TABLE IF EXISTS clasificaciones_cloud CASCADE;
DROP TABLE IF EXISTS clasificadores CASCADE;
DROP TABLE IF EXISTS clientes_servidos CASCADE;
DROP TABLE IF EXISTS book_concepts CASCADE;
DROP TABLE IF EXISTS book_images CASCADE;
DROP TABLE IF EXISTS book_genres CASCADE;
DROP TABLE IF EXISTS book_authors CASCADE;
DROP TABLE IF EXISTS books CASCADE;
DROP TABLE IF EXISTS concepts CASCADE;
DROP TABLE IF EXISTS authors CASCADE;
DROP TABLE IF EXISTS genres CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS formats CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 2. Tabla de Usuarios y Control de Roles
-- Regla de Negocio: Máximo un usuario con rol 'Administrador'
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('Administrador', 'Usuario')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índice único parcial que restringe la existencia de máximo 1 'Administrador'
CREATE UNIQUE INDEX idx_single_admin ON users (role) WHERE role = 'Administrador';

-- 3. Catálogos Independientes (1FN, 2FN, 3FN)
CREATE TABLE formats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE genres (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    biography TEXT,
    country VARCHAR(50)
);

CREATE TABLE concepts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    general_summary TEXT
);

-- 4. Tabla Principal de Libros (Entidad Central)
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(200) NOT NULL,
    publication_year INT CHECK (publication_year >= 1000 AND publication_year <= 2100),
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    format_id INT NOT NULL REFERENCES formats(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    category_id INT NOT NULL REFERENCES categories(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Tablas Intermedias / Descomposición de Dependencias Multivaluadas (4FN)

-- MVD: book_id ->-> author_id (Relación N:M)
CREATE TABLE book_authors (
    book_id INT NOT NULL REFERENCES books(id) ON UPDATE CASCADE ON DELETE CASCADE,
    author_id INT NOT NULL REFERENCES authors(id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (book_id, author_id)
);

-- MVD: book_id ->-> genre_id (Relación N:M)
CREATE TABLE book_genres (
    book_id INT NOT NULL REFERENCES books(id) ON UPDATE CASCADE ON DELETE CASCADE,
    genre_id INT NOT NULL REFERENCES genres(id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (book_id, genre_id)
);

-- MVD: book_id ->-> image_url (Relación 1:N)
CREATE TABLE book_images (
    id SERIAL PRIMARY KEY,
    book_id INT NOT NULL REFERENCES books(id) ON UPDATE CASCADE ON DELETE CASCADE,
    image_url VARCHAR(255) NOT NULL,
    alt_text VARCHAR(255),
    is_cover BOOLEAN NOT NULL DEFAULT FALSE
);

-- MVD: book_id ->-> concept_id con atributos de relación contextualizada por libro
CREATE TABLE book_concepts (
    book_id INT NOT NULL REFERENCES books(id) ON UPDATE CASCADE ON DELETE CASCADE,
    concept_id INT NOT NULL REFERENCES concepts(id) ON UPDATE CASCADE ON DELETE CASCADE,
    definition TEXT NOT NULL,
    specific_definition TEXT,
    chapter_page VARCHAR(100),
    PRIMARY KEY (book_id, concept_id)
);

-- 6. Índices para Optimización de Consultas y Búsqueda
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_isbn ON books(isbn);
CREATE INDEX idx_books_format_id ON books(format_id);
CREATE INDEX idx_books_category_id ON books(category_id);
CREATE INDEX idx_book_images_book_id ON book_images(book_id);
CREATE INDEX idx_book_concepts_concept_id ON book_concepts(concept_id);

-- ==============================================================================
-- 7. Tablas de Integración SOAP & Microservicios Cloud (SC3705 - Sesión 04)
-- ==============================================================================

-- Registro de usuarios evaluadores/clasificadores que interactúan vía SOAP o Electron
CREATE TABLE IF NOT EXISTS clasificadores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    correo VARCHAR(150) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Almacena las clasificaciones automáticas o manuales a modelos Cloud (IaaS, PaaS, SaaS, FaaS)
-- Vinculadas a los libros (books.isbn) y a los conceptos técnicos (concepts.id)
CREATE TABLE IF NOT EXISTS clasificaciones_cloud (
    id SERIAL PRIMARY KEY,
    clasificador_id INT NOT NULL REFERENCES clasificadores(id) ON UPDATE CASCADE ON DELETE CASCADE,
    isbn VARCHAR(20) REFERENCES books(isbn) ON UPDATE CASCADE ON DELETE SET NULL,
    concept_id INT REFERENCES concepts(id) ON UPDATE CASCADE ON DELETE SET NULL,
    texto_evaluado TEXT NOT NULL,
    modelo_cloud VARCHAR(10) NOT NULL CHECK (modelo_cloud IN ('IaaS', 'PaaS', 'SaaS', 'FaaS')),
    justificacion TEXT,
    fecha_clasificacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Restricción para detonar SOAP Fault (409 Conflict) si el mismo clasificador evalúa el mismo concepto dos veces:
    CONSTRAINT uq_usuario_concepto UNIQUE (clasificador_id, concept_id)
);

-- Métricas de auditoría: tipos de clientes servidos y número de peticiones procesadas
CREATE TABLE IF NOT EXISTS clientes_servidos (
    id SERIAL PRIMARY KEY,
    tipo_cliente VARCHAR(60) NOT NULL, -- 'Electron Desktop XML', 'SOAP Client', 'REST Web Browser', etc.
    endpoint_consultado VARCHAR(255) NOT NULL,
    formato_solicitado VARCHAR(20) NOT NULL, -- 'XML', 'JSON', 'SOAP-XML'
    peticiones_servidas INT NOT NULL DEFAULT 1,
    ip_origen VARCHAR(45) DEFAULT '127.0.0.1',
    ultima_peticion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_clasificaciones_isbn ON clasificaciones_cloud(isbn);
CREATE INDEX idx_clasificaciones_modelo ON clasificaciones_cloud(modelo_cloud);
CREATE INDEX idx_clientes_tipo ON clientes_servidos(tipo_cliente);


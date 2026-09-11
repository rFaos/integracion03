"""
==============================================================================
PROYECTO: INTEGRACION03 - MICROSERVICIO RESTFUL DE GESTIÓN BIBLIOGRÁFICA
TECNOLOGÍAS: Python 3, Flask, Psycopg v3 (psycopg), Flasgger (OpenAPI/Swagger)
AUTOR: Fabián Azaed Orta Singlaterry (Matrícula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
==============================================================================
"""

import os
import sys
from decimal import Decimal
from datetime import datetime, date
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flasgger import Swagger
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, ForeignKeyViolation, CheckViolation

# 1. Cargar variables de entorno desde el archivo .env local
load_dotenv()

app = Flask(__name__)

# 2. Configurar CORS para permitir invocaciones cross-origin
CORS(app, resources={r"/*": {"origins": "*"}})

# 3. Configuración de Swagger / OpenAPI
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs",
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Academic Library RESTful Microservice API",
        "description": (
            "Microservicio de backend para la administración y consulta del catálogo bibliográfico "
            "en arquitectura orientada a servicios (SOA / Microservicios) con base de datos PostgreSQL en 4FN."
        ),
        "version": "1.0.0",
        "contact": {
            "name": "Fabián Azaed Orta Singlaterry",
            "email": "azaedorta@hotmail.com",
            "institution": "Universidad de Monterrey (UDEM)"
        }
    },
    "tags": [
        {"name": "General", "description": "Endpoints de estado y verificación"},
        {"name": "Books", "description": "Operaciones CRUD y búsqueda avanzada sobre libros y 4FN"}
    ],
    "schemes": ["http", "https"]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# ==============================================================================
# HELPERS DE CONEXIÓN Y SERIALIZACIÓN
# ==============================================================================

def get_db_connection():
    """
    Establece y retorna una conexión a PostgreSQL usando el controlador moderno psycopg v3.
    """
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "library_user"),
        password=os.getenv("DB_PASSWORD", "666"),
        dbname=os.getenv("DB_NAME", "library"),
        row_factory=dict_row
    )

def serialize_record(record):
    """
    Convierte tipos no serializables nativamente en JSON (Decimal, date, datetime).
    """
    if record is None:
        return None
    if isinstance(record, list):
        return [serialize_record(item) for item in record]
    if isinstance(record, dict):
        new_dict = {}
        for k, v in record.items():
            if isinstance(v, Decimal):
                new_dict[k] = float(v)
            elif isinstance(v, (date, datetime)):
                new_dict[k] = v.isoformat()
            elif isinstance(v, dict):
                new_dict[k] = serialize_record(v)
            elif isinstance(v, list):
                new_dict[k] = [serialize_record(elem) for elem in v]
            else:
                new_dict[k] = v
        return new_dict
    return record

def serialize_book_to_xml_element(book_data):
    """
    Convierte un diccionario de libro a un elemento XML <book isbn="...">
    siguiendo la estructura canónica de library.xml / library03.xml.
    """
    isbn = str(book_data.get("isbn") or "")
    book_elem = ET.Element("book", attrib={"isbn": isbn})
    
    title_elem = ET.SubElement(book_elem, "title")
    title_elem.text = str(book_data.get("title") or "")
    
    authors_elem = ET.SubElement(book_elem, "authors")
    raw_authors = book_data.get("authors")
    if isinstance(raw_authors, list):
        for a in raw_authors:
            a_name = a.get("name") if isinstance(a, dict) else str(a)
            if a_name:
                auth_elem = ET.SubElement(authors_elem, "author")
                auth_elem.text = str(a_name)
    elif isinstance(raw_authors, str) and raw_authors:
        for a_name in raw_authors.split(","):
            if a_name.strip():
                auth_elem = ET.SubElement(authors_elem, "author")
                auth_elem.text = a_name.strip()
                
    pub_year = book_data.get("publication_year")
    if pub_year is not None:
        ET.SubElement(book_elem, "publication_year").text = str(pub_year)
        
    price = book_data.get("price")
    if price is not None:
        try:
            price_val = f"{float(price):.2f}"
        except (ValueError, TypeError):
            price_val = str(price)
        ET.SubElement(book_elem, "price", attrib={"currency": "USD"}).text = price_val
        
    stock = book_data.get("stock")
    if stock is not None:
        ET.SubElement(book_elem, "stock").text = str(stock)
        
    fmt = book_data.get("format_name") or book_data.get("format")
    if fmt:
        ET.SubElement(book_elem, "format").text = str(fmt)
        
    cat = book_data.get("category_name") or book_data.get("category")
    if cat:
        ET.SubElement(book_elem, "category").text = str(cat)
        
    genres_elem = ET.SubElement(book_elem, "genres")
    raw_genres = book_data.get("genres")
    if isinstance(raw_genres, list):
        for g in raw_genres:
            g_name = g.get("name") if isinstance(g, dict) else str(g)
            if g_name:
                ET.SubElement(genres_elem, "genre").text = str(g_name)
    elif isinstance(raw_genres, str) and raw_genres:
        for g_name in raw_genres.split(","):
            if g_name.strip():
                ET.SubElement(genres_elem, "genre").text = g_name.strip()
                
    cover_image = book_data.get("cover_image")
    if not cover_image and isinstance(book_data.get("images"), list):
        for img in book_data["images"]:
            if isinstance(img, dict) and img.get("is_cover"):
                cover_image = img.get("image_url")
                break
        if not cover_image and book_data["images"]:
            first_img = book_data["images"][0]
            if isinstance(first_img, dict):
                cover_image = first_img.get("image_url")
    if cover_image:
        ET.SubElement(book_elem, "cover_image").text = str(cover_image)
        
    raw_concepts = book_data.get("concepts")
    if isinstance(raw_concepts, list) and raw_concepts:
        concepts_elem = ET.SubElement(book_elem, "concepts")
        for c in raw_concepts:
            if isinstance(c, dict):
                c_name = c.get("concept_name") or c.get("name") or ""
                c_def = c.get("definition") or c.get("specific_definition") or ""
                c_page = c.get("chapter_page") or ""
                concept_elem = ET.SubElement(concepts_elem, "concept", attrib={"name": str(c_name)})
                ET.SubElement(concept_elem, "definition").text = str(c_def)
                if c_page:
                    ET.SubElement(concept_elem, "chapter_page").text = str(c_page)
                    
    return book_elem

def serialize_books_to_xml(books_list):
    """
    Serializa una lista de libros a un documento XML con elemento raíz <library>.
    """
    root = ET.Element("library")
    for b in books_list:
        root.append(serialize_book_to_xml_element(b))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

def serialize_single_book_to_xml(book_data, wrap_library=False):
    """
    Serializa un libro individual a XML. Por defecto elemento raíz <book isbn="...">
    o envuelto en <library> si wrap_library=True.
    """
    elem = serialize_book_to_xml_element(book_data)
    if wrap_library:
        root = ET.Element("library")
        root.append(elem)
        target = root
    else:
        target = elem
    ET.indent(target, space="  ")
    return ET.tostring(target, encoding="utf-8", xml_declaration=True).decode("utf-8")

def serialize_error_to_xml(message, extra=None):
    """
    Serializa un mensaje de error a XML.
    """
    root = ET.Element("error")
    msg_elem = ET.SubElement(root, "message")
    msg_elem.text = str(message)
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            sub = ET.SubElement(root, str(k))
            sub.text = str(v)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

def serialize_book_topics_to_xml(data):
    """
    Serializa la respuesta de temas de un libro (o lista de libros) a XML.
    """
    if isinstance(data, list):
        root = ET.Element("libros_temas")
        for item in data:
            libro_elem = ET.SubElement(root, "libro", attrib={"isbn": str(item.get("isbn") or "")})
            ET.SubElement(libro_elem, "nombre_libro").text = str(item.get("nombre_libro") or "")
            temas_elem = ET.SubElement(libro_elem, "temas")
            for t in item.get("temas", []):
                tema_elem = ET.SubElement(temas_elem, "tema")
                ET.SubElement(tema_elem, "nombre").text = str(t.get("tema") or "")
                ET.SubElement(tema_elem, "descripcion").text = str(t.get("descripcion") or "")
                if t.get("referencia"):
                    ET.SubElement(tema_elem, "referencia").text = str(t["referencia"])
        target = root
    else:
        root = ET.Element("libro", attrib={"isbn": str(data.get("isbn") or "")})
        ET.SubElement(root, "nombre_libro").text = str(data.get("nombre_libro") or "")
        temas_elem = ET.SubElement(root, "temas")
        for t in data.get("temas", []):
            tema_elem = ET.SubElement(temas_elem, "tema")
            ET.SubElement(tema_elem, "nombre").text = str(t.get("tema") or "")
            ET.SubElement(tema_elem, "descripcion").text = str(t.get("descripcion") or "")
            if t.get("referencia"):
                ET.SubElement(tema_elem, "referencia").text = str(t["referencia"])
        target = root

    ET.indent(target, space="  ")
    return ET.tostring(target, encoding="utf-8", xml_declaration=True).decode("utf-8")

def registrar_cliente_servido(tipo_cliente, endpoint, formato):
    """
    Registra métricas de auditoría en la tabla clientes_servidos (SC3705 - Sesión 04).
    """
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'clientes_servidos'
                    );
                """)
                table_exists = cur.fetchone()
                if table_exists and table_exists["exists"]:
                    cur.execute("""
                        INSERT INTO clientes_servidos (tipo_cliente, endpoint_consultado, formato_solicitado, peticiones_servidas, ip_origen, ultima_peticion)
                        VALUES (%s, %s, %s, 1, %s, NOW());
                    """, (tipo_cliente, endpoint, formato, ip))
                    conn.commit()
    except Exception:
        pass

# ==============================================================================
# ENDPOINTS GENERALES
# ==============================================================================

@app.route("/", methods=["GET"])
def index():
    """
    Endpoint raíz con información de servicio y documentación
    ---
    tags:
      - General
    responses:
      200:
        description: Metadatos del microservicio y rutas disponibles
    """
    return jsonify({
        "service": "Academic Library RESTful Microservice",
        "version": "1.0.0",
        "author": "Fabián Azaed Orta Singlaterry (613504)",
        "docs_url": "/docs",
        "endpoints": {
            "get_all_books": "GET /books",
            "get_book_by_isbn": "GET /books/<isbn>",
            "get_book_topics": "GET /books/<isbn>/temas",
            "get_all_books_topics": "GET /books/temas",
            "search_books": "GET /books/search?q=...&genre=...&year=...",
            "create_book": "POST /books",
            "update_book": "PUT /books/<isbn>",
            "delete_book": "DELETE /books/<isbn>",
            "health_check": "GET /health"
        }
    }), 200

@app.route("/health", methods=["GET"])
def health_check():
    """
    Verificación del estado del microservicio y conectividad a PostgreSQL
    ---
    tags:
      - General
    responses:
      200:
        description: Servicio y base de datos operativos
      503:
        description: Fallo de conexión a PostgreSQL
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS status;")
                res = cur.fetchone()
                return jsonify({
                    "status": "healthy",
                    "database": "connected",
                    "db_response": res["status"],
                    "timestamp": datetime.utcnow().isoformat()
                }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 503

# ==============================================================================
# ENDPOINTS CRUD Y BÚSQUEDA DE LIBROS
# ==============================================================================

@app.route("/books", methods=["GET"])
@app.route("/books/", methods=["GET"])
@app.route("/api/books", methods=["GET"])
@app.route("/api/books/", methods=["GET"])
def get_books():
    """
    Obtener todos los libros con autores, géneros, formatos y categorías (Soporta JSON y XML)
    ---
    tags:
      - Books
    produces:
      - application/json
      - application/xml
    parameters:
      - name: format
        in: query
        type: string
        enum: [JSON, XML, json, xml]
        default: JSON
        description: Formato de respuesta deseado (JSON o XML)
      - name: isbn
        in: query
        type: string
        description: Filtro opcional por código ISBN
    responses:
      200:
        description: Lista completa de libros en formato JSON o XML
      500:
        description: Error interno del servidor o base de datos
    """
    format_type = request.args.get("format", "JSON").strip().upper()
    isbn_param = request.args.get("isbn")

    query_base = """
        SELECT 
            b.id,
            b.isbn,
            b.title,
            b.publication_year,
            b.price,
            b.stock,
            f.name AS format_name,
            c.name AS category_name,
            COALESCE(
                (SELECT image_url FROM book_images WHERE book_id = b.id AND is_cover = TRUE LIMIT 1),
                (SELECT image_url FROM book_images WHERE book_id = b.id LIMIT 1),
                'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400'
            ) AS cover_image,
            COALESCE(
                (SELECT string_agg(a.name, ', ') 
                 FROM book_authors ba 
                 JOIN authors a ON ba.author_id = a.id 
                 WHERE ba.book_id = b.id), 
                'Sin autor'
            ) AS authors,
            COALESCE(
                (SELECT string_agg(g.name, ', ') 
                 FROM book_genres bg 
                 JOIN genres g ON bg.genre_id = g.id 
                 WHERE bg.book_id = b.id), 
                'General'
            ) AS genres
        FROM books b
        JOIN formats f ON b.format_id = f.id
        JOIN categories c ON b.category_id = c.id
    """
    params = []
    if isbn_param:
        query_base += " WHERE b.isbn = %s"
        params.append(isbn_param.strip())

    query_base += " ORDER BY b.id ASC;"

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_base, tuple(params) if params else None)
                books = cur.fetchall()
                serialized = serialize_record(books)

                if format_type == "XML":
                    xml_content = serialize_books_to_xml(serialized)
                    return Response(xml_content, status=200, mimetype="application/xml")

                return jsonify({
                    "count": len(serialized),
                    "books": serialized
                }), 200
    except Exception as e:
        if format_type == "XML":
            return Response(serialize_error_to_xml("Error al consultar los libros", {"details": str(e)}), status=500, mimetype="application/xml")
        return jsonify({"error": "Error al consultar los libros", "details": str(e)}), 500

@app.route("/books/<string:isbn>", methods=["GET"])
@app.route("/books/<string:isbn>/", methods=["GET"])
@app.route("/api/book/<string:isbn>", methods=["GET"])
@app.route("/api/book/<string:isbn>/", methods=["GET"])
def get_book_by_isbn(isbn):
    """
    Obtener el detalle completo de un libro por su ISBN (Soporta JSON y XML)
    ---
    tags:
      - Books
    produces:
      - application/json
      - application/xml
    parameters:
      - name: isbn
        in: path
        type: string
        required: true
        description: Código ISBN del libro (ej. 978-1491973042)
      - name: format
        in: query
        type: string
        enum: [JSON, XML, json, xml]
        default: JSON
        description: Formato de respuesta deseado (JSON o XML)
      - name: wrap
        in: query
        type: string
        description: "Si es 'library', envuelve el libro en el elemento raíz <library>"
    responses:
      200:
        description: Detalle exhaustivo del libro en formato JSON o XML
      404:
        description: Libro no encontrado
      500:
        description: Error interno del servidor
    """
    format_type = request.args.get("format", "JSON").strip().upper()
    wrap_lib = request.args.get("wrap", "").strip().lower() == "library" or request.args.get("root", "").strip().lower() == "library"
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Obtener datos del libro
                cur.execute("""
                    SELECT b.*, f.name AS format_name, c.name AS category_name
                    FROM books b
                    JOIN formats f ON b.format_id = f.id
                    JOIN categories c ON b.category_id = c.id
                    WHERE b.isbn = %s;
                """, (isbn.strip(),))
                book = cur.fetchone()

                if not book:
                    if format_type == "XML":
                        return Response(serialize_error_to_xml("Libro no encontrado", {"isbn": isbn}), status=404, mimetype="application/xml")
                    return jsonify({"error": "Libro no encontrado", "isbn": isbn}), 404

                book_id = book["id"]

                # 2. Obtener autores
                cur.execute("""
                    SELECT a.id, a.name, a.biography, a.country
                    FROM book_authors ba
                    JOIN authors a ON ba.author_id = a.id
                    WHERE ba.book_id = %s
                    ORDER BY a.name ASC;
                """, (book_id,))
                authors = cur.fetchall()

                # 3. Obtener géneros
                cur.execute("""
                    SELECT g.id, g.name
                    FROM book_genres bg
                    JOIN genres g ON bg.genre_id = g.id
                    WHERE bg.book_id = %s
                    ORDER BY g.name ASC;
                """, (book_id,))
                genres = cur.fetchall()

                # 4. Obtener galería de imágenes
                cur.execute("""
                    SELECT id, image_url, alt_text, is_cover
                    FROM book_images
                    WHERE book_id = %s
                    ORDER BY is_cover DESC, id ASC;
                """, (book_id,))
                images = cur.fetchall()

                # 5. Obtener conceptos contextuales asociados (4FN)
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'book_concepts' AND column_name IN ('definition', 'specific_definition');
                """)
                concept_cols = [r["column_name"] for r in cur.fetchall()]
                if "definition" in concept_cols and "specific_definition" in concept_cols:
                    def_expr = "COALESCE(bc.definition, bc.specific_definition) AS definition"
                elif "specific_definition" in concept_cols:
                    def_expr = "bc.specific_definition AS definition"
                else:
                    def_expr = "bc.definition AS definition"

                cur.execute(f"""
                    SELECT c.id AS concept_id, c.name AS concept_name, c.general_summary, 
                           {def_expr}, 
                           bc.chapter_page
                    FROM book_concepts bc
                    JOIN concepts c ON bc.concept_id = c.id
                    WHERE bc.book_id = %s
                    ORDER BY c.name ASC;
                """, (book_id,))
                concepts = cur.fetchall()

                full_book = dict(book)
                full_book["authors"] = authors
                full_book["genres"] = genres
                full_book["images"] = images
                full_book["concepts"] = concepts
                serialized = serialize_record(full_book)

                if format_type == "XML":
                    xml_content = serialize_single_book_to_xml(serialized, wrap_library=wrap_lib)
                    return Response(xml_content, status=200, mimetype="application/xml")

                return jsonify(serialized), 200
    except Exception as e:
        if format_type == "XML":
            return Response(serialize_error_to_xml("Error al consultar el libro", {"details": str(e)}), status=500, mimetype="application/xml")
        return jsonify({"error": "Error al consultar el libro", "details": str(e)}), 500

@app.route("/api/book/author/<int:author_id>", methods=["GET"])
@app.route("/api/book/author/<int:author_id>/", methods=["GET"])
@app.route("/books/author/<int:author_id>", methods=["GET"])
@app.route("/books/author/<int:author_id>/", methods=["GET"])
def get_books_by_author(author_id):
    """
    Obtener todos los libros escritos por un autor específico (SC3705 - Sesión 04a)
    ---
    tags:
      - Books
    produces:
      - application/json
      - application/xml
    parameters:
      - name: author_id
        in: path
        type: integer
        required: true
        description: Identificador numérico del autor
      - name: format
        in: query
        type: string
        enum: [JSON, XML, json, xml]
        default: JSON
        description: Formato de respuesta deseado (JSON o XML)
    responses:
      200:
        description: Metadatos del autor y catálogo de sus obras
      404:
        description: Autor no encontrado
      500:
        description: Error interno del servidor
    """
    format_type = request.args.get("format", "JSON").strip().upper()
    registrar_cliente_servido("REST Client", f"/api/book/author/{author_id}", format_type)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, biography, country FROM authors WHERE id = %s;", (author_id,))
                author = cur.fetchone()
                if not author:
                    msg = f"Autor con ID {author_id} no encontrado en catálogo"
                    if format_type == "XML":
                        return Response(serialize_error_to_xml(msg), status=404, mimetype="application/xml")
                    return jsonify({"error": msg}), 404

                cur.execute("""
                    SELECT b.id, b.isbn, b.title, b.publication_year, b.price, b.stock,
                           f.name AS format_name, c.name AS category_name,
                           COALESCE(
                               (SELECT image_url FROM book_images WHERE book_id = b.id AND is_cover = TRUE LIMIT 1),
                               (SELECT image_url FROM book_images WHERE book_id = b.id LIMIT 1),
                               'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400'
                           ) AS cover_image
                    FROM books b
                    JOIN book_authors ba ON b.id = ba.book_id
                    JOIN formats f ON b.format_id = f.id
                    JOIN categories c ON b.category_id = c.id
                    WHERE ba.author_id = %s
                    ORDER BY b.publication_year DESC;
                """, (author_id,))
                books = cur.fetchall()

                data = {
                    "author": dict(author),
                    "total_books": len(books),
                    "books": [dict(b) for b in books]
                }
                serialized = serialize_record(data)

                if format_type == "XML":
                    root = ET.Element("author_catalog", attrib={"author_id": str(author_id)})
                    auth_elem = ET.SubElement(root, "author")
                    ET.SubElement(auth_elem, "name").text = str(author["name"])
                    if author.get("country"):
                        ET.SubElement(auth_elem, "country").text = str(author["country"])
                    if author.get("biography"):
                        ET.SubElement(auth_elem, "biography").text = str(author["biography"])
                    books_elem = ET.SubElement(root, "books", attrib={"count": str(len(books))})
                    for b in serialized["books"]:
                        b_elem = ET.SubElement(books_elem, "book", attrib={"isbn": str(b.get("isbn") or "")})
                        ET.SubElement(b_elem, "title").text = str(b.get("title") or "")
                        ET.SubElement(b_elem, "publication_year").text = str(b.get("publication_year") or "")
                        ET.SubElement(b_elem, "price", attrib={"currency": "USD"}).text = f"{float(b.get('price', 0)):.2f}"
                        ET.SubElement(b_elem, "stock").text = str(b.get("stock") or "")
                        ET.SubElement(b_elem, "format").text = str(b.get("format_name") or "")
                        ET.SubElement(b_elem, "category").text = str(b.get("category_name") or "")
                        if b.get("cover_image"):
                            ET.SubElement(b_elem, "cover_image").text = str(b["cover_image"])
                    ET.indent(root, space="  ")
                    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
                    return Response(xml_str, status=200, mimetype="application/xml")

                return jsonify(serialized), 200
    except Exception as e:
        if format_type == "XML":
            return Response(serialize_error_to_xml("Error al consultar libros del autor", {"details": str(e)}), status=500, mimetype="application/xml")
        return jsonify({"error": "Error al consultar libros del autor", "details": str(e)}), 500

# ==============================================================================
# ENDPOINTS DE TEMAS Y CONCEPTOS (ESQUEMA 4FN)
# ==============================================================================

@app.route("/books/<string:isbn>/temas", methods=["GET"])
@app.route("/books/<string:isbn>/temas/", methods=["GET"])
@app.route("/books/<string:isbn>/topics", methods=["GET"])
@app.route("/books/<string:isbn>/topics/", methods=["GET"])
def get_book_topics(isbn):
    """
    Obtener nombre del libro, ISBN, temas que maneja y la descripción de cada tema
    ---
    tags:
      - Books
    produces:
      - application/json
      - application/xml
    parameters:
      - name: isbn
        in: path
        type: string
        required: true
        description: Código ISBN del libro (ej. 978-1491973042)
      - name: format
        in: query
        type: string
        enum: [JSON, XML, json, xml]
        default: JSON
        description: Formato de respuesta deseado (JSON o XML)
    responses:
      200:
        description: Nombre del libro, ISBN y lista de temas con sus descripciones
      404:
        description: Libro no encontrado
      500:
        description: Error interno del servidor
    """
    format_type = request.args.get("format", "JSON").strip().upper()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Obtener datos del libro por ISBN
                cur.execute("SELECT id, title, isbn FROM books WHERE isbn = %s;", (isbn.strip(),))
                book = cur.fetchone()
                if not book:
                    if format_type == "XML":
                        return Response(serialize_error_to_xml("Libro no encontrado", {"isbn": isbn}), status=404, mimetype="application/xml")
                    return jsonify({"error": "Libro no encontrado", "isbn": isbn}), 404

                book_id = book["id"]

                # 2. Detectar dinámicamente columnas en book_concepts para compatibilidad con el esquema
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'book_concepts' AND column_name IN ('definition', 'specific_definition');
                """)
                c_cols = [r["column_name"] for r in cur.fetchall()]
                if "definition" in c_cols and "specific_definition" in c_cols:
                    def_expr = "COALESCE(bc.definition, bc.specific_definition, c.general_summary)"
                elif "specific_definition" in c_cols:
                    def_expr = "COALESCE(bc.specific_definition, c.general_summary)"
                else:
                    def_expr = "COALESCE(bc.definition, c.general_summary)"

                # 3. Consultar temas asociados y su descripción
                cur.execute(f"""
                    SELECT 
                        c.name AS tema,
                        {def_expr} AS descripcion,
                        bc.chapter_page AS referencia
                    FROM book_concepts bc
                    JOIN concepts c ON bc.concept_id = c.id
                    WHERE bc.book_id = %s
                    ORDER BY c.name ASC;
                """, (book_id,))
                topics = cur.fetchall()

                result = {
                    "nombre_libro": book["title"],
                    "isbn": book["isbn"],
                    "total_temas": len(topics),
                    "temas": serialize_record(topics)
                }

                if format_type == "XML":
                    xml_content = serialize_book_topics_to_xml(result)
                    return Response(xml_content, status=200, mimetype="application/xml")

                return jsonify(result), 200
    except Exception as e:
        if format_type == "XML":
            return Response(serialize_error_to_xml("Error al consultar temas del libro", {"details": str(e)}), status=500, mimetype="application/xml")
        return jsonify({"error": "Error al consultar temas del libro", "details": str(e)}), 500

@app.route("/books/temas", methods=["GET"])
@app.route("/books/temas/", methods=["GET"])
@app.route("/books/topics", methods=["GET"])
@app.route("/books/topics/", methods=["GET"])
def get_all_books_topics():
    """
    Obtener todos los libros con sus temas y descripciones
    ---
    tags:
      - Books
    produces:
      - application/json
      - application/xml
    parameters:
      - name: isbn
        in: query
        type: string
        description: Filtro opcional por ISBN
      - name: format
        in: query
        type: string
        enum: [JSON, XML, json, xml]
        default: JSON
        description: Formato de respuesta deseado (JSON o XML)
    responses:
      200:
        description: Lista de libros con nombre, ISBN y sus temas con descripciones
      500:
        description: Error interno del servidor
    """
    isbn_param = request.args.get("isbn")
    if isbn_param:
        return get_book_topics(isbn_param.strip())

    format_type = request.args.get("format", "JSON").strip().upper()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, isbn FROM books ORDER BY id ASC;")
                books = cur.fetchall()

                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'book_concepts' AND column_name IN ('definition', 'specific_definition');
                """)
                c_cols = [r["column_name"] for r in cur.fetchall()]
                if "definition" in c_cols and "specific_definition" in c_cols:
                    def_expr = "COALESCE(bc.definition, bc.specific_definition, c.general_summary)"
                elif "specific_definition" in c_cols:
                    def_expr = "COALESCE(bc.specific_definition, c.general_summary)"
                else:
                    def_expr = "COALESCE(bc.definition, c.general_summary)"

                results = []
                for b in books:
                    cur.execute(f"""
                        SELECT 
                            c.name AS tema,
                            {def_expr} AS descripcion,
                            bc.chapter_page AS referencia
                        FROM book_concepts bc
                        JOIN concepts c ON bc.concept_id = c.id
                        WHERE bc.book_id = %s
                        ORDER BY c.name ASC;
                    """, (b["id"],))
                    topics = cur.fetchall()
                    results.append({
                        "nombre_libro": b["title"],
                        "isbn": b["isbn"],
                        "total_temas": len(topics),
                        "temas": serialize_record(topics)
                    })

                if format_type == "XML":
                    xml_content = serialize_book_topics_to_xml(results)
                    return Response(xml_content, status=200, mimetype="application/xml")

                return jsonify({
                    "count": len(results),
                    "libros": results
                }), 200
    except Exception as e:
        if format_type == "XML":
            return Response(serialize_error_to_xml("Error al consultar temas de los libros", {"details": str(e)}), status=500, mimetype="application/xml")
        return jsonify({"error": "Error al consultar temas de los libros", "details": str(e)}), 500

@app.route("/books/search", methods=["GET"])
@app.route("/books/search/", methods=["GET"])
def search_books():
    """
    Búsqueda avanzada de libros por filtros multi-criterio (Soporta JSON y XML)
    ---
    tags:
      - Books
    produces:
      - application/json
      - application/xml
    parameters:
      - name: q
        in: query
        type: string
        description: Texto a buscar en título o ISBN
      - name: author
        in: query
        type: string
        description: Nombre del autor
      - name: genre
        in: query
        type: string
        description: Género temático
      - name: year
        in: query
        type: integer
        description: Año de publicación exacto
      - name: min_price
        in: query
        type: number
        description: Precio mínimo
      - name: max_price
        in: query
        type: number
        description: Precio máximo
      - name: format
        in: query
        type: string
        enum: [JSON, XML, json, xml]
        default: JSON
        description: Formato de respuesta deseado (JSON o XML)
    responses:
      200:
        description: Resultados de la búsqueda en formato JSON o XML
      500:
        description: Error interno del servidor
    """
    format_type = request.args.get("format", "JSON").strip().upper()
    q = request.args.get("q", "").strip()
    author = request.args.get("author", "").strip()
    genre = request.args.get("genre", "").strip()
    year = request.args.get("year", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    query_parts = ["""
        SELECT 
            b.id,
            b.isbn,
            b.title,
            b.publication_year,
            b.price,
            b.stock,
            f.name AS format_name,
            c.name AS category_name,
            COALESCE(
                (SELECT string_agg(a.name, ', ') FROM book_authors ba JOIN authors a ON ba.author_id = a.id WHERE ba.book_id = b.id),
                'Sin autor'
            ) AS authors,
            COALESCE(
                (SELECT string_agg(g.name, ', ') FROM book_genres bg JOIN genres g ON bg.genre_id = g.id WHERE bg.book_id = b.id),
                'General'
            ) AS genres
        FROM books b
        JOIN formats f ON b.format_id = f.id
        JOIN categories c ON b.category_id = c.id
        WHERE 1=1
    """]
    params = []

    if q:
        query_parts.append(" AND (b.title ILIKE %s OR b.isbn ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if author:
        query_parts.append("""
            AND b.id IN (
                SELECT ba.book_id FROM book_authors ba 
                JOIN authors a ON ba.author_id = a.id 
                WHERE a.name ILIKE %s
            )
        """)
        params.append(f"%{author}%")

    if genre:
        query_parts.append("""
            AND b.id IN (
                SELECT bg.book_id FROM book_genres bg 
                JOIN genres g ON bg.genre_id = g.id 
                WHERE g.name ILIKE %s
            )
        """)
        params.append(f"%{genre}%")

    if year:
        try:
            query_parts.append(" AND b.publication_year = %s")
            params.append(int(year))
        except ValueError:
            pass

    if min_price:
        try:
            query_parts.append(" AND b.price >= %s")
            params.append(float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            query_parts.append(" AND b.price <= %s")
            params.append(float(max_price))
        except ValueError:
            pass

    query_parts.append(" ORDER BY b.id ASC;")
    final_query = "".join(query_parts)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(final_query, tuple(params))
                results = cur.fetchall()
                serialized = serialize_record(results)

                if format_type == "XML":
                    xml_content = serialize_books_to_xml(serialized)
                    return Response(xml_content, status=200, mimetype="application/xml")

                return jsonify({
                    "query_params": {
                        "q": q, "author": author, "genre": genre,
                        "year": year, "min_price": min_price, "max_price": max_price,
                        "format": format_type
                    },
                    "count": len(serialized),
                    "results": serialized
                }), 200
    except Exception as e:
        if format_type == "XML":
            return Response(serialize_error_to_xml("Error en la búsqueda de libros", {"details": str(e)}), status=500, mimetype="application/xml")
        return jsonify({"error": "Error en la búsqueda de libros", "details": str(e)}), 500

@app.route("/books", methods=["POST"])
@app.route("/api/book/insert", methods=["POST"])
def create_book():
    """
    Crear un nuevo libro junto con sus relaciones 4FN (Transacción Atómica)
    ---
    tags:
      - Books
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - isbn
            - title
            - publication_year
            - price
            - format_id
            - category_id
          properties:
            isbn:
              type: string
              example: "978-0131103627"
            title:
              type: string
              example: "The C Programming Language"
            publication_year:
              type: integer
              example: 1988
            price:
              type: number
              example: 59.00
            stock:
              type: integer
              example: 30
            format_id:
              type: integer
              example: 2
            category_id:
              type: integer
              example: 8
            author_ids:
              type: array
              items:
                type: integer
              example: [1, 2]
            genre_ids:
              type: array
              items:
                type: integer
              example: [1, 5]
            images:
              type: array
              items:
                type: object
                properties:
                  image_url:
                    type: string
                  alt_text:
                    type: string
                  is_cover:
                    type: boolean
            concepts:
              type: array
              items:
                type: object
                properties:
                  concept_id:
                    type: integer
                  definition:
                    type: string
                  chapter_page:
                    type: string
    responses:
      201:
        description: Libro creado exitosamente
      400:
        description: Datos de entrada inválidos o faltantes
      409:
        description: Conflicto - El ISBN ya existe
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Cuerpo de solicitud JSON requerido"}), 400

    required_fields = ["isbn", "title", "publication_year", "price", "format_id", "category_id"]
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        return jsonify({"error": "Campos obligatorios faltantes", "missing_fields": missing}), 400

    isbn = str(data["isbn"]).strip()
    title = str(data["title"]).strip()
    try:
        pub_year = int(data["publication_year"])
        price = float(data["price"])
        stock = int(data.get("stock", 0))
        format_id = int(data["format_id"])
        category_id = int(data["category_id"])
    except (ValueError, TypeError) as e:
        return jsonify({"error": "Tipos de datos numéricos inválidos", "details": str(e)}), 400

    author_ids = data.get("author_ids", [])
    genre_ids = data.get("genre_ids", [])
    images = data.get("images", [])
    concepts = data.get("concepts", [])

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Insertar el libro
                cur.execute("""
                    INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (isbn, title, pub_year, price, stock, format_id, category_id))
                new_book_id = cur.fetchone()["id"]

                # 2. Asociar autores
                for auth_id in author_ids:
                    cur.execute("""
                        INSERT INTO book_authors (book_id, author_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (new_book_id, int(auth_id)))

                # 3. Asociar géneros
                for gnr_id in genre_ids:
                    cur.execute("""
                        INSERT INTO book_genres (book_id, genre_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (new_book_id, int(gnr_id)))

                # 4. Insertar imágenes
                for img in images:
                    img_url = img.get("image_url")
                    if img_url:
                        alt = img.get("alt_text", title)
                        is_cov = bool(img.get("is_cover", False))
                        cur.execute("""
                            INSERT INTO book_images (book_id, image_url, alt_text, is_cover)
                            VALUES (%s, %s, %s, %s);
                        """, (new_book_id, img_url, alt, is_cov))

                # 5. Asociar conceptos
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'book_concepts' AND column_name IN ('definition', 'specific_definition');
                """)
                c_cols = [r["column_name"] for r in cur.fetchall()]

                for con in concepts:
                    c_id = con.get("concept_id")
                    c_def = con.get("definition") or con.get("specific_definition", "")
                    c_page = con.get("chapter_page", "")
                    if c_id and c_def:
                        if "definition" in c_cols and "specific_definition" in c_cols:
                            cur.execute("""
                                INSERT INTO book_concepts (book_id, concept_id, definition, specific_definition, chapter_page)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (book_id, concept_id)
                                DO UPDATE SET definition = EXCLUDED.definition, specific_definition = EXCLUDED.specific_definition, chapter_page = EXCLUDED.chapter_page;
                            """, (new_book_id, int(c_id), c_def, c_def, c_page))
                        elif "specific_definition" in c_cols:
                            cur.execute("""
                                INSERT INTO book_concepts (book_id, concept_id, specific_definition, chapter_page)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (book_id, concept_id)
                                DO UPDATE SET specific_definition = EXCLUDED.specific_definition, chapter_page = EXCLUDED.chapter_page;
                            """, (new_book_id, int(c_id), c_def, c_page))
                        else:
                            cur.execute("""
                                INSERT INTO book_concepts (book_id, concept_id, definition, chapter_page)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (book_id, concept_id)
                                DO UPDATE SET definition = EXCLUDED.definition, chapter_page = EXCLUDED.chapter_page;
                            """, (new_book_id, int(c_id), c_def, c_page))

            conn.commit()

        return jsonify({
            "message": "Libro registrado exitosamente",
            "book_id": new_book_id,
            "isbn": isbn,
            "title": title
        }), 201

    except UniqueViolation:
        return jsonify({"error": "Conflicto", "message": f"El ISBN '{isbn}' ya existe en la base de datos"}), 409
    except (ForeignKeyViolation, CheckViolation) as e:
        return jsonify({"error": "Violación de restricción de integridad relacional", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Error interno al crear el libro", "details": str(e)}), 500

@app.route("/books/<string:isbn>", methods=["PUT"])
@app.route("/api/book/update/<string:isbn>", methods=["PUT", "POST"])
def update_book(isbn):
    """
    Actualizar un libro existente y sus relaciones por ISBN
    ---
    tags:
      - Books
    parameters:
      - name: isbn
        in: path
        type: string
        required: true
        description: Código ISBN del libro a actualizar
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
            publication_year:
              type: integer
            price:
              type: number
            stock:
              type: integer
            format_id:
              type: integer
            category_id:
              type: integer
            author_ids:
              type: array
              items:
                type: integer
            genre_ids:
              type: array
              items:
                type: integer
    responses:
      200:
        description: Libro actualizado correctamente
      404:
        description: Libro no encontrado
      400:
        description: Datos inválidos
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Cuerpo de solicitud JSON requerido"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Verificar existencia del libro
                cur.execute("SELECT id FROM books WHERE isbn = %s;", (isbn.strip(),))
                book_row = cur.fetchone()
                if not book_row:
                    return jsonify({"error": "Libro no encontrado", "isbn": isbn}), 404

                book_id = book_row["id"]

                # 2. Actualizar campos escalares
                fields_to_update = []
                values = []

                if "title" in data and data["title"] is not None:
                    fields_to_update.append("title = %s")
                    values.append(str(data["title"]).strip())

                if "publication_year" in data and data["publication_year"] is not None:
                    fields_to_update.append("publication_year = %s")
                    values.append(int(data["publication_year"]))

                if "price" in data and data["price"] is not None:
                    fields_to_update.append("price = %s")
                    values.append(float(data["price"]))

                if "stock" in data and data["stock"] is not None:
                    fields_to_update.append("stock = %s")
                    values.append(int(data["stock"]))

                if "format_id" in data and data["format_id"] is not None:
                    fields_to_update.append("format_id = %s")
                    values.append(int(data["format_id"]))

                if "category_id" in data and data["category_id"] is not None:
                    fields_to_update.append("category_id = %s")
                    values.append(int(data["category_id"]))

                if fields_to_update:
                    values.append(book_id)
                    update_query = f"UPDATE books SET {', '.join(fields_to_update)} WHERE id = %s;"
                    cur.execute(update_query, tuple(values))

                # 3. Actualizar autores si se especifican
                if "author_ids" in data:
                    cur.execute("DELETE FROM book_authors WHERE book_id = %s;", (book_id,))
                    for a_id in data["author_ids"]:
                        cur.execute("INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s);", (book_id, int(a_id)))

                # 4. Actualizar géneros si se especifican
                if "genre_ids" in data:
                    cur.execute("DELETE FROM book_genres WHERE book_id = %s;", (book_id,))
                    for g_id in data["genre_ids"]:
                        cur.execute("INSERT INTO book_genres (book_id, genre_id) VALUES (%s, %s);", (book_id, int(g_id)))

            conn.commit()

        return jsonify({"message": "Libro actualizado correctamente", "isbn": isbn}), 200

    except Exception as e:
        return jsonify({"error": "Error al actualizar el libro", "details": str(e)}), 500

@app.route("/books/<string:isbn>", methods=["DELETE"])
@app.route("/api/book/delete/<string:isbn>", methods=["DELETE", "POST"])
def delete_book(isbn):
    """
    Eliminar un libro y sus referencias asociadas por ISBN
    ---
    tags:
      - Books
    parameters:
      - name: isbn
        in: path
        type: string
        required: true
        description: Código ISBN del libro a eliminar
    responses:
      200:
        description: Libro eliminado exitosamente
      404:
        description: Libro no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM books WHERE isbn = %s RETURNING id, title;", (isbn.strip(),))
                deleted = cur.fetchone()
                if not deleted:
                    return jsonify({"error": "Libro no encontrado", "isbn": isbn}), 404

            conn.commit()

        return jsonify({
            "message": "Libro eliminado correctamente",
            "isbn": isbn,
            "title": deleted["title"]
        }), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar el libro", "details": str(e)}), 500

# ==============================================================================
# MÓDULO DE SERVICIOS SOAP & WSDL (SC3705 - SESIÓN 04)
# Construcción manual de sobres XML con xml.etree.ElementTree (Sin Spyne ni Zeep)
# ==============================================================================

WSDL_DEFINITION = """<?xml version="1.0" encoding="UTF-8"?>
<definitions name="LibraryCloudClassifierService"
    targetNamespace="http://udem.edu/sc3705/soap/library"
    xmlns="http://schemas.xmlsoap.org/wsdl/"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
    xmlns:tns="http://udem.edu/sc3705/soap/library"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema">

  <types>
    <xsd:schema targetNamespace="http://udem.edu/sc3705/soap/library">
      <xsd:element name="ObtenerConceptosPendientesRequest">
        <xsd:complexType><xsd:sequence/></xsd:complexType>
      </xsd:element>
      <xsd:element name="ObtenerConceptosPendientesResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="total" type="xsd:int"/>
            <xsd:element name="conceptos">
              <xsd:complexType>
                <xsd:sequence>
                  <xsd:element name="concepto" maxOccurs="unbounded" minOccurs="0">
                    <xsd:complexType>
                      <xsd:sequence>
                        <xsd:element name="concept_id" type="xsd:int"/>
                        <xsd:element name="concept_name" type="xsd:string"/>
                        <xsd:element name="book_isbn" type="xsd:string"/>
                        <xsd:element name="book_title" type="xsd:string"/>
                        <xsd:element name="category" type="xsd:string"/>
                        <xsd:element name="definition" type="xsd:string"/>
                        <xsd:element name="chapter_page" type="xsd:string" minOccurs="0"/>
                      </xsd:sequence>
                    </xsd:complexType>
                  </xsd:element>
                </xsd:sequence>
              </xsd:complexType>
            </xsd:element>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>

      <xsd:element name="RegistrarClasificacionRequest">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="nombre" type="xsd:string"/>
            <xsd:element name="apellidos" type="xsd:string"/>
            <xsd:element name="correo" type="xsd:string"/>
            <xsd:element name="isbn" type="xsd:string" minOccurs="0"/>
            <xsd:element name="concept_id" type="xsd:int" minOccurs="0"/>
            <xsd:element name="texto_evaluado" type="xsd:string"/>
            <xsd:element name="modelo_cloud">
              <xsd:simpleType>
                <xsd:restriction base="xsd:string">
                  <xsd:enumeration value="IaaS"/>
                  <xsd:enumeration value="PaaS"/>
                  <xsd:enumeration value="SaaS"/>
                  <xsd:enumeration value="FaaS"/>
                </xsd:restriction>
              </xsd:simpleType>
            </xsd:element>
            <xsd:element name="justificacion" type="xsd:string" minOccurs="0"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="RegistrarClasificacionResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="status" type="xsd:string"/>
            <xsd:element name="clasificacion_id" type="xsd:int"/>
            <xsd:element name="mensaje" type="xsd:string"/>
            <xsd:element name="timestamp" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>

      <xsd:element name="ObtenerProgresoUsuarioRequest">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="correo" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="ObtenerProgresoUsuarioResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="correo" type="xsd:string"/>
            <xsd:element name="nombre_completo" type="xsd:string"/>
            <xsd:element name="total_clasificados" type="xsd:int"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>

      <xsd:element name="ObtenerEstadisticasPorModeloRequest">
        <xsd:complexType><xsd:sequence/></xsd:complexType>
      </xsd:element>
      <xsd:element name="ObtenerEstadisticasPorModeloResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="iaas_count" type="xsd:int"/>
            <xsd:element name="paas_count" type="xsd:int"/>
            <xsd:element name="saas_count" type="xsd:int"/>
            <xsd:element name="faas_count" type="xsd:int"/>
            <xsd:element name="total_count" type="xsd:int"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>

      <xsd:element name="DuplicateClassificationFault">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="error_message" type="xsd:string"/>
            <xsd:element name="correo" type="xsd:string"/>
            <xsd:element name="concept_id" type="xsd:int"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
  </types>

  <message name="ObtenerConceptosPendientesInput">
    <part name="parameters" element="tns:ObtenerConceptosPendientesRequest"/>
  </message>
  <message name="ObtenerConceptosPendientesOutput">
    <part name="parameters" element="tns:ObtenerConceptosPendientesResponse"/>
  </message>

  <message name="RegistrarClasificacionInput">
    <part name="parameters" element="tns:RegistrarClasificacionRequest"/>
  </message>
  <message name="RegistrarClasificacionOutput">
    <part name="parameters" element="tns:RegistrarClasificacionResponse"/>
  </message>
  <message name="DuplicateFaultMessage">
    <part name="fault" element="tns:DuplicateClassificationFault"/>
  </message>

  <message name="ObtenerProgresoUsuarioInput">
    <part name="parameters" element="tns:ObtenerProgresoUsuarioRequest"/>
  </message>
  <message name="ObtenerProgresoUsuarioOutput">
    <part name="parameters" element="tns:ObtenerProgresoUsuarioResponse"/>
  </message>

  <message name="ObtenerEstadisticasPorModeloInput">
    <part name="parameters" element="tns:ObtenerEstadisticasPorModeloRequest"/>
  </message>
  <message name="ObtenerEstadisticasPorModeloOutput">
    <part name="parameters" element="tns:ObtenerEstadisticasPorModeloResponse"/>
  </message>

  <portType name="LibraryCloudPortType">
    <operation name="ObtenerConceptosPendientes">
      <input message="tns:ObtenerConceptosPendientesInput"/>
      <output message="tns:ObtenerConceptosPendientesOutput"/>
    </operation>
    <operation name="RegistrarClasificacion">
      <input message="tns:RegistrarClasificacionInput"/>
      <output message="tns:RegistrarClasificacionOutput"/>
      <fault name="DuplicateFault" message="tns:DuplicateFaultMessage"/>
    </operation>
    <operation name="ObtenerProgresoUsuario">
      <input message="tns:ObtenerProgresoUsuarioInput"/>
      <output message="tns:ObtenerProgresoUsuarioOutput"/>
    </operation>
    <operation name="ObtenerEstadisticasPorModelo">
      <input message="tns:ObtenerEstadisticasPorModeloInput"/>
      <output message="tns:ObtenerEstadisticasPorModeloOutput"/>
    </operation>
  </portType>

  <binding name="LibraryCloudBinding" type="tns:LibraryCloudPortType">
    <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="ObtenerConceptosPendientes">
      <soap:operation soapAction="http://udem.edu/sc3705/soap/library/ObtenerConceptosPendientes"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
    </operation>
    <operation name="RegistrarClasificacion">
      <soap:operation soapAction="http://udem.edu/sc3705/soap/library/RegistrarClasificacion"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
      <fault name="DuplicateFault"><soap:fault name="DuplicateFault" use="literal"/></fault>
    </operation>
    <operation name="ObtenerProgresoUsuario">
      <soap:operation soapAction="http://udem.edu/sc3705/soap/library/ObtenerProgresoUsuario"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
    </operation>
    <operation name="ObtenerEstadisticasPorModelo">
      <soap:operation soapAction="http://udem.edu/sc3705/soap/library/ObtenerEstadisticasPorModelo"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
    </operation>
  </binding>

  <service name="LibraryCloudClassifierService">
    <port name="LibraryCloudPort" binding="tns:LibraryCloudBinding">
      <soap:address location="http://34.51.8.146:5001/soap"/>
    </port>
  </service>
</definitions>
"""

def build_soap_fault(faultcode, faultstring, detail_dict=None, status_code=500):
    """
    Construye un sobre SOAP Fault conforme al estándar SOAP 1.1 con códigos de estado adecuados
    """
    envelope = ET.Element("soap:Envelope", attrib={
        "xmlns:soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema"
    })
    body = ET.SubElement(envelope, "soap:Body")
    fault = ET.SubElement(body, "soap:Fault")
    
    fc = ET.SubElement(fault, "faultcode")
    fc.text = faultcode
    
    fs = ET.SubElement(fault, "faultstring")
    fs.text = faultstring
    
    if detail_dict:
        detail = ET.SubElement(fault, "detail")
        for k, v in detail_dict.items():
            elem = ET.SubElement(detail, str(k))
            elem.text = str(v)
            
    ET.indent(envelope, space="  ")
    xml_str = ET.tostring(envelope, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return Response(xml_str, status=status_code, mimetype="text/xml; charset=utf-8")

def build_soap_response(body_child_elem):
    """
    Envuelve un elemento XML en un sobre SOAP Envelope 1.1 estándar
    """
    envelope = ET.Element("soap:Envelope", attrib={
        "xmlns:soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "xmlns:m": "http://udem.edu/sc3705/soap/library"
    })
    body = ET.SubElement(envelope, "soap:Body")
    body.append(body_child_elem)
    ET.indent(envelope, space="  ")
    xml_str = ET.tostring(envelope, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return Response(xml_str, status=200, mimetype="text/xml; charset=utf-8")

def _strip_ns(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag

@app.route("/soap", methods=["GET"])
@app.route("/wsdl", methods=["GET"])
def get_soap_wsdl():
    """
    Descarga del Contrato Formal WSDL 1.1 del Servicio SOAP (SC3705 - Sesión 04)
    ---
    tags:
      - SOAP
    produces:
      - application/xml
      - text/xml
    responses:
      200:
        description: Documento de definición WSDL del servicio SOAP
    """
    if "wsdl" in request.args or request.path.endswith("/wsdl") or request.path == "/wsdl":
        registrar_cliente_servido("SOAP WSDL Client", "/soap?wsdl", "WSDL-XML")
        return Response(WSDL_DEFINITION.strip(), status=200, mimetype="text/xml; charset=utf-8")
    
    # Vista informativa del endpoint SOAP
    info_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap_service status="ONLINE">
  <name>Academic Library SOAP Cloud Classifier Service</name>
  <version>1.0.0</version>
  <institution>Universidad de Monterrey (UDEM)</institution>
  <course>SC3705 - Integracion de Aplicaciones Computacionales</course>
  <wsdl_url>{request.host_url}soap?wsdl</wsdl_url>
  <operations>
    <operation name="ObtenerConceptosPendientes">Retorna conceptos de Cloud catalogados pendientes de evaluacion.</operation>
    <operation name="RegistrarClasificacion">Registra clasificacion (IaaS/PaaS/SaaS/FaaS) de un concepto. Retorna Fault 409 si duplicado.</operation>
    <operation name="ObtenerProgresoUsuario">Consulta el total de conceptos clasificados por un usuario.</operation>
    <operation name="ObtenerEstadisticasPorModelo">Conteo agregado por modelo de servicio cloud.</operation>
  </operations>
</soap_service>"""
    return Response(info_xml, status=200, mimetype="application/xml; charset=utf-8")

@app.route("/soap", methods=["POST"])
def handle_soap_post():
    """
    Endpoint principal para procesamiento manual de mensajes SOAP 1.1 con xml.etree
    """
    raw_xml = request.get_data(as_text=True)
    if not raw_xml or not raw_xml.strip():
        return build_soap_fault("soap:Client", "Petición SOAP vacía o sin payload XML", status_code=400)
    
    try:
        root = ET.fromstring(raw_xml)
    except Exception as parse_err:
        return build_soap_fault("soap:Client.XMLParseError", f"Error de sintaxis XML: {str(parse_err)}", status_code=400)

    # Buscar el elemento Body
    body_elem = None
    for child in root:
        if _strip_ns(child.tag).lower() == "body":
            body_elem = child
            break

    if body_elem is None or len(body_elem) == 0:
        return build_soap_fault("soap:Client", "El sobre SOAP no contiene un elemento Body válido", status_code=400)

    op_elem = body_elem[0]
    op_name = _strip_ns(op_elem.tag)

    # Dispatch de operaciones:
    if op_name in ("ObtenerConceptosPendientes", "ObtenerConceptosPendientesRequest"):
        return _soap_obtener_conceptos_pendientes()
    elif op_name in ("RegistrarClasificacion", "RegistrarClasificacionRequest"):
        return _soap_registrar_clasificacion(op_elem)
    elif op_name in ("ObtenerProgresoUsuario", "ObtenerProgresoUsuarioRequest"):
        return _soap_obtener_progreso_usuario(op_elem)
    elif op_name in ("ObtenerEstadisticasPorModelo", "ObtenerEstadisticasPorModeloRequest"):
        return _soap_obtener_estadisticas_modelo()
    else:
        return build_soap_fault("soap:Client.InvalidOperation", f"Operación SOAP no reconocida: '{op_name}'", status_code=400)

def _soap_obtener_conceptos_pendientes():
    registrar_cliente_servido("SOAP Client", "/soap:ObtenerConceptosPendientes", "SOAP-XML")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'book_concepts' AND column_name = 'specific_definition';
                """)
                has_spec = cur.fetchone() is not None
                def_field = "COALESCE(bc.specific_definition, bc.definition, co.general_summary)" if has_spec else "COALESCE(bc.definition, co.general_summary)"

                cur.execute(f"""
                    SELECT 
                        co.id AS concept_id,
                        co.name AS concept_name,
                        b.isbn AS book_isbn,
                        b.title AS book_title,
                        cat.name AS category,
                        {def_field} AS definition,
                        bc.chapter_page
                    FROM book_concepts bc
                    JOIN books b ON bc.book_id = b.id
                    JOIN categories cat ON b.category_id = cat.id
                    JOIN concepts co ON bc.concept_id = co.id
                    ORDER BY b.id, co.id;
                """)
                rows = cur.fetchall()

                resp_elem = ET.Element("m:ObtenerConceptosPendientesResponse")
                ET.SubElement(resp_elem, "total").text = str(len(rows))
                conceptos_elem = ET.SubElement(resp_elem, "conceptos")
                for r in rows:
                    c_elem = ET.SubElement(conceptos_elem, "concepto")
                    ET.SubElement(c_elem, "concept_id").text = str(r["concept_id"])
                    ET.SubElement(c_elem, "concept_name").text = str(r["concept_name"])
                    ET.SubElement(c_elem, "book_isbn").text = str(r["book_isbn"])
                    ET.SubElement(c_elem, "book_title").text = str(r["book_title"])
                    ET.SubElement(c_elem, "category").text = str(r["category"])
                    ET.SubElement(c_elem, "definition").text = str(r["definition"] or "")
                    if r.get("chapter_page"):
                        ET.SubElement(c_elem, "chapter_page").text = str(r["chapter_page"])
                
                return build_soap_response(resp_elem)
    except Exception as e:
        return build_soap_fault("soap:Server", f"Error interno en base de datos: {str(e)}", status_code=500)

def _soap_registrar_clasificacion(op_elem):
    registrar_cliente_servido("SOAP Client", "/soap:RegistrarClasificacion", "SOAP-XML")
    data = {}
    for sub in op_elem:
        data[_strip_ns(sub.tag)] = sub.text.strip() if sub.text else ""

    nombre = data.get("nombre") or "Usuario"
    apellidos = data.get("apellidos") or "SOAP"
    correo = data.get("correo") or ""
    isbn = data.get("isbn") or None
    concept_id_str = data.get("concept_id") or ""
    texto_evaluado = data.get("texto_evaluado") or ""
    modelo_cloud = data.get("modelo_cloud", "").strip().upper()
    justificacion = data.get("justificacion") or "Clasificación registrada mediante sobre SOAP"

    if not correo:
        return build_soap_fault("soap:Client.ValidationError", "El campo 'correo' es obligatorio para identificar al clasificador", status_code=400)
    if not texto_evaluado:
        return build_soap_fault("soap:Client.ValidationError", "El campo 'texto_evaluado' no puede estar vacío", status_code=400)
    
    # Normalizar modelo_cloud
    valid_models = {"IAAS": "IaaS", "PAAS": "PaaS", "SAAS": "SaaS", "FAAS": "FaaS"}
    if modelo_cloud not in valid_models:
        return build_soap_fault("soap:Client.ValidationError", f"Modelo de servicio '{modelo_cloud}' inválido. Debe ser IaaS, PaaS, SaaS o FaaS.", status_code=400)
    modelo_cloud = valid_models[modelo_cloud]

    concept_id = int(concept_id_str) if concept_id_str.isdigit() else None

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Asegurar clasificador
                cur.execute("""
                    INSERT INTO clasificadores (nombre, apellidos, correo)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (correo) DO UPDATE SET 
                        nombre = EXCLUDED.nombre, 
                        apellidos = EXCLUDED.apellidos
                    RETURNING id;
                """, (nombre, apellidos, correo))
                clasificador_id = cur.fetchone()["id"]

                # 2. Intentar registrar la clasificación
                cur.execute("""
                    INSERT INTO clasificaciones_cloud (clasificador_id, isbn, concept_id, texto_evaluado, modelo_cloud, justificacion)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, fecha_clasificacion;
                """, (clasificador_id, isbn, concept_id, texto_evaluado, modelo_cloud, justificacion))
                new_row = cur.fetchone()
                conn.commit()

                resp_elem = ET.Element("m:RegistrarClasificacionResponse")
                ET.SubElement(resp_elem, "status").text = "SUCCESS"
                ET.SubElement(resp_elem, "clasificacion_id").text = str(new_row["id"])
                ET.SubElement(resp_elem, "clasificador_id").text = str(clasificador_id)
                ET.SubElement(resp_elem, "modelo_cloud").text = modelo_cloud
                ET.SubElement(resp_elem, "mensaje").text = f"Concepto clasificado exitosamente como {modelo_cloud}"
                ET.SubElement(resp_elem, "timestamp").text = str(new_row["fecha_clasificacion"])
                return build_soap_response(resp_elem)

    except UniqueViolation:
        # SOAP Fault 409 cuando ya fue clasificado por este clasificador (Sesión 04 Requisito)
        return build_soap_fault(
            faultcode="soap:Client.DuplicateClassification",
            faultstring=f"El concepto con ID {concept_id} ya fue clasificado previamente por el usuario {correo}",
            detail_dict={
                "error_code": "409_DUPLICATE_CLASSIFICATION",
                "correo": correo,
                "concept_id": str(concept_id),
                "message": "Violación de unicidad en clasificaciones_cloud: un clasificador no puede evaluar dos veces el mismo concepto."
            },
            status_code=409
        )
    except Exception as ex:
        return build_soap_fault("soap:Server", f"Error al procesar la clasificación: {str(ex)}", status_code=500)

def _soap_obtener_progreso_usuario(op_elem):
    registrar_cliente_servido("SOAP Client", "/soap:ObtenerProgresoUsuario", "SOAP-XML")
    data = {}
    for sub in op_elem:
        data[_strip_ns(sub.tag)] = sub.text.strip() if sub.text else ""
    correo = data.get("correo", "")
    if not correo:
        return build_soap_fault("soap:Client.ValidationError", "El campo 'correo' es obligatorio", status_code=400)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.id, c.nombre, c.apellidos, c.correo,
                           COUNT(cc.id) AS total_clasificados
                    FROM clasificadores c
                    LEFT JOIN clasificaciones_cloud cc ON c.id = cc.clasificador_id
                    WHERE c.correo = %s
                    GROUP BY c.id;
                """, (correo,))
                row = cur.fetchone()
                if not row:
                    return build_soap_fault("soap:Client.UserNotFound", f"No se encontró registro para el correo '{correo}'", status_code=404)

                cur.execute("""
                    SELECT id, isbn, concept_id, modelo_cloud, fecha_clasificacion
                    FROM clasificaciones_cloud
                    WHERE clasificador_id = %s
                    ORDER BY fecha_clasificacion DESC;
                """, (row["id"],))
                clasif_rows = cur.fetchall()

                resp_elem = ET.Element("m:ObtenerProgresoUsuarioResponse")
                ET.SubElement(resp_elem, "correo").text = row["correo"]
                ET.SubElement(resp_elem, "nombre_completo").text = f"{row['nombre']} {row['apellidos']}"
                ET.SubElement(resp_elem, "total_clasificados").text = str(row["total_clasificados"])
                items_elem = ET.SubElement(resp_elem, "clasificaciones")
                for cr in clasif_rows:
                    it = ET.SubElement(items_elem, "item")
                    ET.SubElement(it, "id").text = str(cr["id"])
                    ET.SubElement(it, "isbn").text = str(cr["isbn"] or "N/A")
                    ET.SubElement(it, "concept_id").text = str(cr["concept_id"] or "N/A")
                    ET.SubElement(it, "modelo_cloud").text = str(cr["modelo_cloud"])
                    ET.SubElement(it, "fecha").text = str(cr["fecha_clasificacion"])

                return build_soap_response(resp_elem)
    except Exception as e:
        return build_soap_fault("soap:Server", str(e), status_code=500)

def _soap_obtener_estadisticas_modelo():
    registrar_cliente_servido("SOAP Client", "/soap:ObtenerEstadisticasPorModelo", "SOAP-XML")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT modelo_cloud, COUNT(*) AS count
                    FROM clasificaciones_cloud
                    GROUP BY modelo_cloud;
                """)
                counts = {r["modelo_cloud"]: r["count"] for r in cur.fetchall()}
                iaas_c = counts.get("IaaS", 0)
                paas_c = counts.get("PaaS", 0)
                saas_c = counts.get("SaaS", 0)
                faas_c = counts.get("FaaS", 0)
                total_c = iaas_c + paas_c + saas_c + faas_c

                resp_elem = ET.Element("m:ObtenerEstadisticasPorModeloResponse")
                ET.SubElement(resp_elem, "iaas_count").text = str(iaas_c)
                ET.SubElement(resp_elem, "paas_count").text = str(paas_c)
                ET.SubElement(resp_elem, "saas_count").text = str(saas_c)
                ET.SubElement(resp_elem, "faas_count").text = str(faas_c)
                ET.SubElement(resp_elem, "total_count").text = str(total_c)
                return build_soap_response(resp_elem)
    except Exception as e:
        return build_soap_fault("soap:Server", str(e), status_code=500)

# ==============================================================================
# MANEJO CONTROLADO DE ERRORES GLOBALES
# ==============================================================================

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "Recurso no encontrado", "status_code": 404}), 404

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"error": "Error interno del servidor", "status_code": 500}), 500

# ==============================================================================
# ARRANQUE DE LA APLICACIÓN
# ==============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    print("=" * 70)
    print(" Academic Library RESTful Microservice (Flask + Psycopg v3)")
    print(f" Servidor iniciado en: http://127.0.0.1:{port}")
    print(f" Documentación Interactiva Swagger: http://127.0.0.1:{port}/docs")
    print(f" Base de Datos: {os.getenv('DB_NAME', 'library')} @ {os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}")
    print("=" * 70)
    app.run(host="0.0.0.0", port=port, debug=debug_mode)

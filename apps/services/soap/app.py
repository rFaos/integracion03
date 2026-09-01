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
from flask import Flask, request, jsonify
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
def get_books():
    """
    Obtener todos los libros con autores, géneros, formatos y categorías
    ---
    tags:
      - Books
    responses:
      200:
        description: Lista completa de libros
        schema:
          type: object
          properties:
            count:
              type: integer
            books:
              type: array
              items:
                type: object
      500:
        description: Error interno del servidor o base de datos
    """
    query = """
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
        ORDER BY b.id ASC;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                books = cur.fetchall()
                serialized = serialize_record(books)
                return jsonify({
                    "count": len(serialized),
                    "books": serialized
                }), 200
    except Exception as e:
        return jsonify({"error": "Error al consultar los libros", "details": str(e)}), 500

@app.route("/books/<string:isbn>", methods=["GET"])
def get_book_by_isbn(isbn):
    """
    Obtener el detalle completo de un libro por su ISBN (incluyendo autores, géneros, imágenes y conceptos 4FN)
    ---
    tags:
      - Books
    parameters:
      - name: isbn
        in: path
        type: string
        required: true
        description: Código ISBN del libro (ej. 978-1491973042)
    responses:
      200:
        description: Detalle exhaustivo del libro
      404:
        description: Libro no encontrado
      500:
        description: Error interno del servidor
    """
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
                    SELECT c.id AS concept_id, c.name AS concept_name, c.general_summary, 
                           COALESCE(bc.definition, bc.specific_definition) AS definition, 
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

                return jsonify(serialize_record(full_book)), 200
    except Exception as e:
        return jsonify({"error": "Error al consultar el libro", "details": str(e)}), 500

@app.route("/books/search", methods=["GET"])
def search_books():
    """
    Búsqueda avanzada de libros por filtros multi-criterio
    ---
    tags:
      - Books
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
    responses:
      200:
        description: Resultados de la búsqueda
      500:
        description: Error interno del servidor
    """
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
                return jsonify({
                    "query_params": {
                        "q": q, "author": author, "genre": genre,
                        "year": year, "min_price": min_price, "max_price": max_price
                    },
                    "count": len(serialized),
                    "results": serialized
                }), 200
    except Exception as e:
        return jsonify({"error": "Error en la búsqueda de libros", "details": str(e)}), 500

@app.route("/books", methods=["POST"])
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
                for con in concepts:
                    c_id = con.get("concept_id")
                    c_def = con.get("definition") or con.get("specific_definition", "")
                    c_page = con.get("chapter_page", "")
                    if c_id and c_def:
                        cur.execute("""
                            INSERT INTO book_concepts (book_id, concept_id, definition, specific_definition, chapter_page)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (book_id, concept_id)
                            DO UPDATE SET definition = EXCLUDED.definition, specific_definition = EXCLUDED.specific_definition, chapter_page = EXCLUDED.chapter_page;
                        """, (new_book_id, int(c_id), c_def, c_def, c_page))

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

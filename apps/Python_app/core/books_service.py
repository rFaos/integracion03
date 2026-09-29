"""Servicio de libros: habla con el microservicio de libros (puerto 5001).

Endpoints utilizados:

    GET    /health              -> semaforo de estado (lo usa health_service)
    GET    /books?format=json   -> catalogo
    GET    /books/<isbn>        -> detalle: autores, generos, imagenes y conceptos
    GET    /books/search        -> filtros por texto, autor, genero, anio y precio
    POST   /books               -> alta (201; 409 si el ISBN ya existe)
    PUT    /books/<isbn>        -> reemplazo COMPLETO de la representacion
    PATCH  /books/<isbn>        -> modificacion PARCIAL (solo lo enviado)
    DELETE /books/<isbn>        -> baja (404 si no existe)
    GET    /catalogs            -> listas de formatos, categorias, autores y generos

La aplicacion NUNCA accede a PostgreSQL: todo pasa por estos endpoints.
"""


class BooksService:
    """Operaciones del catalogo bibliografico."""

    def __init__(self, http, config):
        self.http = http
        self.config = config

    @property
    def base_url(self):
        return self.config.base_url("books")

    # ------------------------------------------------------------------ lectura
    def list_books(self):
        """Catalogo completo. El servicio devuelve {'count', 'books'}."""
        payload = self.http.get(self.base_url, "/books", params={"format": "json"})
        return self._extract_list(payload, "books")

    def search(self, q=None, author=None, genre=None, year=None,
               min_price=None, max_price=None):
        """Busqueda multi-criterio. El servicio devuelve {'count', 'results'}.

        Se envian solo los filtros con valor: un parametro vacio no filtra.
        El parametro `q` del servicio busca a la vez en titulo e ISBN
        (`b.title ILIKE %s OR b.isbn ILIKE %s`), por lo que cubre los dos
        criterios de busqueda que pide la actividad.
        """
        params = {
            "format": "json",
            "q": q or None,
            "author": author or None,
            "genre": genre or None,
            "year": year or None,
            "min_price": min_price or None,
            "max_price": max_price or None,
        }
        payload = self.http.get(self.base_url, "/books/search", params=params)
        return self._extract_list(payload, "results")

    def get_book(self, isbn):
        """Detalle de un libro, incluidos sus conceptos y su galeria de imagenes."""
        return self.http.get(self.base_url, f"/books/{isbn}", params={"format": "json"})

    def get_topics(self, isbn):
        """Conceptos asociados al libro (GET /books/<isbn>/temas)."""
        payload = self.http.get(self.base_url, f"/books/{isbn}/temas", params={"format": "json"})
        if isinstance(payload, dict):
            for key in ("temas", "topics", "results", "conceptos"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        return []

    def catalogs(self):
        """Listas de apoyo para los formularios (formatos, categorias, autores, generos)."""
        payload = self.http.get(self.base_url, "/catalogs", params={"format": "json"})
        if isinstance(payload, dict):
            return {
                "formats": payload.get("formats") or [],
                "categories": payload.get("categories") or [],
                "authors": payload.get("authors") or [],
                "genres": payload.get("genres") or [],
            }
        return {"formats": [], "categories": [], "authors": [], "genres": []}

    # ------------------------------------------------------------------ escritura
    def create(self, book):
        """Alta de libro (POST /books). 409 si el ISBN ya existe."""
        return self.http.post(self.base_url, "/books", body=book)

    def replace(self, isbn, book):
        """Actualizacion COMPLETA (PUT /books/<isbn>).

        Se envia la representacion entera del libro porque PUT reemplaza el
        recurso: el servicio responde 400 si falta algun campo editable.
        """
        return self.http.put(self.base_url, f"/books/{isbn}", body=book)

    def patch(self, isbn, changes):
        """Actualizacion PARCIAL (PATCH /books/<isbn>).

        `changes` lleva unicamente los atributos modificados; el servicio deja
        el resto como estaba.
        """
        return self.http.patch(self.base_url, f"/books/{isbn}", body=changes)

    def delete(self, isbn):
        """Baja de libro (DELETE /books/<isbn>). 404 si no existe."""
        return self.http.delete(self.base_url, f"/books/{isbn}")

    # ------------------------------------------------------------------ internos
    @staticmethod
    def _extract_list(payload, key):
        if isinstance(payload, dict):
            if isinstance(payload.get(key), list):
                return payload[key]
            for alternative in ("books", "results", "data", "libros"):
                if isinstance(payload.get(alternative), list):
                    return payload[alternative]
        if isinstance(payload, list):
            return payload
        return []


# ------------------------------------------------------------------------------
# Normalizacion para la interfaz grafica
# ------------------------------------------------------------------------------
def _authors_text(value):
    """Autores como texto legible.

    El catalogo los entrega como cadena ("A, B") y el detalle como lista de
    diccionarios ([{'name': 'A'}]): aqui se unifican.
    """
    if not value:
        return "Sin autor"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        names = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    names.append(str(name))
            elif item:
                names.append(str(item))
        return ", ".join(names) if names else "Sin autor"
    return str(value)


def _images_of(raw):
    """Galeria de imagenes normalizada; lista vacia si el libro no tiene."""
    images = raw.get("images") or []
    result = []
    for image in images:
        if isinstance(image, dict) and image.get("image_url"):
            result.append({
                "url": image["image_url"],
                "alt": image.get("alt_text") or raw.get("title") or "",
                "is_cover": bool(image.get("is_cover")),
            })
    return result


def _concepts_of(raw):
    """Conceptos/definiciones asociados al libro (formato 4FN del servicio)."""
    concepts = raw.get("concepts") or []
    result = []
    for concept in concepts:
        if not isinstance(concept, dict):
            continue
        result.append({
            "name": concept.get("concept_name") or concept.get("name") or "Concepto",
            "summary": concept.get("general_summary") or "",
            "definition": concept.get("definition") or concept.get("specific_definition") or "",
            "page": concept.get("chapter_page") or "",
        })
    return result


def _ids_of(value):
    """Identificadores de una relacion (autores o generos).

    El detalle entrega [{'id': 1, 'name': '...'}]; el formulario de reemplazo
    (PUT) necesita esos identificadores para no perder las relaciones.
    """
    if isinstance(value, list):
        ids = []
        for item in value:
            if isinstance(item, dict) and item.get("id") is not None:
                ids.append(int(item["id"]))
        return ids
    return []


def normalize_book(raw):
    """Unifica la forma del libro entre el catalogo y el detalle.

    La interfaz grafica solo conoce este diccionario, de modo que un campo
    ausente nunca provoca un error: siempre hay un valor por omision.
    """
    raw = raw if isinstance(raw, dict) else {}
    images = _images_of(raw)
    cover = raw.get("cover_image") or (images[0]["url"] if images else None)
    return {
        "isbn": raw.get("isbn") or "",
        "title": raw.get("title") or "(sin titulo)",
        "authors": _authors_text(raw.get("authors")),
        "genres": _authors_text(raw.get("genres")),
        "year": raw.get("publication_year"),
        "price": raw.get("price"),
        "stock": raw.get("stock"),
        "format_name": raw.get("format_name") or "",
        "category_name": raw.get("category_name") or "",
        "format_id": raw.get("format_id"),
        "category_id": raw.get("category_id"),
        "author_ids": _ids_of(raw.get("authors")),
        "genre_ids": _ids_of(raw.get("genres")),
        "cover_image": cover,
        "images": images,
        "image_urls": [image["url"] for image in images],
        "concepts": _concepts_of(raw),
        "raw": raw,
    }

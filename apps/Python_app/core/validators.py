"""Validaciones del lado del cliente.

Repiten las reglas que aplican los microservicios y la base de datos, para que
el usuario reciba el aviso en el formulario en lugar de un error del servidor.

Reglas copiadas de la fuente real (no supuestas):
  - users.email      : formato de correo.
  - users.password   : minimo 8, una mayuscula, una minuscula, un digito y un simbolo.
  - books.isbn       : VARCHAR(20) UNIQUE NOT NULL.
  - books.title      : VARCHAR(200) NOT NULL.
  - books.publication_year : entre 1000 y 2100.
  - books.price      : NUMERIC(10,2) >= 0.
  - books.stock      : entero >= 0.

Validar aqui NO sustituye la validacion del servidor: es solo comodidad. El
servidor sigue siendo la autoridad y sus mensajes se muestran tal cual.
"""

import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

ISBN_MAX = 20
TITLE_MAX = 200
YEAR_MIN, YEAR_MAX = 1000, 2100

PASSWORD_RULES = (
    "Minimo 8 caracteres.",
    "Al menos una letra mayuscula.",
    "Al menos una letra minuscula.",
    "Al menos un digito.",
    "Al menos un simbolo (por ejemplo #, !, $).",
)


class ValidationError(ValueError):
    """Dato invalido detectado antes de enviar la peticion."""


# ------------------------------------------------------------------------------
# Cuentas
# ------------------------------------------------------------------------------
def validate_email(email):
    email = (email or "").strip()
    if not email:
        raise ValidationError("El correo electronico es obligatorio.")
    if not EMAIL_RE.match(email):
        raise ValidationError("El correo electronico no tiene un formato valido.")
    return email.lower()


def validate_password(password):
    """Devuelve None si cumple; si no, el primer incumplimiento."""
    if not password or len(password) < 8:
        return PASSWORD_RULES[0]
    if not re.search(r"[A-Z]", password):
        return PASSWORD_RULES[1]
    if not re.search(r"[a-z]", password):
        return PASSWORD_RULES[2]
    if not re.search(r"\d", password):
        return PASSWORD_RULES[3]
    if not re.search(r"[^A-Za-z0-9]", password):
        return PASSWORD_RULES[4]
    return None


def validate_registration(nombre, apellido_paterno, apellido_materno, email, password, confirm):
    """Valida el formulario de registro completo. Devuelve los datos limpios."""
    nombre = (nombre or "").strip()
    apellido_paterno = (apellido_paterno or "").strip()
    apellido_materno = (apellido_materno or "").strip()

    if not nombre:
        raise ValidationError("El nombre es obligatorio.")
    if not apellido_paterno:
        raise ValidationError("El apellido paterno es obligatorio.")
    if not apellido_materno:
        raise ValidationError("El apellido materno es obligatorio.")

    email = validate_email(email)
    problem = validate_password(password)
    if problem:
        raise ValidationError(f"La contrasena no cumple la politica: {problem}")
    if password != confirm:
        raise ValidationError("Las dos contrasenas no coinciden.")

    return {
        "nombre": nombre,
        "apellido_paterno": apellido_paterno,
        "apellido_materno": apellido_materno,
        "email": email,
        "password": password,
    }


# ------------------------------------------------------------------------------
# Libros
# ------------------------------------------------------------------------------
def parse_number(value, field, allow_empty=False):
    """Convierte texto a float aceptando coma decimal (uso en espanol)."""
    text = str(value or "").strip().replace(",", ".")
    if not text:
        if allow_empty:
            return None
        raise ValidationError(f"El campo '{field}' es obligatorio.")
    try:
        return float(text)
    except ValueError:
        raise ValidationError(f"El campo '{field}' debe ser un numero.")


def parse_int(value, field, allow_empty=False):
    number = parse_number(value, field, allow_empty=allow_empty)
    if number is None:
        return None
    if abs(number - round(number)) > 1e-9:
        raise ValidationError(f"El campo '{field}' debe ser un numero entero.")
    return int(round(number))


def validate_isbn(isbn, required=True):
    isbn = (isbn or "").strip()
    if not isbn:
        if required:
            raise ValidationError("El ISBN es obligatorio.")
        return None
    if len(isbn) > ISBN_MAX:
        raise ValidationError(
            f"El ISBN no puede superar {ISBN_MAX} caracteres (tiene {len(isbn)}). "
            "Ojo: el titulo es el que lleva la matricula, no el ISBN.")
    if " " in isbn:
        raise ValidationError("El ISBN no debe contener espacios.")
    return isbn


def validate_book_form(values, is_new=True):
    """Valida el formulario de alta/edicion de un libro.

    Devuelve el diccionario listo para enviar al microservicio. Cuando
    `is_new` es False no se exige el ISBN (no se modifica) y se devuelven solo
    los campos que el usuario realmente cambio, si `values['__partial__']` trae
    la lista de campos a enviar.
    """
    result = {}

    isbn = validate_isbn(values.get("isbn"), required=is_new)
    if isbn:
        result["isbn"] = isbn

    title = (values.get("title") or "").strip()
    if not title:
        raise ValidationError("El titulo es obligatorio.")
    if len(title) > TITLE_MAX:
        raise ValidationError(f"El titulo no puede superar {TITLE_MAX} caracteres.")
    result["title"] = title

    year = parse_int(values.get("publication_year"), "anio de publicacion")
    if year is None or not (YEAR_MIN <= year <= YEAR_MAX):
        raise ValidationError(f"El anio debe estar entre {YEAR_MIN} y {YEAR_MAX}.")
    result["publication_year"] = year

    price = parse_number(values.get("price"), "precio")
    if price is None or price < 0:
        raise ValidationError("El precio no puede ser negativo.")
    if price >= 10 ** 8:
        raise ValidationError("El precio es demasiado grande (maximo 99,999,999.99).")
    result["price"] = round(price, 2)

    stock = parse_int(values.get("stock", 0), "existencia")
    if stock is None:
        stock = 0
    if stock < 0:
        raise ValidationError("La existencia no puede ser negativa.")
    result["stock"] = stock

    format_id = parse_int(values.get("format_id"), "formato")
    category_id = parse_int(values.get("category_id"), "categoria")
    if format_id is None:
        raise ValidationError("Selecciona un formato.")
    if category_id is None:
        raise ValidationError("Selecciona una categoria.")
    result["format_id"] = format_id
    result["category_id"] = category_id

    # Relaciones: se envian como listas de identificadores.
    result["author_ids"] = [int(i) for i in values.get("author_ids") or []]
    result["genre_ids"] = [int(i) for i in values.get("genre_ids") or []]

    # Imagenes: se admite una URL por linea (la primera sera la portada).
    urls = [line.strip() for line in str(values.get("images_text") or "").splitlines()]
    urls = [url for url in urls if url]
    for url in urls:
        if not url.startswith(("http://", "https://")):
            raise ValidationError(f"La imagen '{url[:40]}' debe iniciar con http:// o https://")
        if len(url) > 255:
            raise ValidationError("La URL de una imagen no puede superar 255 caracteres.")
    result["images"] = [{"image_url": url, "is_cover": index == 0}
                        for index, url in enumerate(urls)]

    return result


def build_partial_update(original, edited):
    """Devuelve solo los atributos que cambiaron (lo que se envia por PATCH).

    Es la pieza que hace visible la diferencia entre PUT y PATCH: aqui se
    calcula el minimo conjunto de cambios, y el formulario de edicion completa
    reutiliza `validate_book_form` para mandar todo.
    """
    changes = {}
    for field in ("title", "publication_year", "price", "stock", "format_id", "category_id"):
        if field in edited and edited[field] != original.get(field):
            changes[field] = edited[field]
    for field in ("author_ids", "genre_ids"):
        if field in edited and sorted(edited[field] or []) != sorted(original.get(field) or []):
            changes[field] = edited[field]
    return changes

# PROMPT 03: Microservicio RESTful en Python/Flask con Psycopg v3 y Swagger
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Institución:** Universidad de Monterrey (UDEM)  
**Semestre:** Primavera 2026  

---

## 1. Objetivo del Prompt
Desarrollar un microservicio RESTful en **Python con Flask** para la gestión programática de la librería, utilizando el driver oficial moderno **`psycopg` (psycopg v3)** para interactuar con la base de datos PostgreSQL en 4FN, con documentación interactiva **Swagger/OpenAPI** y soporte para **CORS**.

---

## 2. Restricciones Técnicas

1. **Ubicación:** `apps/services/soap/app.py`.
2. **Framework:** Flask estándar (código limpio, **sin Blueprints**).
3. **Driver PostgreSQL:** Exclusivamente **`psycopg` (v3)** con `psycopg.rows.dict_row`.
4. **Seguridad de Credenciales:** Variables cargadas vía `python-dotenv` desde `.env` local (`DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`).
5. **CORS:** Configurado mediante `flask-cors`.
6. **Documentación Swagger:** Integrada con `flasgger` accesible en `/docs` o `/apidocs`.
7. **Endpoints Obligatorios:**
   - `GET /books`: Listar libros con autores, géneros, stock y precio.
   - `GET /books/<isbn>`: Obtener detalle completo por ISBN.
   - `GET /books/search`: Búsqueda avanzada por título, autor, género, año, rango de precios.
   - `POST /books`: Crear nuevo libro con relaciones atómicas.
   - `PUT /books/<isbn>`: Actualizar libro existente.
   - `DELETE /books/<isbn>`: Eliminar libro y dependencias.

---

## 3. Entregables Esperados
En `apps/services/soap/`:
- `app.py`
- `.env.example`
- `requirements.txt`

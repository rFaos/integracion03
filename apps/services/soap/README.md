# Módulo de Servicios SOAP, XML/XSLT y Microservicio RESTful (Flask)
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Institución:** Universidad de Monterrey (UDEM)  

---

## 1. Archivos en este Módulo

- `app.py`: Microservicio RESTful en Python Flask con conexión directa a PostgreSQL usando `psycopg` (v3) y documentación OpenAPI/Swagger en `/docs`.
- `requirements.txt`: Dependencias de Python (`flask`, `psycopg[binary]`, `python-dotenv`, `flask-cors`, `flasgger`, `gunicorn`).
- `library.xml` y `library02.xml`: Documentos XML con metadatos de libros y conceptos asociados a `estilo.css`.
- `estilo.css`: Hoja de estilos CSS pura para renderizado nativo de XML en el navegador.
- `library03.xml`: Documento XML estructurado para transformación XSLT con `library03.xsl`.
- `library03.xsl`: Plantilla de transformación declarativa XSLT con lógica de indicadores de stock condicionales (`in-stock`, `low-stock`, `out-stock`).
- `estilo03.css`: Sistema de diseño moderno Dark Mode Glassmorphism para la GUI HTML5 generada por XSLT.
- `.env.example` y `.env`: Configuración segura de credenciales de base de datos (`library_user` / `666`).

---

## 2. Instrucciones de Ejecución del Microservicio Flask

### 2.1 Instalación de Dependencias
```bash
python3 -m venv venv
source venv/bin/activate      # En Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2 Ejecución con Flask CLI (como en clase)
```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001
```

O directamente con Python:
```bash
python app.py
```

### 2.3 Acceso y Documentación Swagger
- **Swagger UI interactivo:** `http://localhost:5001/docs` (o `http://<IP_GCP>:5001/docs`)
- **API Endpoint Base:** `http://localhost:5001/books`
- **Health Check:** `http://localhost:5001/health`

---

## 3. Visualización Local de XML / XSLT
```bash
python3 -m http.server 8080
```
- XML con CSS puro: `http://localhost:8080/library.xml`
- GUI XSLT con Stock Condicional: `http://localhost:8080/library03.xml`

# Requerimientos: Catálogo de Libros en Electron para Windows 11 (04_Electron_app.md)

**Materia:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  
**Universidad de Monterrey (UDEM)** — Primavera 2026  

---

## 📋 Requerimientos del Proyecto

### 1. Interfaz Gráfica Profesional con Cards y Paginación
* Escribe una app de escritorio para **Windows 11** con **Electron** y una **GUI profesional** que muestre el catálogo de libros con sus imágenes usando **Cards**.
* Cada **Card** debe mostrar:
  1. **Imagen del libro** (con fallback elegante ante fallas de carga).
  2. **Autor(es)**.
  3. **ISBN**.
  4. **Stock** (con semáforo condicional: Verde en stock, Amarillo bajo stock, Rojo agotado).
  5. **Año de publicación**.
  6. **Género** / Categoría.
  7. **Precio** con su divisa (`USD`).
* **Implementa paginación y carga por petición** (paginación en demanda, selector de libros por página y buscador en tiempo real).
* **Deposítala en:** `/apps/ElectronApp` (y réplica en `/Electron_app`).

---

### 2. Consumo Exclusivo de XML y Persistencia en LocalStorage
* La app de escritorio para Windows 11 con Electron debe de consumir **EXCLUSIVAMENTE XML** provisto por el microservicio disponible en `http://34.51.8.146:5001/books` (o `http://34.51.75.114:5001/books`), solicitando `?format=XML` y parseándolo estrictamente con `DOMParser`.
* La **URL Base** y el **EndPoint** deben de ser configurables en la app.
* Esta configuración **debe de persistir mediante el uso de `LocalStorage`** para que se mantenga guardada al reiniciar la aplicación.

---

### 3. Documentación y Ejecución
* Incluye los pasos para ejecutar la app en Windows 11 mediante la creación de un archivo llamado **`README.md`**.
* Incluye el archivo **`start.bat`** para ejecución directa de 1 clic en Windows 11 sin bloqueos de PowerShell.

# Catálogo de Libros en Desktop (Electron Windows 11)

**Materia:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  
**Universidad de Monterrey (UDEM)** — Primavera 2026  

---

## 📌 Descripción del Proyecto
Aplicación de escritorio nativa para **Windows 11** desarrollada con **Electron**, diseñada con una interfaz gráfica profesional (*Fluent / Glassmorphism Dark Mode*) que renderiza el catálogo de libros mediante **Cards interactivas**, consumiendo **EXCLUSIVAMENTE datos en formato XML** provistos por el microservicio en la nube desplegado en Google Cloud Platform (`http://34.51.8.146:5001/books`).

---

## 🚀 Requerimientos Funcionales Implementados

1. **Interfaz Gráfica Profesional con Cards:**
   * Cada tarjeta de libro muestra:
     - 🖼️ **Imagen de portada** con carga asíncrona y respaldo ante errores.
     - ✍️ **Autor(es)**.
     - 🏷️ **Código ISBN**.
     - 📦 **Stock disponible** con badges de semáforo condicional (Verde: En Stock, Amarillo: Bajo Stock $\le 5$, Rojo: Agotado $= 0$).
     - 📅 **Año de publicación**.
     - 🏷️ **Género(s)** y categoría.
     - 💲 **Precio** en moneda especificada por el XML (`USD`).
2. **Paginación y Carga por Petición:**
   * Paginación dinámica configurable (4, 6, 8 o 12 libros por página).
   * Botones de navegación *Anterior / Siguiente* y selector directo de páginas.
   * Filtro de búsqueda en tiempo real por título, autor, género o ISBN.
   * Botón de **Recargar** para refrescar los datos bajo demanda.
3. **Consumo Exclusivo de XML:**
   * La aplicación solicita únicamente XML (`Accept: application/xml`) y procesa el árbol de elementos mediante `DOMParser`.
   * Incluye visor interactivo modal para auditar el **Payload XML Crudo**.
4. **Configuración Persistente en LocalStorage:**
   * Tanto la **URL Base** (`http://34.51.8.146:5001`) como el **EndPoint** (`/books`) son configurables desde la barra superior de la aplicación.
   * La configuración se guarda y persiste automáticamente en el almacenamiento local (`localStorage`), manteniendo la personalización entre sesiones de la app.

---

## 🛠️ Pasos para Ejecutar la App en Windows 11

### Método 1: Lanzador Rápido de 1 Clic (Recomendado)
1. Abre el Explorador de Archivos de Windows.
2. Navega hasta la carpeta del proyecto:
   `C:\VSCODEOMG\IntegracionWeb\MonolitoCosa\integracion03\apps\ElectronApp\`
3. Haz doble clic en el archivo **`start.bat`**.
4. ¡Listo! La aplicación se iniciará de inmediato sin problemas de permisos de PowerShell.

---

### Método 2: Desde la Terminal (PowerShell / CMD)
1. Abre una terminal de PowerShell o CMD en la carpeta:
   ```powershell
   cd C:\VSCODEOMG\IntegracionWeb\MonolitoCosa\integracion03\apps\ElectronApp
   ```
2. Ejecuta la aplicación usando `npm.cmd`:
   ```powershell
   npm.cmd start
   ```
   *(O si habilitaste scripts en tu usuario: `npm start`).*

---

## 📂 Estructura de Archivos
```text
apps/ElectronApp/
├── index.html       # Estructura semántica de la GUI y barra de configuración
├── styles.css       # Estilos modernos Windows 11 Glassmorphism Dark Mode
├── renderer.js      # Consumo exclusivo XML, parser DOMParser, paginación y LocalStorage
├── main.js          # Proceso principal de Electron (ventana 1320x900, sin CORS)
├── package.json     # Metadatos y scripts de ejecución
├── start.bat        # Lanzador de un solo clic para Windows 11
└── README.md        # Documentación e instrucciones de instalación y uso
```

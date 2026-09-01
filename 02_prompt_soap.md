# PROMPT 02: Modelado XML, Transformación XSLT y Estilizado CSS
**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Institución:** Universidad de Monterrey (UDEM)  
**Semestre:** Primavera 2026  

---

## 1. Objetivo del Prompt
Modelar y representar los datos del catálogo bibliográfico utilizando estándares de intercambio de datos **XML**, transformación declarativa **XSLT** y estilos **CSS** nativos para renderizado directo en el navegador web y preparación de interfaces orientadas a servicios (SOAP / XML-RPC / REST).

---

## 2. Requisitos Técnicos

1. **Documento XML Estándar (`library.xml`):**
   - Elemento raíz `<library>`.
   - Elementos `<book>` con atributo `isbn` obligatorio.
   - Campos en inglés coherentes con la base de datos: `<title>`, `<authors>`, `<publication_year>`, `<price currency="USD">`, `<stock>`, `<format>`, `<genres>`, `<cover_image>`, `<concepts>`.
   - Asociación a hoja de estilos pura `estilo.css` mediante `<?xml-stylesheet type="text/css" href="estilo.css"?>`.
2. **Transformación XSLT Avanzada (`library03.xml`, `library03.xsl` y `estilo03.css`):**
   - `library03.xml` asociado a `library03.xsl` mediante `<?xml-stylesheet type="text/xsl" href="library03.xsl"?>`.
   - `library03.xsl` genera una interfaz HTML5 responsiva y profesional.
   - **Indicadores Visuales de Stock con Condicionales XSL (`<xsl:choose>`):**
     - `stock > 5` $\rightarrow$ Verde (In Stock).
     - `1 <= stock <= 5` $\rightarrow$ Amarillo/Ámbar (Low Stock).
     - `stock = 0` $\rightarrow$ Rojo (Out of Stock).
   - Renderizado de portadas de libros, autores múltiples, géneros y conceptos clave.

---

## 3. Entregables Esperados
En el directorio `apps/services/soap/`:
- `library.xml` y `estilo.css`
- `library03.xml`, `library03.xsl` y `estilo03.css`

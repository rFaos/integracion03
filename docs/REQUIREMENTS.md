# Matriz de Trazabilidad de Requisitos (SC3705 - Ejercicio 03)

| ID Requisito | Origen | Descripción | Componente / Archivo | Estado de Cumplimiento |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-001** | Prompt 00 | Diseño relacional en 4FN en PostgreSQL | `data/db_schema.sql`, `data/db_design.md` | ✅ 100% Implementado |
| **REQ-002** | Prompt 00 | Regla de Máximo 1 Administrador vía índice parcial | `data/db_schema.sql` (`idx_single_admin`) | ✅ 100% Implementado |
| **REQ-003** | Prompt 01 | Monolito Node/Express/EJS con SSR y cero APIs | `apps/web-monolito01/` | ✅ 100% Implementado |
| **REQ-004** | Prompt 02 | Modelado XML canónico con atributo ISBN | `apps/services/soap/library.xml` | ✅ 100% Implementado |
| **REQ-005** | Prompt 02 | Estilos puros de XML en navegador | `apps/services/soap/estilo.css` | ✅ 100% Implementado |
| **REQ-006** | Prompt 02 | Transformación XSLT con reglas de color de Stock | `apps/services/soap/library03.xsl` | ✅ 100% Implementado |
| **REQ-007** | Prompt 03 | Microservicio Flask con driver psycopg v3 | `apps/services/soap/app.py` | ✅ 100% Implementado |
| **REQ-008** | Prompt 03 | Documentación interactiva Swagger OpenAPI en `/docs` | `apps/services/soap/app.py` (`flasgger`) | ✅ 100% Implementado |
| **REQ-009** | Sesión 04a | Endpoints de catálogo `/api/books`, `/api/book/<isbn>`, etc. | `apps/services/soap/app.py` | ✅ 100% Implementado |
| **REQ-010** | Sesión 04a | Endpoint por autor `/api/book/author/<id>` dual XML/JSON | `apps/services/soap/app.py` | ✅ 100% Implementado |
| **REQ-011** | Sesión 04a | Hoja de estilos de clase `library.css` con colores exactos | `apps/services/soap/library.css`, `library02.xml` | ✅ 100% Implementado |
| **REQ-012** | Prompt 04 | Cliente Electron de escritorio con consumo XML exclusivo | `apps/cliente-electron/` | ✅ 100% Implementado |
| **REQ-013** | Prompt 04 | Captura de Nombre y Apellido del evaluador | `apps/cliente-electron/index.html` | ✅ 100% Implementado |
| **REQ-014** | Prompt 04 | Métodos de clasificación independientes (IaaS, PaaS, SaaS, FaaS) | `apps/cliente-electron/renderer.js` | ✅ 100% Implementado |
| **REQ-015** | Sesión 04 | Módulo SOAP manual (`POST /soap`) y WSDL (`GET /soap?wsdl`) | `apps/services/soap/app.py` | ✅ 100% Implementado |
| **REQ-016** | Sesión 04 | Tablas `clasificadores`, `clasificaciones_cloud`, `clientes_servidos` | `data/db_schema.sql`, `data/library_data.sql` | ✅ 100% Implementado |
| **REQ-017** | Sesión 04 | SOAP Fault 409 por clasificación duplicada | `apps/services/soap/app.py`, `renderer.js` | ✅ 100% Implementado |
| **REQ-018** | Portafolio | Reporte web técnico completo con simulación en vivo y descarga | `html/parcial1/ejercicio3/index.html` | ✅ 100% Implementado |

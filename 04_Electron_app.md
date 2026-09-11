# Requerimientos de la Aplicación de Escritorio Electron (04_Electron_app)

**Materia:** Integración de Aplicaciones Computacionales (SC-2236)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  
**Universidad de Monterrey (UDEM)** — Primavera 2026  

---

## 1. Objetivo General
Diseñar y construir una aplicación de escritorio multiplataforma basada en **Electron** que se integre con el microservicio en la nube (`/apps/services/soap/app.py` desplegado en Google Cloud Compute Engine, IP `34.51.23.80:5001`), consumiendo **exclusivamente datos estructurados en formato XML**.

---

## 2. Requerimientos Funcionales Específicos

### R1. Consumo Exclusivo de Datos en XML
* La aplicación de escritorio debe realizar solicitudes HTTP solicitando y procesando **únicamente XML** (vía `/books/temas?format=XML` o mediante sobres SOAP 1.1 en `/soap`).
* Está **estrictamente prohibido el consumo o parseo de JSON** en la lógica de negocio del clasificador.
* El procesamiento del árbol XML se realiza en el cliente mediante la API nativa `DOMParser` de JavaScript.
* Debe contemplar las directivas de seguridad **CORS** y configurar `webSecurity: false` en `webPreferences` de Electron para permitir peticiones cross-origin a la instancia remota de Google Cloud sin bloqueos de navegador.

### R2. Captura de Datos del Evaluador y Descripción Técnica
* La interfaz gráfica de usuario (GUI) debe proporcionar campos para capturar:
  1. **Nombre(s)** del usuario evaluador.
  2. **Apellido(s)** del usuario evaluador.
  3. **Correo institucional** (para trazabilidad en auditoría y operaciones SOAP).
  4. Un **área de texto (`<textarea>`)** amplia donde el usuario pueda ingresar palabras clave, frases o descripciones técnicas relacionadas con libros y temas de Cloud Computing.

### R3. Motor de Clasificación Modular por Categoría de Servicio Cloud
* La aplicación analiza el texto ingresado por el usuario, cruza los conceptos contra el catálogo temático XML obtenido del microservicio remoto y determina a qué modelo de servicio Cloud corresponde principalmente:
  1. **IaaS (Infrastructure as a Service):** Servidores virtuales, cómputo dedicado, discos en bloque, VPC, subredes, firewalls, particionamiento de hardware.
  2. **PaaS (Platform as a Service):** Runtimes de ejecución, contenedores, orquestadores (Kubernetes, Pods), middleware, bases de datos gestionadas, CI/CD.
  3. **SaaS (Software as a Service):** Software final empaquetado, correo, CRM, ERP, ofimática en la nube, consumo por navegador sin gestión de infraestructura.
  4. **FaaS (Function as a Service / Serverless):** Funciones efímeras disparadas por eventos (triggers, HTTP), microfacturación por milisegundo, escalado automático a cero.
* **Modularidad obligatoria:** El código debe estructurarse mediante **funciones o métodos independientes** y autónomos para cada categoría:
  * `classifyIaaS(text, xmlTopics)`
  * `classifyPaaS(text, xmlTopics)`
  * `classifySaaS(text, xmlTopics)`
  * `classifyFaaS(text, xmlTopics)`
* Cada función debe contener comentarios técnicos exhaustivos explicando la heurística y la lógica de ponderación léxica.

### R4. Retroalimentación Visual y Auditoría en Tiempo Real
* Indicador de estado del servidor en la nube (`Servidor ONLINE / Conectado`, `Error de Conexión`).
* Resultados gráficos con barras de porcentaje de afinidad para las 4 categorías (IaaS, PaaS, SaaS, FaaS).
* Justificación técnica explicativa del resultado ganador.
* Consola interactiva de auditoría en vivo mostrando el **payload XML crudo** recibido del servidor y los eventos del protocolo.

---

## 3. Directorio de Entrega
* **Ruta Solicitada:** `C:\VSCODEOMG\IntegracionWeb\MonolitoCosa\integracion03\Electron_app\` (y réplica en `apps/Electron_app`).
* **Lanzador para Windows:** Incluir archivo `start.bat` para ejecución en 1 solo clic.

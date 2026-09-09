# Cliente de Escritorio Electron - Consumo Exclusivo XML (Prompt 04)

**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Institución:** Universidad de Monterrey (UDEM)  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Profesor:** Dr. Raúl Morales Salcedo  

---

## 1. Descripción
Aplicación de escritorio construida sobre **Electron** que consume **exclusivamente datos en formato XML** provenientes del microservicio desplegado en Google Cloud Platform (`http://34.51.75.114:5001/books/temas?format=XML`).

Permite al usuario ingresar su Nombre y Apellido, escribir frases o descripciones técnicas de Cloud Computing y clasificarlas automáticamente en uno de los 4 modelos principales:
- **IaaS (Infrastructure as a Service)**
- **PaaS (Platform as a Service)**
- **SaaS (Software as a Service)**
- **FaaS (Function as a Service / Serverless)**

El código está estructurado con métodos de clasificación totalmente independientes (`classifyIaaS`, `classifyPaaS`, `classifySaaS`, `classifyFaaS`) y soporte para registro en base de datos mediante sobres **SOAP Envelope (POST /soap)** con detección de **SOAP Fault 409** en caso de duplicados.

---

## 2. Instrucciones de Ejecución en Windows

### Opción Rápida (1 Clic):
Doble clic sobre el archivo `start.bat` en esta carpeta. El script verificará Node.js, instalará Electron si es necesario y abrirá la ventana gráfica.

### Opción Manual desde Terminal:
```bash
cd apps/cliente-electron/
npm install
npm start
```

# Memoria Técnica y Análisis Crítico: Módulo SOAP, WSDL y Paradigmas de Integración

**Curso:** Integración de Aplicaciones Computacionales (SC-2236)  
**Institución:** Universidad de Monterrey (UDEM)  
**Profesor:** Dr. Raúl Morales Salcedo  
**Estudiante:** Fabián Azaed Orta Singlaterry (Matrícula: 613504)  
**Fecha:** 8 de Septiembre, 2026  

---

## 1. Panorama Comparativo de Arquitecturas de Integración

En la Sesión 4 se evaluaron ocho enfoques arquitectónicos para resolver la comunicación entre sistemas distribuidos. A continuación se sintetizan sus dimensiones clave:

| Arquitectura | Creador / Año | Modelo | Formato Payload | Rendimiento | Caso de Uso Óptimo |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **REST** | Roy Fielding (2000) | Recursos + Métodos HTTP | JSON / XML | Medio-Alto | APIs públicas, SaaS, operaciones CRUD desacopladas. |
| **SOAP** | W3C / Dave Winer (1998) | RPC + Contrato Estricto | XML Envelope | Medio | Banca, SWIFT, sanidad (HL7), transacciones distribuidas ACID. |
| **GraphQL** | Facebook (2015) | Grafo de Consultas | JSON | Medio | Frontends complejos que requieren evitar over-fetching. |
| **gRPC** | Google (2015) | RPC Binario (HTTP/2) | Protocol Buffers | Muy Alto | Comunicación inter-microservicios de latencia ultra-baja. |
| **WebSocket** | IETF (2011) | Canal Full-Duplex | Binario / Texto | Muy Alto | Streaming en tiempo real, dashboards bursátiles, chats. |
| **Webhook** | Patrón Industrial (~2007) | Push Reactivo por Eventos | JSON | Alto | Notificaciones asíncronas entre plataformas SaaS (ej. Stripe). |
| **MQTT** | IBM / OASIS (1999) | Publicación / Suscripción | Binario Ultraligero | Muy Alto | Sensores IoT, telemetría automotriz y redes con ancho de banda limitado. |
| **MCP** | Anthropic (2024) | Descubrimiento de Tools | JSON-RPC | Alto | Integración de contexto y ejecución de herramientas para Agentes de IA. |

---

## 2. Respuestas Fundamentadas a las 16 Preguntas de Reflexión (Sesión 04)

### 1. ¿Qué pasaría si mañana agregas un cuarto campo a `RegistrarClasificacion` sin avisar a nadie? ¿Se rompería algún cliente existente? ¿Por qué SOAP es tan estricto con esto?
**Respuesta:**  
En SOAP, el contrato WSDL y el esquema XSD determinan de manera vinculante la estructura del mensaje XML. Si un cliente fue generado a partir del WSDL original (mediante herramientas como `wsimport` en Java o `dotnet-svcutil` en .NET), su deserializador estricto rechazará el mensaje con un `SchemaValidationException` o `SOAPFaultException` si recibe campos inesperados no declarados en `<xsd:sequence>` o si falta un elemento obligatorio. A diferencia de JSON en REST donde los campos adicionales simplemente se ignoran (Postel's Law / Robustness Principle), SOAP impone tipado estricto porque fue diseñado para transacciones empresariales donde cualquier ambigüedad en el payload representa un riesgo legal o financiero inaceptable.

### 2. Miraste el WSDL de tu propio servicio: ¿qué información expone que un atacante podría aprovechar? ¿Ocultarías algo si esto fuera un servicio real de producción?
**Respuesta:**  
El archivo WSDL expone la topología completa del servicio: nombres de métodos internos (`RegistrarClasificacion`), estructura exacta de las entidades (`nombre`, `apellidos`, `correo`, `isbn`, `concept_id`), tipos de datos de base de datos (`xsd:int`, `xsd:string`), enumeraciones de negocio (`IaaS`, `PaaS`, `SaaS`, `FaaS`) y la ubicación física del endpoint (`http://34.51.8.146:5001/soap`). Un atacante puede utilizar este mapa para realizar reconocimiento automatizado, inyección de datos malformados o ataques dirigidos de denegación de servicio. En producción se ocultaría el WSDL público detrás de un API Gateway que requiera mTLS o token previo, se deshabilitaría la ruta `?wsdl` pública y se ofuscarían nombres internos de esquemas.

### 3. Construiste el Envelope a mano con `xml.etree`. ¿Qué partes del mensaje son "boilerplate" (siempre iguales) y cuáles cambian por operación? ¿Qué ganarías usando una librería como Spyne en vez de construirlo tú mismo?
**Respuesta:**  
- **Boilerplate invariable:** Los encabezados XML `<?xml version="1.0"?>`, las declaraciones de namespaces (`xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"`), las etiquetas estructurales envolventes `<soap:Envelope>`, `<soap:Header>` y `<soap:Body>`.
- **Dinámico:** El nombre del elemento hijo dentro de `<soap:Body>` (ej. `<m:ObtenerConceptosPendientesResponse>` vs `<m:RegistrarClasificacionResponse>`) y el payload específico de cada operación.
- **Ventaja de Spyne:** Automatiza la serialización/deserialización, genera el WSDL dinámicamente según decoradores `@rpc`, maneja validaciones XSD de tipos nativos y despacha excepciones como `Fault` sin tener que concatenar ni estructurar nodos `ElementTree` manualmente.

### 4. ¿Por qué crees que el WSDL define tipos con XML Schema (`xsd:string`, `xsd:int`) en lugar de simplemente confiar en el texto plano?
**Respuesta:**  
Porque SOAP busca **interoperabilidad agnóstica de lenguaje a nivel de compilador**. Un entero en Python es dinámico, en Java es `int` de 32 bits y en C# es `System.Int32`. Al declarar `xsd:int`, los generadores de código cliente en cualquier lenguaje pueden instanciar tipos nativos fuertemente tipados con chequeo en tiempo de compilación. Si se enviara texto plano, cada desarrollador de cliente tendría que escribir código defensivo de parseo, incrementando la probabilidad de errores en tiempo de ejecución (`NullPointerException`, conversiones fallidas).

### 5. Compara el tamaño en bytes de una petición `RegistrarClasificacion` en SOAP contra el mismo dato en JSON. ¿Vale la pena ese overhead? ¿Cuándo sí y cuándo no?
**Respuesta:**  
- **SOAP Envelope XML:** ~540 bytes (incluyendo tags de apertura/cierre `<soap:Envelope>`, namespaces, `<soap:Body>`, `<m:RegistrarClasificacionRequest>` y nombres de etiquetas extensos).
- **REST JSON:** ~160 bytes (`{"nombre":"Fabian","correo":"...","modelo":"IaaS"}`).
- **Overhead:** SOAP representa aproximadamente un **230% a 300% más de bytes transferidos**.
- **¿Vale la pena?:**
  - **SÍ:** En transacciones bancarias, transferencias financieras interbancarias (SWIFT/SEPA) o registros médicos (HL7) donde se requiere firma digital a nivel de mensaje (WS-Security XML-Signature) y validación criptográfica antes de tocar la capa de aplicación.
  - **NO:** En aplicaciones web móviles, streaming de datos, microservicios orientados al consumidor o clientes con ancho de banda celular limitado.

### 6. Implementaste SOAP Fault para "ya clasificado" y "concepto inexistente". ¿Por qué SOAP mete los errores dentro del Body en vez de usar solo el código de estado HTTP, como hace REST?
**Respuesta:**  
Porque SOAP fue diseñado bajo el principio de **independencia del transporte**. Un mensaje SOAP puede transmitirse sobre HTTP, HTTPS, pero también sobre **SMTP (correo electrónico), JMS (Java Message Service) o TCP puro**. Ni SMTP ni TCP cuentan con códigos de estado HTTP como 400, 404 o 500. Al encapsular la excepción dentro de `<soap:Body><soap:Fault>`, el error viaja intacto independientemente del protocolo de transporte subyacente.

### 7. Si tu app de escritorio recibe un Fault, ¿cómo debería reaccionar la interfaz gráfica? ¿Es lo mismo un error 400 (Client) que uno 500 (Server) desde el punto de vista del usuario final?
**Respuesta:**  
- **Error 400 (`Client / Faultcode: soap:Client`):** El problema radica en la entrada del usuario (ej. campo obligatorio vacío, concepto ya evaluado). La interfaz debe resaltar el campo en color ámbar/rojo con un mensaje comprensible (ej. *"Este concepto ya fue clasificado previamente por usted; seleccione otro título."*) permitiendo corregir y reintentar inmediatamente.
- **Error 500 (`Server / Faultcode: soap:Server`):** El error es una falla de infraestructura o base de datos inalcanzable. La interfaz debe alertar con un mensaje amigable pero no técnico (ej. *"El servicio central de clasificación no responde temporalmente. Intente más tarde o verifique su conexión."*) y habilitar reintentos con retroceso exponencial.

### 8. ¿Por qué crearon una tabla `clasificadores` separada de `users` del monolito, en lugar de reutilizar `users`? ¿Qué hubiera pasado si intentaban insertar ahí directamente?
**Respuesta:**  
1. **Regla de Negocio Crítica del Monolito:** La tabla `users` posee una restricción relacional estricta mediante el índice único parcial `idx_single_admin ON users (role) WHERE role = 'Administrador'`, y está reservada para el control de acceso y credenciales hash `bcrypt` de la administración del catálogo.
2. **Principio de Aislamiento de Dominios:** Los evaluadores/clasificadores representan actores externos que interactúan a través de clientes de escritorio o llamadas distribuidas sin acceso al panel web del monolito.
3. **Consecuencia de insertar en `users`:** Si se hubiera intentado registrar a cada clasificador en `users`, se hubiera violado el principio de responsabilidad única, se habrían requerido campos ficticios de contraseña o roles no previstos, arriesgando la integridad del acceso administrativo del sistema monolítico.

### 9. Si el monolito cambiara su esquema de `books` mañana (por ejemplo, renombrando `isbn`), ¿qué tan frágil es tu módulo SOAP ante ese cambio? ¿Cómo lo protegerías?
**Respuesta:**  
Actualmente, el módulo SOAP realiza consultas SQL directas sobre `books.isbn`. Si la columna cambia de nombre, el servicio fallaría inmediatamente con un error `column does not exist`.  
**Estrategia de Protección de Ingeniería:**
1. Crear una **Vista de Base de Datos (View)** o un esquema lógico de fachada en PostgreSQL (ej. `CREATE VIEW v_catalog_books AS SELECT book_code AS isbn, title FROM books;`).
2. Implementar una capa de acceso a datos parametrizada (Repository Pattern) que desacople la persistencia física del modelo canónico SOAP.
3. En entornos de producción, el módulo SOAP consumiría una API interna o un evento de integración en lugar de consultar tablas compartidas directamente (Patrón Database-per-Service).

### 10. Tu servicio ahora mismo no valida quién llama. ¿Qué pasaría si cualquiera en la red pudiera invocar `RegistrarClasificacion`? ¿Dónde encaja WS-Security aquí?
**Respuesta:**  
Cualquier cliente no autenticado podría enviar miles de solicitudes, saturando la tabla `clasificaciones_cloud` con datos espurios (Spam/Poisoning) o alterando las métricas institucionales de clientes servidos.  
**Encaje de WS-Security:**  
El estándar OASIS WS-Security permite insertar dentro del `<soap:Header>` elementos `<wsse:Security>` con:
- `<wsse:UsernameToken>`: credenciales cifradas del evaluador con timestamp y nonce anti-replay.
- Cifrado XML (XML-Encryption) para proteger la confidencialidad en tránsito sobre cualquier canal.
- Firmas XML (XML-Signature) para asegurar el no-repudio: nadie puede clasificar haciéndose pasar por otro usuario.

### 11. ¿Confiarías en el campo `correo` que manda el cliente para identificar al usuario, sin ninguna verificación adicional? ¿Por qué es o no es suficiente para este ejercicio?
**Respuesta:**  
- **Para este ejercicio académico:** Es suficiente porque el objetivo didáctico es comprender el flujo de mensajes XML, la validación del esquema y el disparo de excepciones `Fault` ante restricciones de unicidad compuestas `(clasificador_id, concept_id)`.
- **Para un entorno de producción real:** Jamás se confiaría en un campo de texto simple sin verificación, ya que permitiría suplantación de identidad (Identity Spoofing). Se requeriría autenticación mediante tokens JWT firmados, OAuth2 OpenID Connect o validación de firma digital corporativa.

### 12. Si tuvieras que explicarle a alguien que nunca ha visto SOAP por qué querría usar esto en vez de simplemente hacer un POST con JSON, ¿qué le dirías?
**Respuesta:**  
*"Imagina que tienes que conectar dos bancos de diferentes países que mueven millones de dólares. Si usas JSON, cualquiera de los dos lados puede cambiar una letra en un campo sin avisar y todo se rompe silenciosamente en producción. SOAP es como un contrato notariado en papel oficial (el WSDL): antes de que el dinero se mueva, ambos sistemas validan matemáticamente cada letra, cada tipo de dato y cada regla de seguridad. SOAP sacrifica velocidad y ligereza a cambio de certeza absoluta y seguridad no negociable."*

### 13. Del 1 al 10, ¿qué tan doloroso fue construir el XML a mano comparado con lo que imaginas que sería en REST? Anota ese número.
**Respuesta:**  
**Calificación: 8.5 / 10 en dolor de desarrollo.**  
La construcción manual de XML mediante `xml.etree` exige gestionar manualmente namespaces, nombres calificados (`{http://...}Tag`), jerarquías de elementos hijos, conversiones explícitas a string de valores numéricos/nulos y escapes de caracteres especiales (`&`, `<`, `>`). En contraste, en una API REST con JSON en Flask o Express, un diccionario de datos nativo se convierte automáticamente con `jsonify(dict)` en una sola línea de código legible.

### 14. ¿En qué momento de tu carrera profesional crees que te vas a topar con SOAP en un sistema real? ¿Qué tipo de organización lo seguiría usando en 2026 y por qué?
**Respuesta:**  
Nos toparemos con SOAP al integrarnos con:
1. **Sistemas Gubernamentales y Fiscales:** Facturación electrónica (SAT en México vía CFDI y PACs, DIAN en Colombia, SII en Chile) que utilizan SOAP obligatorio para timbrado fiscal con firma XML-DSig.
2. **Instituciones Financieras y Bancarias:** Mensajería SWIFT, pasarelas de pago legacy de bancos centrales y compensación interbancaria.
3. **Sector Salud:** Interfaces HL7 v3 y DICOM en hospitales.
4. **ERPs Industriales:** SAP NetWeaver y Oracle E-Business Suite para transacciones distribuidas con garantía ACID (Two-Phase Commit vía WS-AtomicTransaction).

### 15. ¿Qué parte del protocolo SOAP te pareció innecesariamente compleja, y qué parte te pareció que realmente resuelve un problema legítimo?
**Respuesta:**  
- **Innecesariamente compleja:** La verbosidad extrema de los namespaces XML anidados, la especificación de codificación RPC/encoded vs Document/literal, y la dificultad para inspeccionar o depurar mensajes en consola sin herramientas especializadas (como SoapUI).
- **Problema legítimo que resuelve:** El contrato WSDL y la especificación de excepciones estructuradas (`SOAP Fault` con `<detail>` tipado). Permite a clientes en lenguajes fuertemente tipados (C#, Java) capturar errores de negocio como excepciones nativas de código en lugar de inspeccionar strings en un cuerpo HTTP 200/400.

### 16. Conclusión de Ingeniería
**Respuesta:**  
La transición de SOAP a REST (y en el futuro a gRPC y Agentes con MCP) no representa una descalificación de los estándares previos, sino una evolución hacia la especialización: SOAP reina en transacciones rígidas reguladas; REST domina el ecosistema web público; gRPC lidera la eficiencia de cómputo en la nube; y los clientes modernos como Electron permiten unificar ambos mundos mediante interfaces accesibles y reactivas.

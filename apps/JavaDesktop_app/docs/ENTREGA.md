# Library Desktop: aplicación Java cliente de Library con rastreo GPS

Fabián Azaed Orta Singlaterry, 613504. SC-2236, UDEM.

El código está en el monorepo `integracion03`:
- `apps/JavaDesktop_app`: la aplicación de escritorio (JavaFX).
- `apps/services/rastreo`: el servidor de rastreo (Flask + Flask-Sock) que agregué para el seguimiento.

---

## A. Explicación de la aplicación

### Objetivo
La idea es tener una aplicación de escritorio en Java que use los mismos microservicios de Library que hemos hecho en el semestre (login, users, libros, autores, pedidos y pagos) para comprar libros. Además, el cliente puede seguir su pedido en un mapa de Monterrey que se va moviendo en tiempo real con WebSockets.

### Arquitectura

```
 JavaDesktop_app (JavaFX)
   ├── REST/JSON con Authorization: Bearer <JWT>
   │      login :5000   libros/soap :5001   users :5002   autores :5003
   │      pedidos :5004   pagos :5005          (todos usan PostgreSQL)
   └── WebSocket (java.net.http) con el JWT en el handshake
          rastreo :5006 (Flask-Sock)  ──►  le pregunta a pedidos si el pedido es del usuario
   WebView: map.html con Leaflet + OpenStreetMap
```

La app nunca se conecta a PostgreSQL. Todo pasa por los servicios. El WebSocket lo abre Java y no el mapa: cada mensaje que llega lo paso al mapa con `executeScript()`, y el mapa solo dibuja.

### Tecnologías
- Java 21 y JavaFX 21 (controls y web).
- `java.net.http.HttpClient` para REST y `java.net.http.WebSocket` para el rastreo. No usé librerías externas; el JSON lo leo con una clase pequeña (`Json.java`).
- Leaflet 1.9.4 con mapas de OpenStreetMap dentro de un WebView.
- Flask + Flask-Sock para el servidor de rastreo, basado en mi proyecto GpsWebSockest. De ahí también tomé las 5 rutas por calles reales de Monterrey.
- Los servicios corren en la VM de GCP (34.51.29.27) con PostgreSQL. Las URLs se cambian en `config.properties`.

### Servicios que consume la app
| Servicio | Endpoints | Para qué lo uso |
|---|---|---|
| login | `GET /captcha`, `POST /login`, `GET /session`, `POST /logout` | Iniciar sesión, obtener el JWT, ver los datos de la sesión, cerrar sesión |
| users | `GET /users/{id}`, `GET /users` | Ver mi perfil; la lista completa es solo para administradores |
| libros | `GET /books`, `GET /books/search?q=`, `GET /books/{isbn}`, `GET /books?isbn=` | Catálogo, búsqueda por título, detalle y revisar precio y stock antes de comprar |
| autores | `GET /autores/{id}` | Biografía, país y libros del autor |
| pedidos | `POST /pedidos`, `GET /pedidos`, `GET /pedidos/{id}` | Crear el pedido y ver Mis compras |
| pagos | `POST /pagos`, `GET /pedidos/{id}/pagos` | Pago simulado y su estado |
| rastreo | `POST /rastreo`, `GET /rastreo`, `GET /rastreo/{codigo}`, `WS /ws/rastreo/{codigo}` | Código de rastreo y posición del vehículo |
| libros (SOAP) | `GET /wsdl`, `POST /soap` | Demostración de SOAP/XML |

Los endpoints los saqué del código de cada servicio. Pedidos y pagos no tienen nada de envíos, así que el rastreo lo hice como un servicio aparte que no cambia sus contratos ni toca la base de datos.

### Autenticación con JWT
1. La pantalla de login pide el CAPTCHA (`GET /captcha`), porque el servicio no deja iniciar sesión sin él.
2. Se manda `POST /login?format=json` con correo, contraseña y la respuesta del CAPTCHA. El servicio regresa el `access_token`, su fecha de expiración y los datos del usuario.
3. El token se guarda solo en memoria y se envía como `Authorization: Bearer <token>` en todo lo protegido. Arriba se ve el nombre del usuario, su rol y cuánto le queda al token.
4. Si el token expira, o si cualquier servicio responde 401, la app cierra el WebSocket, borra el token y regresa al login con un aviso.
5. El botón de usuarios solo se activa para administradores. Aun así, el que decide es el servicio, que regresa 403 si el usuario no tiene permiso.

### Cesta y compra
La cesta está en memoria. Se pueden agregar libros, subir o bajar cantidades, eliminar y vaciar, y se ven el precio unitario, el subtotal y el total. No deja pedir más unidades de las que hay en stock.

Al confirmar la compra:
1. Se elige el método de pago. Es simulado y no se piden datos de tarjeta.
2. Se revisa cada libro otra vez con `GET /books?isbn=`. Si el precio cambió se actualiza, y si ya no hay stock se detiene la compra.
3. `POST /pedidos` con las líneas (`book_id` y `cantidad`). El servicio descuenta el stock y guarda el precio.
4. `POST /pagos` con `estado: Aprobado`. En la misma operación el servicio pasa el pedido a *Pagado*.
5. Se consulta `GET /pedidos/{id}` para ver el estado real. No se da por hecho que el pago salió bien.
6. Solo si el pedido quedó *Pagado* se pide el código de rastreo.

### Código de rastreo
El código tiene la forma `LIB-MTY-<año>-<id del pedido a 6 dígitos>`, por ejemplo `LIB-MTY-2026-000125`. Como sale del id real del pedido, no se repite. El servidor guarda qué código va con qué pedido y qué ruta le toca. Cada pedido usa una ruta distinta según su id, así que no siempre se ve el mismo recorrido.

En **Mis compras** salen todos mis pedidos con el estado, el pago, el total y el código. Al seleccionar uno se ven los libros que lleva, y desde ahí se abre el rastreo. También se puede escribir el código en la pestaña Rastreo para consultarlo otra vez.

### Seguimiento por WebSockets
- **Seguridad:** el servidor de rastreo no tiene su propia base ni conoce el secreto del JWT. Cada vez que alguien pide un rastreo, reenvía el mismo token a `pedidos` (`GET /pedidos/{id}`). Si pedidos dice 401 (token malo o vencido) o 403 (el pedido es de otra persona), el rastreo también se niega. Mientras el socket está abierto, el token se vuelve a revisar cada minuto.
- **Mensajes:** al conectar, el servidor manda primero la ruta completa y lo que ya se recorrió; así, si te reconectas no se pierde el avance. Después manda la posición cada segundo (lat, lng, estado y progreso).
- **Estados:** Pedido confirmado, Preparando pedido, Pedido enviado, En ruta de entrega y Entregado. *Entregado* solo aparece cuando el vehículo llega al último punto de la ruta, no por tiempo.
- **Mapa:** la ruta planeada va punteada, lo recorrido en azul, y aparecen el almacén, el destino y el camión 🚚 con su estado. A un lado se ven el estado, las coordenadas, el porcentaje y los mensajes que van llegando.

### Cómo se ejecuta
```bat
cd integracion03\apps\services\rastreo
pip install -r requirements.txt
set PEDIDOS_BASE_URL=http://127.0.0.1:5004
python app.py

cd integracion03\apps\JavaDesktop_app
run.bat
```
`run.bat` descarga JavaFX si no está, compila y abre la app. En GCP hay que abrir el puerto 5006 para el rastreo.

### Evidencias
Las capturas están en `docs/evidencias/`. Las tomé corriendo la app contra los servicios reales (login, libros, users, autores, pedidos, pagos y rastreo) con PostgreSQL:

| Captura | Qué muestra |
|---|---|
| `01_login.png` | Login con CAPTCHA |
| `02_catalogo.png` | Catálogo con portadas, autores, precio, ISBN y disponibilidad |
| `03_detalle_libro_autores.png` | Detalle del libro con descripción y autores |
| `04_busqueda_titulo.png` | Búsqueda por título |
| `05_cesta.png` | Cesta con cantidades, subtotales y total |
| `06_compra_confirmada.png` | Pedido creado, pago aprobado y código de rastreo |
| `07` a `10_rastreo_*.png` | Rastreo en el mapa: preparando, en ruta y entregado |
| `11_mis_compras.png` | Mis compras con el estado del pedido y del pago, el código y los libros |
| `12_perfil_users.png` | Perfil obtenido del servicio users |
| `13_soap_xml.png` | Llamada SOAP al servicio de libros |
| `14_sesion_expirada.png` | Token vencido: la app regresa al login |

También probé el servidor de rastreo por separado: un pedido ajeno regresa 403, un token inválido regresa 401, y los estados avanzan en orden hasta *Entregado* en el último punto.

---

## B. Reflexión sobre tecnologías de integración

**REST.** Los libros, el login, los pedidos y los pagos son recursos con operaciones claras, y REST encaja muy bien: GET para consultar el catálogo, POST para iniciar sesión, crear pedidos o registrar pagos. Como todo es JSON por HTTP, el mismo backend lo usan la app de Python, la de Electron y ahora la de Java sin cambiar nada. Si cada aplicación se conectara directo a la base de datos, todas tendrían que conocer el esquema y tener la contraseña de PostgreSQL. Además, cada una tendría que repetir reglas como descontar stock sin errores, guardar el precio del pedido o cobrar y marcar el pedido como pagado al mismo tiempo. Con los servicios esas reglas están en un solo lugar, protegidas con JWT y roles, y se puede cambiar la base sin romper a los clientes.

**WebSockets.** El camión cambia de posición cada segundo, y el que sabe cuándo cambia es el servidor. Con WebSocket la conexión se queda abierta y el servidor manda cada posición en cuanto la tiene, con muy poco peso por mensaje. Si lo hiciera con REST, la app tendría que preguntar a cada rato aunque no hubiera cambios. Cada pregunta es una petición completa con encabezados y token, se llena el servidor de peticiones inútiles y el camión se mueve a saltos, porque siempre hay retraso entre consultas.

**SOAP.** REST es un estilo que usa los métodos de HTTP sobre recursos, casi siempre con JSON y sin un contrato obligatorio. SOAP es un protocolo con mensajes XML muy estrictos y un contrato formal (WSDL), y trae estándares para seguridad y confiabilidad a nivel de mensaje. Conviene en bancos, aseguradoras, gobierno (como la facturación con el SAT) o cuando hay que conectarse con sistemas viejos o ERPs como SAP, donde importa más tener un contrato fijo y validado que la ligereza. En Java se puede integrar generando las clases desde el WSDL con JAX-WS (`wsimport`) o Apache CXF, o mandando el XML a mano por HTTP. En esta app hice lo segundo: leo el `/wsdl` del servicio de libros y mando un sobre SOAP a `/soap`.

**GCP.** Tener los servicios en una VM de GCP hace que estén disponibles siempre y desde cualquier lugar con una IP pública, sin depender de que mi computadora esté prendida, y se pueden escalar si hace falta. Que la app esté en mi computadora y los servicios en la nube tiene consecuencias:
- **Disponibilidad:** si la VM se apaga o falla el internet, la app no puede hacer nada, así que tiene que avisar bien qué servicio falló. La mía dice cuál y en qué URL.
- **Seguridad:** el tráfico pasa por internet. Ahora va por HTTP normal, y lo correcto sería HTTPS/WSS, abrir solo los puertos necesarios y usar tokens que duren poco.
- **Latencia:** cada petición tarda más que en local, por eso las peticiones van en otro hilo para no congelar la ventana.
- **Escalabilidad:** se pueden poner más instancias o una base administrada. Para eso, el rastreo tendría que guardar su estado en Redis y no en un archivo.

**PostgreSQL.** Es donde vive toda la información de Library: usuarios, roles, libros, autores, stock, pedidos y pagos. Además asegura que las operaciones se hagan completas o no se hagan, por ejemplo que no se cobre un pedido sin marcarlo como pagado, o que dos personas no compren el último libro al mismo tiempo. Lo deben usar los servicios y no la app de Java porque así la contraseña de la base nunca sale del servidor, las reglas y los permisos siempre se aplican (un usuario solo ve sus pedidos) y el puerto de la base no queda expuesto a internet. Si la app mandara SQL directo, cualquiera podría saltarse las reglas.

**Comparación.** REST es pregunta y respuesta, sin estado, bueno para operaciones puntuales. WebSocket deja un canal abierto en los dos sentidos, bueno cuando el servidor tiene que estar mandando datos. SOAP también es pregunta y respuesta, pero con un contrato XML estricto, más pesado y más formal. Para este proyecto usaría:
- REST con JWT (y HTTPS) para la autenticación.
- REST para el catálogo, porque es público y se puede guardar en caché.
- REST para los pagos; si un banco lo pidiera, SOAP con WS-Security.
- WebSocket para el rastreo GPS.

---

## C. Reflexión sobre el uso de inteligencia artificial

**Herramienta.** Usé Claude Code dentro de VS Code y la terminal.

**En qué me apoyé.** Para revisar rápido el código de los servicios y sacar las rutas y los JSON que esperan, para la estructura de la interfaz en JavaFX, para la parte de pasar los mensajes del WebSocket al mapa de Leaflet, para adaptar el servidor de GpsWebSockest a los pedidos y para ordenar este documento.

**Instrucciones que más sirvieron.** Pedirle que no inventara rutas y que todo saliera del código de los servicios, y que si algo no existía lo documentara e hiciera lo mínimo necesario. Por eso salieron cosas que el enunciado no dice: el login pide CAPTCHA, los servicios regresan XML si no pones `?format=json`, la búsqueda de libros regresa `results` y no `books`, y el pago aprobado ya pasa el pedido a *Pagado*.

**Errores y limitaciones.** Al principio la búsqueda estaba leyendo la clave equivocada. Sin el CAPTCHA el login daba error 400. Los servicios de GCP estaban apagados, así que tuve que levantarlos en local para probar. Como Redis no estaba prendido, para las pruebas locales usé la opción `REDIS_REQUIRED_FOR_AUTH=false` que ya tienen los servicios. Además, cada servicio regresa los errores con un formato distinto.

**Qué cambié para que funcionara.**
- Leer los dos formatos de error.
- Tratar cualquier 401 como sesión vencida.
- Revisar precio y stock antes de crear el pedido.
- Generar el código solo después de confirmar que el pedido quedó pagado.
- Hacer que el rastreo le pregunte a pedidos si el pedido es del usuario, en vez de copiar el secreto del JWT a otro servicio.

**Qué entendí mejor.**
- La diferencia entre autenticar y autorizar: el login da el token, pero cada servicio decide qué puedes ver con él.
- Por qué conviene que el WebSocket lo maneje Java y el mapa solo dibuje.
- Por qué la app no debe tocar la base.
- Que un servicio nuevo se puede apoyar en otro reenviando el token del usuario.

**Qué podría hacer sin IA.** El cliente REST con `HttpClient`, la cesta y los cálculos, los estados del pedido y el servidor de Flask-Sock, porque ya lo había hecho en GpsWebSockest. Donde sí me costaría más es en el diseño de JavaFX (CSS y WebView) y en la comunicación entre Java y JavaScript.

---

## D. Entrega
`Fabian_Azaed_Orta_Singlaterry_613504_JavaDesktop.zip`, con el monorepo sin `venv`, `node_modules`, `.git`, `.env` ni los zips anteriores.

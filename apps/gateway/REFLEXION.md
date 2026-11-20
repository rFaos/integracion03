# Reflexión — Implementación del Reverse Proxy con nginx

**SC3705 · Sesión 08** · Fabián Azaed Orta Singlaterry · 613504

## 1. Cómo fue la implementación

Partí de un problema concreto: las tres apps de escritorio conocían **siete direcciones**
cada una (login 5000, libros 5001, users 5002, autores 5003, pedidos 5004, pagos 5005 y
rastreo 5006). Cambiar la IP de la VM de Google Cloud —que ya cambió varias veces durante
el semestre— obligaba a editar Electron, Python y Java por separado.

Elegí **nginx** en lugar de escribir un gateway propio porque el objetivo era un reverse
proxy y nginx resuelve las piezas pedidas solo con configuración: enrutamiento por
prefijo, balanceo, salud pasiva, timeouts, límites por IP y registro. El trabajo fue en
este orden:

1. **Tabla de rutas por prefijo** (`/api/<servicio>/`). La barra final en
   `proxy_pass http://books_svc/;` quita el prefijo, así que los servicios reciben la
   misma ruta de siempre y **no se tocó su lógica**.
2. **Upstreams en un archivo aparte**. La tabla de rutas es la misma en Docker Desktop
   (mi PC) y en la VM; solo cambia `upstreams.docker.conf` ↔ `upstreams.local.conf`.
3. **Segunda instancia de Libros** en :6001 (misma app, otra variable `PORT`) y round
   robin. Aquí apareció el primer detalle: con `worker_processes auto` cada worker lleva
   su propio turno y el reparto salía `5001, 5001, 5001, 6001…`. Con `zone books_svc 64k`
   el estado se comparte y el reparto quedó perfecto: `5001, 6001, 5001, 6001…`.
4. **Errores en JSON**, `X-Request-ID`, formato de log y límite de tasa.
5. **Apps**: solo cambiaron su URL base. Python ya tenía las URL en configuración;
   le agregué `use_gateway`/`gateway_port` para que el botón *Usar remoto* arme
   `http://<IP>:8080/api/<svc>` en vez de un puerto por servicio. En Java bastó con
   `config.properties` (incluido el WebSocket). En Electron, el valor por defecto.
6. **Pruebas** funcionales, de falla y de carga, y el script de despliegue en GCP.

El segundo detalle, el más instructivo: en Docker Desktop `host.docker.internal` (y
`host-gateway`) resuelve a **IPv4 e IPv6**. nginx tomó cada nombre como *dos* servidores,
y como los servicios Flask solo escuchan IPv4, la mitad de los intentos daba 502. Con la
instancia :5001 apagada hubo una petición que probó :5001 (IPv4) y :6001 (IPv6), ambas
fallaron, y el cliente recibió 503 aunque :6001 estaba sana. Lo resolví con
`docker-start.sh`, que resuelve **solo la IPv4** al arrancar el contenedor. Después de eso
la prueba de falla dio 6/6 respuestas 200.

## 2. Ventajas identificadas

- **Un solo punto de entrada.** Las apps pasaron de 7 direcciones a 1 host:puerto. Mover
  la VM ahora es cambiar una IP, no siete puertos en tres apps.
- **Superficie de ataque menor.** En la VM se expone solo `tcp:8080`; los servicios
  escuchan en `127.0.0.1`. Antes había siete puertos abiertos al internet.
- **Alta disponibilidad de Libros sin que las apps lo sepan.** Apagué :5001 en plena
  prueba y ninguna petición falló; nginx reintentó en :6001 y apartó la instancia caída.
- **Políticas comunes en un solo lugar.** Límite de tasa (la ráfaga de 40 peticiones al
  login produjo 31 respuestas 429 sin que el servicio las viera), timeouts y formato de
  error uniforme en JSON.
- **Trazabilidad.** Cada petición lleva `X-Request-ID` de ida y vuelta y deja una línea
  con instancia, código y tiempo; con eso encontré en segundos qué instancia atendió qué.
- **Cero cambios de lógica** en microservicios y apps: el estilo de prefijo permitió
  migrar solo cambiando direcciones.
- **WebSocket incluido.** El rastreo GPS de la app Java funcionó por el mismo puerto con
  dos cabeceras (`Upgrade`, `Connection`).

## 3. Desventajas y retos encontrados

- **Latencia extra.** Con Locust, `GET /books` pasó de p50 8 ms / p95 21 ms (directo) a
  p50 14 ms / p95 32 ms (gateway). Es un salto de red más; en mi PC además cruza la red
  virtual de Docker Desktop. En la VM, con nginx nativo y `keepalive` a los upstreams,
  debería ser menor. El RPS fue el mismo (~19/s) y sin fallos.
- **Punto único de falla.** Si nginx cae, caen las tres apps a la vez. Mitigación:
  `restart: unless-stopped` / `systemctl enable`, y en producción dos instancias de nginx
  detrás de un balanceador de Google Cloud.
- **Detalles de red difíciles de ver.** El problema IPv4/IPv6 no aparece en la
  documentación de las diapositivas y solo se notó al provocar una falla. Sin la prueba
  de falla habría pasado como "funciona".
- **El límite de tasa es por IP.** Todas las pruebas de Locust salen de la misma IP; en
  una red escolar con NAT, varios usuarios legítimos compartirían cuota. Hay que
  calibrarlo (dejé 30 r/min para login y 20 r/s para el resto).
- **CORS y JWT siguen en cada servicio.** No los moví al gateway para no tocar la lógica de
  los microservicios; nginx podría centralizar CORS, pero duplicar cabeceras rompe los
  navegadores. Defensa en profundidad: aunque el gateway validara el JWT, los servicios
  deben seguir haciéndolo por si alguien llega por la red interna.
- **Salud agregada limitada.** nginx open source solo hace health checks *pasivos*
  (detecta la caída cuando falla una petición real) y no puede armar un `/health`
  agregado de todos los servicios; eso requeriría nginx Plus, un módulo o un gateway propio.
- **Una pieza más que operar** (configuración, logs, despliegue), justificada aquí porque
  hay siete servicios y tres clientes; con un servicio y un cliente no valdría la pena.

### Retos del despliegue en Google Cloud

- **La VM era CentOS Stream 10, no Ubuntu.** El script asumía `apt-get`; se generalizó a
  `apt-get`/`dnf`/`yum`.
- **SELinux** bloquea por defecto que nginx abra conexiones a otros puertos (502) y que
  escuche en el 8080. Se resolvió con `setsebool -P httpd_can_network_connect 1` y
  `semanage port -a -t http_port_t -p tcp 8080`.
- **`access_log /dev/stdout`** funcionaba en Docker pero hacía fallar a nginx bajo systemd
  (la salida estándar es un socket). `nginx -t` pasaba y aun así el servicio no arrancaba.
- **Configuración incompleta de los servicios:** cuatro `.env` de la VM no tenían los datos
  de PostgreSQL. El gateway lo hizo evidente: login y libros daban 200 y el resto 503 con
  el mismo cuerpo directo y por nginx, lo que descartó al proxy como causa.
- **Filtro de la red escolar (FortiGuard):** desde la red de la universidad, cualquier
  petición a `IP:8080` regresa `403 Web Filter Violation` antes de llegar a Google Cloud.
  Se prueba desde otra red o con un túnel SSH (`gcloud compute ssh -- -L 8080:127.0.0.1:8080`).
  Es otro argumento a favor de un solo punto de entrada: hay que pedir que se permita **un**
  destino, no siete.

## 4. Preguntas de la sesión

- **¿Qué resolvió y qué introdujo?** Resolvió el acoplamiento de las apps a siete
  direcciones y la exposición de siete puertos; introdujo un punto único de falla y unos
  milisegundos de latencia.
- **Si el gateway cae, ¿qué ve el usuario?** Las tres apps marcan todos los servicios como
  caídos. Lo haría más disponible con dos nginx tras un balanceador administrado y
  reinicio automático.
- **¿Por qué los servicios siguen validando el JWT?** Porque el gateway es una capa extra,
  no la única: un error de configuración o un acceso desde la red interna lo saltaría.
- **¿Qué lógica tenté poner en nginx?** Responder el catálogo desde caché con reglas de
  stock; no va ahí porque es regla de negocio y quedaría duplicada fuera del servicio dueño.
- **¿Cuándo usaría uno comercial?** Con autenticación central, cuotas por cliente/API key,
  métricas y despliegue en varias regiones (p. ej. Google Cloud API Gateway, Kong).

## 5. Conclusión

Con unas 200 líneas de configuración nginx convirtió siete direcciones en una, dio
balanceo y conmutación por falla al catálogo, y uniformó errores, límites y registros,
sin tocar la lógica de ningún servicio ni de las apps. Lo más valioso fue **provocar
fallas a propósito**: ahí apareció el problema de IPv6 y el del round robin por worker,
que con pruebas "felices" no se habrían visto.

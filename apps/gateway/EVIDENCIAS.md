# Evidencias — Library API Gateway (nginx)

Todas se generaron el 20-nov-2026 en local (Windows 11, nginx 1.27 en Docker Desktop,
PostgreSQL 17, Redis 7) con los microservicios reales, no simuladores.

## 1. Las tres apps funcionando a través del reverse proxy

### Electron (catálogo XML)
`evidencias/electron/01_catalogo_via_gateway.png` — URL del microservicio
`http://127.0.0.1:8080/api/books`, endpoint `/books`, **10 libros en XML**.
En el log de nginx queda la petición:

```
"GET /api/books/books?format=XML HTTP/1.1" status=200 upstream=…:6001 up_status=200 rt=0.015s
```

### Python / Tkinter
- `evidencias/python/01_login_via_gateway.png` — catálogo cargado y semáforo de los seis
  servicios respondiendo `HTTP 200` a través de nginx.
- `evidencias/python/02_configuracion_gateway.png` — pantalla *Configuración del servidor*:
  las seis URL base son `http://127.0.0.1:8080/api/<servicio>`.

> Nota: el semáforo marca *Degradado* (con HTTP 200) en users/autores/pedidos/pagos.
> No lo causa el proxy: el cuerpo de `/health` es idéntico directo y vía nginx; el
> clasificador de la app espera el sobre plano y esos servicios responden dentro de
> `data`. Es un ajuste pendiente de la app, fuera del alcance de esta entrega.

### Java / JavaFX (recorrido completo, modo `-Devidencias`)
`evidencias/java/01_login.png … 14_sesion_expirada.png`: login JWT (la pantalla muestra
`login: http://127.0.0.1:8080/api/login`), catálogo, detalle con autores, búsqueda,
cesta, compra (pedido + pago), **rastreo GPS por WebSocket** (07–10), mis compras,
perfil, SOAP/XML y expiración de sesión. Todo por el puerto 8080:

```
"POST /api/pedidos/pedidos HTTP/1.1" status=201 upstream=…:5004
"POST /api/pagos/pagos HTTP/1.1"     status=201 upstream=…:5005
"GET /api/rastreo/ws/rastreo/LIB-MTY-2026-000012 HTTP/1.1" status=101 upstream=…:5006 rt=104.393s
```

El `101 Switching Protocols` de 104 s es el WebSocket del rastreo atravesando nginx.

## 2. Pruebas funcionales — `evidencias/pruebas_gateway.log`

`python tests/test_gateway.py` → **21 OK, 0 fallas**:

| Req. | Prueba | Resultado |
|---|---|---|
| RF1 | `/api/{login,books,users,autores,pedidos,pagos,rastreo}/health` + `/health` | 200 en los 8 |
| RF2 | `/api/books/books?format=json` y `?format=xml` | prefijo quitado, query y XML intactos |
| RF7 | `X-Request-ID` generado y respetado | OK |
| RF3 | 6 peticiones a libros | `['5001','6001','5001','6001','5001','6001']` |
| RF2 | login (captcha) → JWT → `/session` y `/pedidos` con Bearer; `/pedidos` sin token | 200, 200, 200, **401 del servicio** |
| RF6 | ruta desconocida | 404 JSON con `request_id` |
| RF8 | 40 peticiones seguidas a `/api/login/` | 9 × 200, 31 × **429** JSON |

## 3. Pruebas de falla — `evidencias/pruebas_falla.log`

`bash tests/pruebas_falla.sh`:

- **Se apaga Libros :5001** → 6/6 peticiones `200`. Cabecera `X-Upstream`:
  `…:5001, …:6001` (nginx intentó :5001, falló y reintentó en :6001) y después solo
  `…:6001` (la instancia quedó fuera de rotación 10 s).
- **Se apaga Pagos :5005** (instancia única) →
  `503 {"error":"SERVICE_UNAVAILABLE", …, "request_id":"359b7a32…"}`.

## 4. Carga con Locust — `evidencias/carga_*_stats.csv`

20 usuarios, 30 s, mismo escenario (`GET /books?format=json` ×3, `GET /health` ×1):

| | Peticiones | Fallos | RPS | `GET /books` p50 | `GET /books` p95 |
|---|---|---|---|---|---|
| Directo `:5001` | 533 | 0 | 18.95 | 8 ms | 21 ms |
| Gateway `:8080/api/books` | 546 | 0 | 18.95 | 14 ms | 32 ms |

## 5. Registro de nginx — `evidencias/nginx_gateway_access.log`

915 líneas, una por petición: `rid` (X-Request-ID), petición, código, instancia que
respondió (`upstream`), código del upstream y tiempos (`rt` total, `urt` del servicio).

## 6. Configuración de nginx usada

[`nginx/nginx.conf`](nginx/nginx.conf) ·
[`nginx/conf.d/library_gateway.conf`](nginx/conf.d/library_gateway.conf) ·
[`nginx/upstreams.docker.conf`](nginx/upstreams.docker.conf) ·
[`nginx/upstreams.local.conf`](nginx/upstreams.local.conf) ·
[`docker-compose.yml`](docker-compose.yml). Validadas con `nginx -t` en ambas variantes.

## 7. Despliegue en Google Cloud — `evidencias/gcp_vm_pruebas.log`

VM `maquina-03` (CentOS Stream 10, `northamerica-south1-c`), nginx 1.26.3 instalado con
`gcp/desplegar_gateway_gcp.sh`. Regla de firewall `library-gateway-8080` (`tcp:8080`).

- Las **7 rutas** `/api/<servicio>/health` responden **200** a través del gateway.
- **Round robin** de libros: `5001, 6001, 5001, 6001, 5001, 6001`.
- Los microservicios escuchan **solo en `127.0.0.1`**; el único puerto del gateway hacia
  fuera es `0.0.0.0:8080`. (El rastreo escucha en `0.0.0.0:5006` porque su código fija el
  host; queda cerrado al eliminar la regla de firewall de 5000-5007.)
- El log de nginx en la VM registra `request_id`, instancia (`upstream`) y tiempos.

En las apps basta escribir la IP externa de la VM en el campo **Servidor (IP del gateway)**.

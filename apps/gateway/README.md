# Library API Gateway — Reverse Proxy con nginx

**Integración de Aplicaciones Computacionales · SC3705 · Sesión 08**
Fabián Azaed Orta Singlaterry · 613504 · Prof. Dr. Raúl Morales Salcedo

Las tres apps de escritorio (**Electron**, **Python/Tkinter** y **Java/JavaFX**) ya no
hablan con siete puertos distintos: hablan con **un solo puerto (8080)** y nginx
reenvía cada petición al microservicio que corresponde.

```
ANTES (21 conexiones: 3 apps x 7 servicios)        DESPUES (3 + 7 conexiones)

 Electron ─┬─> :5000 login                          Electron ─┐
 Python  ──┼─> :5001 libros                         Python  ──┼─> nginx :8080 ─┬─> :5000 login
 Java    ──┼─> :5002 users                          Java    ──┘   /api/<svc>/  ├─> :5001 ┐ libros
           ├─> :5003 autores                                                  ├─> :6001 ┘ (round robin)
           ├─> :5004 pedidos                                                  ├─> :5002 users
           ├─> :5005 pagos                                                    ├─> :5003 autores
           └─> :5006 rastreo (WS)                                             ├─> :5004 pedidos
                                                                              ├─> :5005 pagos
                                                                              └─> :5006 rastreo (HTTP + WebSocket)
```

Diagramas completos: [`entrega_gateway/Diagrama_Arquitectura_Actual.png`](../../entrega_gateway/Diagrama_Arquitectura_Actual.png)
y [`Diagrama_Arquitectura_Propuesta.png`](../../entrega_gateway/Diagrama_Arquitectura_Propuesta.png).

---

## 1. Archivos

```
apps/gateway/
├── nginx/
│   ├── nginx.conf                    principal: incluye upstreams + tabla de rutas
│   ├── conf.d/library_gateway.conf   server :8080, rutas, límites, errores JSON, logs
│   ├── upstreams.local.conf          servicios en 127.0.0.1 (VM de GCP / nginx nativo)
│   └── upstreams.docker.conf         servicios en el host (nginx en Docker Desktop)
├── docker-compose.yml                nginx:1.27-alpine en :8080
├── docker-start.sh                   resuelve la IPv4 del host y arranca nginx
├── levantar_local.sh                 demo local: Redis + 8 procesos + nginx
├── gcp/desplegar_gateway_gcp.sh      instalación en la VM de Google Cloud
├── tests/
│   ├── test_gateway.py               pruebas funcionales (RF1-RF8)
│   ├── pruebas_falla.sh              apaga :5001 y Pagos en vivo
│   └── locust_gateway.py             carga: directo vs gateway
├── evidencias/                       logs de pruebas, log de nginx, capturas, Locust
├── EVIDENCIAS.md                     índice de evidencias
└── REFLEXION.md                      reflexión de la implementación
```

## 2. Tabla de rutas

El prefijo `/api/<servicio>` se **elimina** antes de reenviar (barra final en
`proxy_pass`), así que cada servicio recibe exactamente la ruta que ya conocía y las
apps **solo cambian su URL base**.

| La app llama a | nginx reenvía a | Instancias | Límite |
|---|---|---|---|
| `/api/login/...`   | login `/...`   | :5000 | 30 r/min, burst 10 (anti fuerza bruta) |
| `/api/books/...`   | libros `/...`  | :5001, :6001 (round robin) | 20 r/s, burst 40 |
| `/api/users/...`   | users `/...`   | :5002 | 20 r/s |
| `/api/autores/...` | autores `/...` | :5003 | 20 r/s |
| `/api/pedidos/...` | pedidos `/...` | :5004 | 20 r/s |
| `/api/pagos/...`   | pagos `/...`   | :5005 | 20 r/s |
| `/api/rastreo/...` | rastreo `/...` (incluye WebSocket `ws/rastreo/<código>`) | :5006 | 20 r/s |
| `/health`          | lo responde nginx | — | — |
| cualquier otra     | `404` JSON | — | — |

## 3. Qué hace nginx (además de reenviar)

| Requisito | Cómo se resolvió en nginx |
|---|---|
| RF2 · método, query, cuerpo, `Authorization`, cookies intactos | `proxy_pass` sin reescrituras, `proxy_intercept_errors off` |
| RF3 · balanceo round robin | `upstream books_svc` con dos `server` + `zone` compartida entre workers |
| RF4 · instancia caída fuera de rotación y reintento | `max_fails=2 fail_timeout=10s` + `proxy_next_upstream error timeout http_502 http_503` |
| RF6 · timeouts y errores uniformes | `proxy_connect_timeout 3s`, `proxy_read_timeout 10s`; `error_page` 404/429/502/503/504 → JSON con `request_id` |
| RF7 · `X-Request-ID` y un registro por petición | `map` que respeta el ID del cliente o usa `$request_id`; `log_format gateway` con upstream, código y tiempos |
| RF8 · límite de tasa por IP | `limit_req_zone $binary_remote_addr` (zonas `api` y `login`), `limit_req_status 429` |
| RF9 · configuración fuera del código | upstreams en archivo aparte; apps leen su URL de config/LocalStorage/properties |
| WebSocket (rastreo GPS de la app Java) | `Upgrade`/`Connection` + `proxy_read_timeout 1h` en `/api/rastreo/` |
| Seguridad | `server_tokens off`; en la VM los servicios escuchan solo en `127.0.0.1` |

## 4. Cambios en cada app

Solo cambió **la dirección**, ninguna lógica:

| App | Archivo | Antes | Después |
|---|---|---|---|
| Electron | `ElectronApp/renderer.js`, `index.html` | `http://127.0.0.1:5001` | `http://127.0.0.1:8080/api/books` |
| Python/Tk | `Python_app/core/config.py` | 6 URLs `:5000`–`:5005` | 6 URLs `http://127.0.0.1:8080/api/<svc>`; nuevo `use_gateway`/`gateway_port` para que *Usar remoto* arme `http://<IP>:8080/api/<svc>` |
| Java/JavaFX | `JavaDesktop_app/config.properties`, `ApiClient.java` | 7 URLs `:5000`–`:5006` | 7 URLs `http://127.0.0.1:8080/api/<svc>` (también el WebSocket) |

> Si la app Electron ya tenía guardada una URL vieja en LocalStorage, pulsa **Reset**.
> En la app Python, si existe un `runtime/config.json` anterior, usa **Restablecer**
> en *Configuración del servidor*.

## 5. Ejecutar en local (Windows + Docker Desktop)

Requisitos: PostgreSQL con la base `library`, Docker Desktop y el `.env` de cada servicio
(solo se versiona `.env.example`).

```bash
cd apps/gateway
./levantar_local.sh start     # Redis, servicios (+ libros en :6001) y nginx en :8080
./levantar_local.sh status    # /health de cada servicio A TRAVES del gateway
python tests/test_gateway.py  # pruebas funcionales
bash tests/pruebas_falla.sh   # apaga :5001 y Pagos y muestra la respuesta de nginx
./levantar_local.sh stop
```

Solo nginx: `docker compose up -d` · log en vivo: `docker compose logs -f`.

## 6. Desplegar en Google Cloud

En la VM (repo en `/opt/udem/integracion03`):

```bash
cd /opt/udem/integracion03 && git pull
sudo bash apps/gateway/gcp/desplegar_gateway_gcp.sh
# rastreo (WebSocket) aparte, solo en loopback del lado del firewall:
cd apps/services/rastreo && PEDIDOS_BASE_URL=http://127.0.0.1:5004 nohup python3 app.py &
```

El script instala nginx, copia la configuración con `upstreams.local.conf`, valida con
`nginx -t` (si falla restaura el respaldo) y reinicia los servicios con
`BIND_HOST=127.0.0.1`. En el firewall de GCP se abre **solo `tcp:8080`** y se cierran
las reglas de 5000–5006 (comandos `gcloud` en la cabecera del script).

En las apps, solo se cambia el host:
`http://<IP_EXTERNA_VM>:8080/api/<servicio>` (Electron: campo URL; Python: botón
*Usar remoto*; Java: `config.properties`).

## 7. Pruebas y resultados

Ver [`EVIDENCIAS.md`](EVIDENCIAS.md). Resumen:

- Funcionales: **21/21 OK** (siete rutas, prefijo y query, XML, X-Request-ID, round robin
  `[5001, 6001, 5001, 6001, …]`, login + JWT + 401 propagado, 404 y 429 en JSON).
- Falla: con :5001 apagada las 6 peticiones dieron **200** (nginx reintentó en :6001);
  con Pagos apagado → **503 JSON** con `request_id`.
- Carga (Locust, 20 usuarios, 30 s): `GET /books` p50 8→14 ms, p95 21→32 ms; mismo RPS
  (~19/s) y **0 fallos** en ambos casos.

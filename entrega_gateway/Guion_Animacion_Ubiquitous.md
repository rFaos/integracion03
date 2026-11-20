# Guion de animación: autenticación JWT y compra en Library

Para armar en Ubiquitous a partir del diagrama `Diagrama_Flujo_JWT_Compra.png` (diapositiva 10).

## Colores (los mismos del deck)

| Tipo | Componentes | Color |
|---|---|---|
| Cliente | App Electron / Python / Java / Web | Violeta `#5B3FC4` |
| Infraestructura | Cloud Load Balancer, API Gateway (Kong), upstream de Books | Verde azulado `#0B7F89` |
| Microservicio | Login, Books (×3), Pedidos, Pagos | Ámbar `#B86A0B` |
| Datos | PostgreSQL, Redis | Gris `#556275` |

Regla: no rotular el Load Balancer como "proxy" ni el Gateway como "balanceador". Cada caja tiene un rol distinto.

## Escenas (unos 3 s cada una)

| # | Animación | Texto en pantalla |
|---|---|---|
| 0 | Aparecen las cuatro columnas: Cliente → Cloud LB → API Gateway → microservicios → datos | "Una sola dirección: https://api.library.mx" |
| 1 | Paquete violeta del Cliente cruza LB (destella el candado TLS) y Gateway hasta Login | `POST /api/v1/auth/login` con usuario, contraseña y captcha |
| 2 | Login consulta PostgreSQL y Redis | "bcrypt OK · refresh token guardado como SHA-256" |
| 3 | Regresa al Cliente un paquete con forma de llave | "Access JWT HS256 · 20 min · iss=library-login · aud=library-api" |
| 4 | Petición a Books; el upstream la manda a la instancia con menos conexiones (resalta Books #2) | `GET /api/v1/books` · "público, sin token" |
| 5 | Responde el catálogo; destello en Redis | "Respuesta desde caché Redis" |
| 6 | El Cliente envía la llave adjunta al paquete hacia el Gateway | `POST /api/v1/pedidos` · `Authorization: Bearer <JWT>` |
| 7 | El Gateway "escanea" la llave: firma ✓, exp ✓, iss ✓, cuota ✓, CORS ✓ | "El Gateway valida antes de dejar pasar" |
| 7b | (Opcional) Variante con token vencido: escáner en rojo, 401, el Cliente llama a `/auth/refresh` y reintenta | "401 → refresh → reintento" |
| 8 | El Gateway reenvía a Pedidos con `X-User-Id` | "Pedidos revisa en Redis que el jti no esté revocado" |
| 9 | Pedidos escribe en PostgreSQL y responde | "201 · pedido #1042 · Pendiente" |
| 10 | El Cliente envía el pago con la misma llave hacia Pagos | `POST /api/v1/pagos` · `pedido_id: 1042` |
| 11 | Pagos registra el pago y cambia el pedido a Pagado **en una sola transacción** | "Sin llamada HTTP a Pedidos: atomicidad en BD" |
| 12 | Respuesta final al Cliente; todo en verde | "201 · compra completa" |

## Escena extra (resiliencia, opcional)

Pedidos se pone en gris con una ✕; el health check falla; el Gateway responde `503` al instante. Login, Books, Users y Autores siguen en verde.

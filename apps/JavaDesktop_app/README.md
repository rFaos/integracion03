# JavaDesktop_app: Library Desktop (JavaFX)

Cliente de escritorio en Java para los microservicios Library: login JWT, catálogo, cesta, compra simulada (pedidos y pagos), Mis compras, y rastreo GPS por WebSockets en un mapa Leaflet integrado.

## Ejecutar
1. Arranca los microservicios (local o GCP) y el servicio de rastreo `../services/rastreo` (`python app.py`, puerto 5006, variable `PEDIDOS_BASE_URL`).
2. Ajusta `config.properties` con las URLs de los servicios.
3. Ejecuta `run.bat`: descarga JavaFX 21 si falta, compila y abre la app. También funciona con Maven: `mvn javafx:run`.

## Estructura
```
src/main/java/mx/udem/library/
  Main.java       interfaz JavaFX (6 módulos)
  ApiClient.java  REST + JWT + WebSocket (java.net.http)
  Json.java       parser/serializador JSON mínimo
src/main/resources/
  map.html        Leaflet + OpenStreetMap (Monterrey)
  app.css
docs/ENTREGA.md   documento de entrega (A, B, C)
```

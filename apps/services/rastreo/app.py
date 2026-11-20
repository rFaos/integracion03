"""
==============================================================================
Microservicio de RASTREO GPS (Flask + Flask-Sock) - puerto 5006
==============================================================================
Adaptacion minima del proyecto GpsWebSockest para el cliente JavaDesktop_app.

Por que existe: los servicios `pedidos` y `pagos` NO ofrecen seguimiento de
envios. Este servicio lo agrega SIN tocar sus contratos ni su base de datos:

  * No tiene base propia ni accede a PostgreSQL: la verdad comercial (dueno del
    pedido, estado, total) se consulta SIEMPRE a `pedidos` reenviando el mismo
    `Authorization: Bearer <JWT>` del usuario. Si `pedidos` responde 401/403,
    el rastreo tambien se niega -> nadie puede ver pedidos ajenos y un token
    expirado o revocado se rechaza (lo decide el backend que ya lo valida).
  * Solo guarda el vinculo codigo <-> pedido y el instante de inicio de la
    simulacion (data/rastreos.json).

Contrato:
  GET  /health
  POST /rastreo                 {"pedido_id": 125}  -> crea/recupera el codigo
  GET  /rastreo                 codigos del usuario autenticado
  GET  /rastreo/<codigo>        estado actual (snapshot)
  WS   /ws/rastreo/<codigo>     flujo en tiempo real (Authorization en el
                                handshake, o ?token= como respaldo)

Codigo: LIB-MTY-<anio>-<pedido_id con 6 digitos>, p. ej. LIB-MTY-2026-000125.
Ruta: una de las 5 rutas reales de Monterrey (OSRM/OpenStreetMap), elegida por
pedido_id, de modo que pedidos distintos recorren calles distintas.
El estado "Entregado" se alcanza SOLO cuando el vehiculo llega al ultimo punto.
==============================================================================
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

from flask import Flask, jsonify, request
from flask_sock import Sock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PEDIDOS_URL = os.getenv("PEDIDOS_BASE_URL", "http://127.0.0.1:5004").rstrip("/")
PORT = int(os.getenv("PORT", "5006"))
STORE = os.path.join(BASE_DIR, "data", "rastreos.json")

# Fases previas al recorrido (segundos desde la confirmacion) y duracion del viaje.
T_PREPARANDO = 4
T_ENVIADO = 10
T_EN_RUTA = 14
DURACION_RUTA = float(os.getenv("DURACION_RUTA_S", "90"))
TICK = 1.0
CODE_RE = re.compile(r"^LIB-MTY-\d{4}-\d{6}$")

with open(os.path.join(BASE_DIR, "data", "rutas_monterrey.json"), encoding="utf-8") as fh:
    ROUTES = json.load(fh)["routes"]

app = Flask(__name__)
sock = Sock(app)
_lock = threading.Lock()


# ---------------------------------------------------------------- persistencia
def load_store():
    if not os.path.exists(STORE):
        return {}
    with open(STORE, encoding="utf-8") as fh:
        return json.load(fh)


def save_store(data):
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, STORE)


# ---------------------------------------------------- autorizacion via pedidos
class Denied(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def bearer_from_request():
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.args.get("token") or "").strip()


def pedidos_get(path, token):
    """GET al microservicio pedidos con el JWT del usuario (no hay atajo a la BD)."""
    if not token:
        raise Denied(401, "TOKEN_MISSING", "Falta Authorization: Bearer <token>.")
    req = urllib.request.Request(PEDIDOS_URL + path, headers={
        "Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            err = body.get("error") if isinstance(body.get("error"), dict) else body
            code, msg = err.get("code", "PEDIDOS_ERROR"), err.get("message", str(exc))
        except Exception:
            code, msg = "PEDIDOS_ERROR", str(exc)
        raise Denied(exc.code, code, msg)
    except urllib.error.URLError as exc:
        raise Denied(503, "PEDIDOS_UNAVAILABLE", "No se pudo contactar a pedidos: %s" % exc.reason)


def fetch_order(pedido_id, token):
    return pedidos_get("/pedidos/%d" % int(pedido_id), token)["data"]


def make_code(pedido_id):
    return "LIB-MTY-%d-%06d" % (datetime.now().year, int(pedido_id))


# ------------------------------------------------------------------ simulacion
def snapshot(rec):
    route = ROUTES[rec["route_index"]]
    pts = route["points"]
    elapsed = time.time() - rec["started_at"]
    idx = 0
    if elapsed < T_PREPARANDO:
        estado = "Pedido confirmado"
    elif elapsed < T_ENVIADO:
        estado = "Preparando pedido"
    elif elapsed < T_EN_RUTA:
        estado = "Pedido enviado"
    else:
        progress = min((elapsed - T_EN_RUTA) / DURACION_RUTA, 1.0)
        idx = int(round(progress * (len(pts) - 1)))
        # "Entregado" depende de la POSICION: solo al llegar al ultimo punto.
        estado = "Entregado" if idx >= len(pts) - 1 else "En ruta de entrega"
    return {
        "codigo": rec["codigo"],
        "pedido_id": rec["pedido_id"],
        "ruta": route["name"],
        "estado": estado,
        "lat": pts[idx][0],
        "lng": pts[idx][1],
        "indice": idx,
        "total_puntos": len(pts),
        "progreso": round(idx / (len(pts) - 1) * 100, 1),
        "destino": pts[-1],
        "origen": pts[0],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def authorize(codigo, token):
    """Devuelve el registro si el pedido del codigo es visible para el token."""
    if not CODE_RE.match(codigo or ""):
        raise Denied(400, "INVALID_CODE", "Formato de codigo invalido (LIB-MTY-AAAA-000000).")
    with _lock:
        rec = load_store().get(codigo)
    if not rec:
        raise Denied(404, "CODE_NOT_FOUND", "No existe un rastreo con el codigo %s." % codigo)
    fetch_order(rec["pedido_id"], token)  # 401/403 si el token no es valido o el pedido es ajeno
    return rec


def err(exc):
    return jsonify({"status": "error", "error": {"code": exc.code, "message": exc.message}}), exc.status


# ------------------------------------------------------------------- endpoints
@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "rastreo", "rutas": len(ROUTES),
                    "pedidos_base_url": PEDIDOS_URL})


@app.post("/rastreo")
def crear_rastreo():
    body = request.get_json(silent=True) or {}
    token = bearer_from_request()
    try:
        pedido_id = int(body.get("pedido_id"))
        order = fetch_order(pedido_id, token)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": {"code": "VALIDATION_ERROR",
                        "message": "pedido_id entero es obligatorio."}}), 400
    except Denied as exc:
        return err(exc)
    # Solo se rastrea una compra cuyo pago real ya fue aprobado por `pagos`.
    if order["estado"] not in ("Pagado", "Enviado", "Entregado"):
        return jsonify({"status": "error", "error": {"code": "ORDER_NOT_PAID",
                        "message": "El pedido esta '%s'; se rastrea solo tras el pago." % order["estado"]}}), 409
    codigo = make_code(pedido_id)
    with _lock:
        data = load_store()
        existing = next((r for r in data.values() if r["pedido_id"] == pedido_id), None)
        created = existing is None
        if created:
            data[codigo] = {"codigo": codigo, "pedido_id": pedido_id, "user_id": order["user_id"],
                            "route_index": pedido_id % len(ROUTES), "started_at": time.time(),
                            "created_at": datetime.now().isoformat(timespec="seconds")}
            save_store(data)
        rec = existing or data[codigo]
    return jsonify({"status": "ok", "data": snapshot(rec)}), (201 if created else 200)


@app.get("/rastreo")
def mis_rastreos():
    try:
        mine = {p["id"] for p in pedidos_get("/pedidos?limit=200", bearer_from_request())["data"]}
    except Denied as exc:
        return err(exc)
    with _lock:
        recs = [r for r in load_store().values() if r["pedido_id"] in mine]
    return jsonify({"status": "ok", "data": [snapshot(r) for r in recs], "count": len(recs)})


@app.get("/rastreo/<codigo>")
def ver_rastreo(codigo):
    try:
        rec = authorize(codigo, bearer_from_request())
    except Denied as exc:
        return err(exc)
    return jsonify({"status": "ok", "data": snapshot(rec)})


@sock.route("/ws/rastreo/<codigo>")
def ws_rastreo(ws, codigo):
    token = bearer_from_request()
    try:
        rec = authorize(codigo, token)
    except Denied as exc:
        ws.send(json.dumps({"type": "error", "code": exc.code, "message": exc.message}))
        ws.close()
        return
    route = ROUTES[rec["route_index"]]
    snap = snapshot(rec)
    # Mensaje inicial: ruta completa y tramo ya recorrido (permite reconectar).
    ws.send(json.dumps({"type": "init", "ruta_completa": route["points"],
                        "recorrido": route["points"][:snap["indice"] + 1], **snap}))
    last_check = time.time()
    while True:
        time.sleep(TICK)
        if time.time() - last_check > 60:  # re-valida el JWT periodicamente
            try:
                fetch_order(rec["pedido_id"], token)
            except Denied as exc:
                ws.send(json.dumps({"type": "error", "code": exc.code, "message": exc.message}))
                break
            last_check = time.time()
        snap = snapshot(rec)
        ws.send(json.dumps({"type": "posicion", **snap}))
        if snap["estado"] == "Entregado":
            break
    ws.close()


if __name__ == "__main__":
    print("rastreo escuchando en http://0.0.0.0:%d  (pedidos=%s)" % (PORT, PEDIDOS_URL))
    app.run(host="0.0.0.0", port=PORT, threaded=True)

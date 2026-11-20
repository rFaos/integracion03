"""Pruebas funcionales y de falla del Library API Gateway (nginx :8080).

Uso:
    python test_gateway.py                      # gateway local
    GATEWAY=http://<IP_VM>:8080 python test_gateway.py
    DEMO_EMAIL=... DEMO_PASSWORD=... python test_gateway.py   # incluye login/JWT

Las credenciales de prueba se leen de variables de entorno (o del
demo.properties de la app Java, que esta excluido del repositorio); nunca se
imprimen. El resultado se escribe en consola y en evidencias/pruebas_gateway.log.

Las pruebas de falla (instancia de Libros caida, Pagos caido) las dirige
levantar_local.sh / el operador: este script solo observa lo que responde nginx.
"""
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import requests

GW = os.environ.get("GATEWAY", "http://127.0.0.1:8080").rstrip("/")
HERE = Path(__file__).resolve().parent
LOG = HERE.parent / "evidencias" / "pruebas_gateway.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

_lines = []
_fails = 0


def out(msg=""):
    print(msg)
    _lines.append(msg)


def check(name, cond, detail=""):
    global _fails
    if not cond:
        _fails += 1
    out(f"  [{'OK ' if cond else 'FALLA'}] {name}" + (f"  -> {detail}" if detail else ""))


def demo_credentials():
    email, pwd = os.environ.get("DEMO_EMAIL"), os.environ.get("DEMO_PASSWORD")
    if email and pwd:
        return email, pwd
    props = HERE.parent.parent / "JavaDesktop_app" / "demo.properties"
    if props.exists():
        kv = dict(l.split("=", 1) for l in props.read_text(encoding="utf-8").splitlines()
                  if "=" in l and not l.startswith("#"))
        return kv.get("demo.email"), kv.get("demo.password")
    return None, None


def solve_captcha(question):
    a, op, b = re.search(r"(\d+)\s*([-+x*])\s*(\d+)", question).groups()
    a, b = int(a), int(b)
    return {"+": a + b, "-": a - b, "x": a * b, "*": a * b}[op]


def main():
    out(f"=== Library API Gateway - pruebas contra {GW}  ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===")

    out("\n[RF1] Un solo puerto, rutas /api/<servicio>/ hacia los siete servicios")
    for svc in ("login", "books", "users", "autores", "pedidos", "pagos", "rastreo"):
        r = requests.get(f"{GW}/api/{svc}/health", timeout=10)
        check(f"GET /api/{svc}/health", r.status_code == 200,
              f"{r.status_code} upstream={r.headers.get('X-Upstream')} ({r.elapsed.total_seconds()*1000:.0f} ms)")
    r = requests.get(f"{GW}/health", timeout=5)
    check("GET /health (salud del gateway)", r.status_code == 200 and r.json()["status"] == "ok", r.text[:80])

    out("\n[RF2] Prefijo eliminado, query intacta, XML sin cambios")
    r = requests.get(f"{GW}/api/books/books", params={"format": "json"}, timeout=10)
    check("GET /api/books/books?format=json -> /books?format=json", r.status_code == 200 and "books" in r.json(),
          f"{r.json().get('count')} libros")
    r = requests.get(f"{GW}/api/books/books", params={"format": "xml"}, timeout=10)
    check("GET /api/books/books?format=xml devuelve XML (app Electron)",
          r.status_code == 200 and r.text.lstrip().startswith("<?xml"), r.headers.get("Content-Type"))

    out("\n[RF7] X-Request-ID generado o respetado")
    r = requests.get(f"{GW}/api/books/health", timeout=10)
    check("nginx genera X-Request-ID", bool(r.headers.get("X-Request-ID")), r.headers.get("X-Request-ID"))
    rid = uuid.uuid4().hex[:12]
    r = requests.get(f"{GW}/api/books/health", headers={"X-Request-ID": rid}, timeout=10)
    check("nginx respeta el X-Request-ID del cliente", r.headers.get("X-Request-ID") == rid, rid)

    out("\n[RF3] Round robin entre dos instancias de Libros (:5001 y :6001)")
    ups = []
    for _ in range(6):
        r = requests.get(f"{GW}/api/books/health", timeout=10)
        ups.append(r.headers.get("X-Upstream", "?").rsplit(":", 1)[-1])
    out(f"  puertos que respondieron, 6 peticiones seguidas: {ups}")
    check("las peticiones alternan entre las dos instancias", len(set(ups)) == 2, str(sorted(set(ups))))

    out("\n[RF2] Login, JWT y cookie a traves del gateway")
    email, pwd = demo_credentials()
    if not email:
        out("  (omitido: defina DEMO_EMAIL y DEMO_PASSWORD)")
    else:
        cap = requests.get(f"{GW}/api/login/captcha", params={"format": "json"}, timeout=10).json()["data"]
        r = requests.post(f"{GW}/api/login/login", params={"format": "json"}, json={
            "email": email, "password": pwd, "captcha_id": cap["captcha_id"],
            "captcha_answer": solve_captcha(cap["question"])}, timeout=10)
        body = r.json()
        token = ((body.get("data") or {}).get("session") or {}).get("access_token")
        check("POST /api/login/login -> 200 + access_token", r.status_code == 200 and bool(token),
              f"{r.status_code}, token={'si' if token else 'no'}")
        # El servicio de login de Library entrega el JWT en el cuerpo (no usa
        # cookie). nginx no altera Set-Cookie: si existiera, pasaria igual.
        out(f"  [info] Set-Cookie en la respuesta: {'si' if r.headers.get('Set-Cookie') else 'no (login entrega JWT en el cuerpo)'}")
        check("el cuerpo JSON del login llega intacto", body.get("status") == "success", body.get("message", "")[:60])
        if token:
            h = {"Authorization": f"Bearer {token}"}
            r = requests.get(f"{GW}/api/login/session", params={"format": "json"}, headers=h, timeout=10)
            check("GET /api/login/session con Bearer -> 200 (Authorization intacto)", r.status_code == 200, r.status_code)
            r = requests.get(f"{GW}/api/pedidos/pedidos", headers=h, timeout=10)
            check("GET /api/pedidos/pedidos con Bearer -> 200", r.status_code == 200, r.status_code)
            r = requests.get(f"{GW}/api/pedidos/pedidos", timeout=10)
            check("GET /api/pedidos/pedidos SIN token -> 401 del servicio (pasa tal cual)", r.status_code == 401, r.status_code)

    out("\n[RF6] Errores uniformes en JSON con request_id")
    r = requests.get(f"{GW}/api/noexiste/algo", timeout=5)
    check("ruta desconocida -> 404 JSON", r.status_code == 404 and "request_id" in r.json(), r.text[:110])

    out("\n[RF8] Limite de tasa por IP (zona login: 30 r/min, burst 10)")
    codes = [requests.get(f"{GW}/api/login/health", timeout=10).status_code for _ in range(40)]
    n429 = codes.count(429)
    out(f"  40 peticiones seguidas: {codes.count(200)} x 200, {n429} x 429")
    check("una rafaga produce 429", n429 > 0)
    r = requests.get(f"{GW}/api/login/health", timeout=5)
    if r.status_code == 429:
        check("el 429 es JSON con request_id", "request_id" in r.json(), r.text[:110])

    out(f"\n=== {'TODO OK' if _fails == 0 else f'{_fails} FALLA(S)'} ===")
    with LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(_lines) + "\n\n")
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())

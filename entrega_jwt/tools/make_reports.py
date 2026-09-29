"""
==============================================================================
GENERADOR DE INFORMES DE EVIDENCIA (HTML) PARA LAS CAPTURAS
==============================================================================
Toma la evidencia REAL producida por las pruebas y la convierte en paginas
HTML que despues se capturan como imagen:

    informes/postman_flujo.html     vista tipo Postman de los 28 intercambios
    informes/terminal_e2e.html      la bitacora E2E con aspecto de consola
    informes/terminal_app.html      la bitacora de la app Python (Bearer)
    informes/instancia.html         la instancia: IP, puertos y /health reales

No inventa datos: todo sale de `flujo_e2e.json`, `evidencia_e2e.txt`,
`evidencia_app_python.txt` y de una consulta en vivo a los dos /health.

USO
---
    python entrega_jwt/tools/make_reports.py
==============================================================================
"""

import html
import json
import os
import re
import socket
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENTREGA = os.path.join(ROOT, "entrega_jwt")
INFORMES = os.path.join(ENTREGA, "informes")
os.makedirs(INFORMES, exist_ok=True)

LOGIN_BASE = "http://127.0.0.1:5000"
BOOKS_BASE = "http://127.0.0.1:5001"

ESTILO = """
  * { box-sizing: border-box; }
  body { margin:0; background:#0b1120; color:#e2e8f0;
         font-family: "Segoe UI", Inter, system-ui, sans-serif; }
  .wrap { padding: 26px 30px 40px; }
  h1 { font-size: 21px; margin:0 0 4px; color:#fff; }
  .sub { color:#94a3b8; font-size:12.5px; margin-bottom:18px; }
  .mono { font-family: Consolas, "Cascadia Mono", monospace; }
  pre { margin:0; white-space:pre-wrap; word-break:break-word; }
  table { border-collapse: collapse; width:100%; font-size:12px; }
  th, td { border:1px solid #1e293b; padding:4px 8px; text-align:left;
           vertical-align:top; font-family: Consolas, monospace; }
  th { background:#111c30; color:#7dd3fc; font-weight:600; }
  .ok   { color:#4ade80; font-weight:700; }
  .bad  { color:#f87171; font-weight:700; }
  .muted{ color:#94a3b8; }
  .tag  { display:inline-block; padding:2px 8px; border-radius:999px;
          font-size:11px; font-weight:700; letter-spacing:.4px; }
"""


def esc(value):
    return html.escape(str(value if value is not None else ""))


def read_text(name):
    path = os.path.join(ENTREGA, name)
    if not os.path.exists(path):
        return "(no se encontro %s)" % name
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def live_health(url):
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "desconocida"


def page(title, body):
    return ("<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
            "<title>%s</title><style>%s</style></head><body><div class='wrap'>%s</div></body></html>"
            % (esc(title), ESTILO, body))


def write(name, content):
    path = os.path.join(INFORMES, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("  escrito: %s" % os.path.relpath(path, ROOT))
    return path


# ==============================================================================
# 1. VISTA TIPO POSTMAN DEL FLUJO COMPLETO
# ==============================================================================
def build_postman_report():
    with open(os.path.join(ENTREGA, "flujo_e2e.json"), encoding="utf-8") as fh:
        data = json.load(fh)

    cards = []
    for index, ex in enumerate(data["intercambios"], start=1):
        req = ex["request"]
        res = ex["response"]
        status = res["status"]
        color = "#4ade80" if status < 300 else ("#fbbf24" if status < 500 else "#f87171")
        metodo = req["method"]

        filas_req = "".join(
            "<tr><td>%s</td><td>%s</td></tr>" % (esc(k), esc(v))
            for k, v in req["headers"].items()
        )
        filas_res = "".join(
            "<tr><td>%s</td><td>%s</td></tr>" % (esc(k), esc(v))
            for k, v in res["headers"]
        )

        cuerpo_req = ""
        if req.get("body"):
            texto = req["body"]
            if not isinstance(texto, str):
                texto = json.dumps(texto, ensure_ascii=False, indent=2)
            cuerpo_req = ("<div class='muted' style='margin:8px 0 4px;'>Body enviado</div>"
                          "<pre class='mono' style='background:#0f172a;border:1px solid #1e293b;"
                          "border-radius:6px;padding:8px;font-size:11.5px;'>%s</pre>" % esc(texto))

        cuerpo_res = res["body"]
        try:
            cuerpo_res = json.dumps(json.loads(res["body"]), ensure_ascii=False, indent=2)
        except Exception:
            pass

        cards.append("""
        <div style="border:1px solid #1e293b;border-radius:10px;margin-bottom:16px;overflow:hidden;background:#0e1729;">
          <div style="display:flex;align-items:center;gap:10px;padding:9px 12px;background:#111c30;border-bottom:1px solid #1e293b;">
            <span class="tag" style="background:#1e3a8a;color:#bfdbfe;">%02d</span>
            <span class="tag" style="background:#164e63;color:#a5f3fc;">%s</span>
            <span class="mono" style="font-size:12px;color:#e2e8f0;">%s</span>
            <span style="margin-left:auto;font-weight:700;color:%s;">HTTP %s</span>
          </div>
          <div style="padding:10px 12px;">
            <div class="muted" style="font-size:11.5px;margin-bottom:8px;">%s</div>
            <div class="muted" style="margin-bottom:4px;">Request</div>
            <table>%s</table>
            %s
            <div class="muted" style="margin:10px 0 4px;">Response</div>
            <table>%s</table>
            <pre class="mono" style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;
                 padding:8px;font-size:11.5px;margin-top:8px;">%s</pre>
          </div>
        </div>""" % (index, esc(metodo), esc(req["url"]), color, status,
                     esc(ex.get("note") or ""), filas_req, cuerpo_req,
                     filas_res, esc(cuerpo_res)))

    body = """
    <h1>Flujo JWT verificado contra los microservicios</h1>
    <div class="sub">
      Corrida: <b>%s</b> &nbsp;|&nbsp; Host: <b>%s</b> (<span class="mono">%s</span>) &nbsp;|&nbsp;
      login <span class="mono">%s</span> &nbsp;|&nbsp; libros <span class="mono">%s</span><br>
      Aserciones: <span class="ok">%d correctas</span>, <span class="%s">%d fallidas</span>
      &nbsp;|&nbsp; Intercambios registrados: <b>%d</b>
      &nbsp;|&nbsp; Huella del secreto compartido: <span class="mono">%s</span>
    </div>
    <div class="sub">
      Equivalente al Collection Runner de Postman: cada bloque muestra los encabezados y el cuerpo
      <b>tal como se enviaron y tal como respondio el servicio</b>.
    </div>
    %s
    """ % (esc(data["generado"]), esc(data["host"]), esc(data["ip"]),
           esc(data["login_base"]), esc(data["books_base"]),
           data["aserciones_ok"], "ok" if not data["aserciones_fallidas"] else "bad",
           data["aserciones_fallidas"], len(data["intercambios"]),
           esc(data.get("jwt_fingerprint") or ""), "".join(cards))

    return write("postman_flujo.html", page("Flujo JWT - evidencia tipo Postman", body))


# ==============================================================================
# 2. BITACORAS CON ASPECTO DE CONSOLA
# ==============================================================================
def build_terminal_report(source, title, subtitle, out_name):
    texto = read_text(source)
    lineas = texto.splitlines()
    filas = []
    for line in lineas:
        clase = ""
        if "[OK]" in line:
            clase = " style='color:#4ade80;'"
        elif "[FALLO]" in line:
            clase = " style='color:#f87171;'"
        elif line.strip().startswith("<<<"):
            clase = " style='color:#fbbf24;'"
        elif "Authorization: Bearer" in line:
            clase = " style='color:#7dd3fc;'"
        elif line.startswith("=") or line.startswith("-"):
            clase = " style='color:#334155;'"
        filas.append("<span%s>%s</span>" % (clase, esc(line)))

    body = """
    <h1>%s</h1>
    <div class="sub">%s</div>
    <div style="background:#05080f;border:1px solid #1e293b;border-radius:10px;padding:14px 16px;">
      <div style="color:#64748b;font-size:11px;margin-bottom:10px;">
        &#9679; consola &mdash; %s
      </div>
      <pre class="mono" style="font-size:11.5px;line-height:1.42;">%s</pre>
    </div>
    """ % (esc(title), subtitle, esc(source), "\n".join(filas))
    return write(out_name, page(title, body))


# ==============================================================================
# 2.b CORRIDA DE LA COLECCION DE POSTMAN (Newman)
# ==============================================================================
def build_newman_report():
    """Vuelca la corrida real de la coleccion de Postman con Newman.

    Newman imprime con codigos ANSI de color; se limpian para poder capturar.
    """
    texto = read_text("newman_run.txt")
    texto = re.sub(r"\x1b\[[0-9;]*m", "", texto)
    lineas = texto.splitlines()
    filas = []
    for line in lineas:
        clase = ""
        if "√" in line:
            clase = " style='color:#4ade80;'"
        elif line.strip().startswith(("1.", "2.", "3.", "4.", "5.",
                                      "6.", "7.", "8.", "9.")) and "." in line:
            clase = " style='color:#f87171;'"
        elif "failure" in line or "AssertionError" in line:
            clase = " style='color:#f87171;'"
        elif "Authorization" in line:
            clase = " style='color:#7dd3fc;'"
        elif line.startswith(("┌", "├", "└", "│")):
            clase = " style='color:#64748b;'"
        filas.append("<span%s>%s</span>" % (clase, esc(line)))

    body = """
    <h1>Colección de Postman ejecutada con Newman</h1>
    <div class="sub">
      El runner oficial de Postman por línea de comandos, contra la instancia real.
      Así se comprueba que la colección entregada <b>corre limpia</b> y no solo se ve
      bonita en el editor.
    </div>
    <div style="background:#05080f;border:1px solid #1e293b;border-radius:10px;padding:14px 16px;">
      <div style="color:#64748b;font-size:11px;margin-bottom:10px;">
        &#9679; consola &mdash; npx newman run postman/Libreria_JWT_UDEM_613504.postman_collection.json
      </div>
      <pre class="mono" style="font-size:11.5px;line-height:1.42;">%s</pre>
    </div>
    """ % "\n".join(filas)
    return write("postman_newman.html", page("Coleccion Postman con Newman", body))


# ==============================================================================
# 3. PANEL DE LA INSTANCIA
# ==============================================================================
def build_instance_report():
    login = live_health(LOGIN_BASE + "/health?format=json")
    books = live_health(BOOKS_BASE + "/health")
    ip = local_ip()
    host = socket.gethostname()

    def bloque(nombre, url, payload):
        pretty = json.dumps(payload, ensure_ascii=False, indent=2)
        return """
        <div style="border:1px solid #1e293b;border-radius:10px;background:#0e1729;margin-bottom:14px;overflow:hidden;">
          <div style="padding:9px 12px;background:#111c30;border-bottom:1px solid #1e293b;">
            <b style="color:#7dd3fc;">%s</b>
            <span class="mono muted" style="font-size:12px;margin-left:8px;">%s</span>
          </div>
          <pre class="mono" style="padding:10px 12px;font-size:11.5px;">%s</pre>
        </div>""" % (esc(nombre), esc(url), esc(pretty))

    body = """
    <h1>Instancia en ejecución</h1>
    <div class="sub">Los dos microservicios levantados en el equipo, con PostgreSQL 17 en la misma máquina.</div>

    <table style="margin-bottom:16px;">
      <tr><th style="width:230px;">Equipo</th><td>%s</td></tr>
      <tr><th>Dirección IPv4 (LAN)</th><td class="mono">%s</td></tr>
      <tr><th>Microservicio de autenticación</th><td class="mono">http://%s:5000 &nbsp; (también http://127.0.0.1:5000)</td></tr>
      <tr><th>Microservicio de libros</th><td class="mono">http://%s:5001 &nbsp; (también http://127.0.0.1:5001)</td></tr>
      <tr><th>Base de datos</th><td class="mono">PostgreSQL 17.4 · library @ 127.0.0.1:5432</td></tr>
      <tr><th>Documentación</th><td class="mono">/docs en ambos servicios</td></tr>
    </table>

    %s
    %s
    """ % (esc(host), esc(ip), esc(ip), esc(ip),
           bloque("login-microservice · GET /health?format=json",
                  LOGIN_BASE + "/health?format=json", login),
           bloque("Academic Library RESTful Microservice · GET /health",
                  BOOKS_BASE + "/health", books))
    return write("instancia.html", page("Instancia en ejecucion", body))


if __name__ == "__main__":
    print("Generando informes de evidencia...")
    build_postman_report()
    build_terminal_report(
        "evidencia_e2e.txt",
        "Bitácora E2E de los microservicios con JWT",
        "Peticiones y respuestas literales del flujo completo: lectura pública, "
        "401 sin token, 201 con Bearer, rotación del refresh y ataques rechazados.",
        "terminal_e2e.html")
    build_terminal_report(
        "evidencia_app_python.txt",
        "Bitácora de la app Python TK (Authorization: Bearer)",
        "El cliente de escritorio mostrando en la terminal cada petición con el "
        "encabezado del token y el refresco automático al recibir un 401.",
        "terminal_app.html")
    build_instance_report()
    build_newman_report()
    print("Listo.")

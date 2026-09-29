"""
==============================================================================
CAPTURA DE PANTALLA DE LA EVIDENCIA (Playwright / Chromium headless)
==============================================================================
Convierte los informes HTML (que salen de evidencia REAL) y las interfaces
reales (Electron, Swagger) en imagenes PNG para el reporte de entrega.

Por que Chromium y no la ventana de Electron: la sesion del agente no tiene
escritorio interactivo, asi que `electron .` arranca y muere sin dibujar.
El renderer de Electron es HTML puro, por eso se sirve el MISMO index.html
sobre http://127.0.0.1:8099 y se captura con Chromium: lo que se ve en la
captura es el renderer de verdad consumiendo los microservicios de verdad.

CAPTURAS
--------
  capturas/01_publico_vs_protegido.png   tarjetas 01-03  (GET libre / POST 401)
  capturas/02_login_emite_jwt.png        tarjeta  07     (access + refresh)
  capturas/03_crud_bearer.png            tarjetas 09,11,12
  capturas/04_alias_book_insert.png      tarjetas 13-14  (no hay puerta trasera)
  capturas/05_session_verify_refresh.png tarjetas 15-17
  capturas/06_refresh_reuse.png          tarjeta  18     (deteccion de reuso)
  capturas/07_ataques_rechazados.png     tarjetas 19-22  (alg none, firma, exp, aud)
  capturas/08_delete_logout.png          tarjetas 24,26-28
  capturas/09_terminal_e2e_*.png         recortes de la bitacora E2E
  capturas/10_terminal_app_python.png    bitacora de la app TK con Bearer
  capturas/11_instancia.png              IP, puertos y /health en vivo
  capturas/12_electron_publico.png       renderer Electron sin token
  capturas/13_electron_con_bearer.png    renderer Electron con JWT
  capturas/14_swagger_login.png          Swagger del servicio de login
  capturas/15_swagger_books.png          Swagger del servicio de libros

USO
---
    python entrega_jwt/tools/capture_shots.py
==============================================================================
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENTREGA = ROOT / "entrega_jwt"
INFORMES = ENTREGA / "informes"
CAPTURAS = ENTREGA / "capturas"
CAPTURAS.mkdir(parents=True, exist_ok=True)

ELECTRON_DIR = ROOT / "apps" / "ElectronApp"
ELECTRON_PORT = 8099
ELECTRON_URL = "http://127.0.0.1:%d/index.html" % ELECTRON_PORT

LOGIN_BASE = "http://127.0.0.1:5000"
BOOKS_BASE = "http://127.0.0.1:5001"

ANCHO = 1500
ALTO = 1000
ESCALA = 1.4  # mas densidad de pixeles -> texto legible al abrir el PNG

# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def uri(path):
    return pathlib.Path(path).resolve().as_uri()


def guardar(page, nombre, full_page=True, clip=None):
    destino = CAPTURAS / nombre
    page.screenshot(path=str(destino), full_page=full_page, clip=clip)
    kb = destino.stat().st_size / 1024
    print("  [png] %-38s %7.1f KB" % (nombre, kb))
    return destino


def http_json(url, metodo="GET", cuerpo=None, cabeceras=None):
    datos = None
    headers = dict(cabeceras or {})
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=datos, headers=headers, method=metodo)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolver_captcha():
    """Pide un desafio y resuelve la operacion aritmetica que trae la pregunta."""
    cap = http_json(LOGIN_BASE + "/captcha?format=json")
    pregunta = cap["data"]["question"]
    operacion = re.search(r"(\d+)\s*([+\-*])\s*(\d+)", pregunta)
    a, signo, b = int(operacion.group(1)), operacion.group(2), int(operacion.group(3))
    resultado = {"+": a + b, "-": a - b, "*": a * b}[signo]
    return cap["data"]["captcha_id"], resultado


def login_para_token():
    """Consigue un JWT real para poder capturar la app con Bearer puesto."""
    try:
        usuario = "captura%d@udem.mx" % int(time.time() % 1000000)
        cid, respuesta = resolver_captcha()
        http_json(
            LOGIN_BASE + "/register?format=json",
            "POST",
            {
                "nombre": "Captura",
                "apellido_paterno": "Demo",
                "apellido_materno": "JWT",
                "email": usuario,
                "password": "Captura.2026",
                "captcha_id": cid,
                "captcha_answer": respuesta,
            },
        )
        cid, respuesta = resolver_captcha()
        sesion = http_json(
            LOGIN_BASE + "/login?format=json",
            "POST",
            {
                "email": usuario,
                "password": "Captura.2026",
                "captcha_id": cid,
                "captcha_answer": respuesta,
            },
        )
        datos = sesion["data"]["session"]
        token = datos.get("access_token") or datos.get("token")
        return token, usuario
    except Exception as exc:
        print("  (aviso) no se pudo obtener un token para la captura: %s" % exc)
        return None, None


# --------------------------------------------------------------------------
# Capturas de los informes
# --------------------------------------------------------------------------


# Ojo: al mutar el atributo style, Chromium lo re-serializa con espacios
# ("border-radius: 10px"), asi que un selector [style*="border-radius:10px"]
# deja de coincidir. Por eso las tarjetas se etiquetan UNA vez con data-card.
ETIQUETAR_TARJETAS_JS = """
() => {
    const wrap = document.querySelector('.wrap');
    const cards = Array.from(wrap.children).filter(
        (d) => (d.getAttribute('style') || '').indexOf('border-radius') >= 0);
    cards.forEach((c, i) => { c.dataset.card = String(i + 1); });
    return cards.length;
}
"""

SELECCIONAR_TARJETAS_JS = """
(keep) => {
    const cards = document.querySelectorAll('div.wrap > div[data-card]');
    let visibles = 0;
    cards.forEach((c) => {
        const on = keep.indexOf(parseInt(c.dataset.card, 10)) >= 0;
        c.style.display = on ? '' : 'none';
        if (on) visibles += 1;
    });
    return {visibles: visibles, alto: document.documentElement.scrollHeight};
}
"""


def capturar_postman(page, grupos):
    page.goto(uri(INFORMES / "postman_flujo.html"))
    page.wait_for_timeout(350)
    total = page.evaluate(ETIQUETAR_TARJETAS_JS)
    print("  tarjetas etiquetadas en el informe Postman: %d" % total)
    for nombre, indices in grupos:
        info = page.evaluate(SELECCIONAR_TARJETAS_JS, indices)
        if info["visibles"] != len(indices):
            print("     (aviso) %s: esperaba %d tarjetas, vio %d"
                  % (nombre, len(indices), info["visibles"]))
        page.wait_for_timeout(150)
        guardar(page, nombre)
        page.evaluate("""() => {
            document.querySelectorAll('div.wrap > div[data-card]')
                .forEach((c) => { c.style.display = ''; });
        }""")


BUSCAR_OFFSET_JS = """
(needle) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let nodo;
    while ((nodo = walker.nextNode())) {
        const idx = nodo.nodeValue.indexOf(needle);
        if (idx >= 0) {
            const r = document.createRange();
            r.setStart(nodo, idx);
            r.setEnd(nodo, Math.min(idx + needle.length, nodo.nodeValue.length));
            const rect = r.getBoundingClientRect();
            return Math.max(0, rect.top + window.scrollY);
        }
    }
    return -1;
}
"""


def capturar_terminal(page, archivo, recortes, prefijo):
    """recortes = [(nombre, marcador, desplazamiento, alto), ...]"""
    page.goto(uri(INFORMES / archivo))
    page.wait_for_timeout(400)
    alto_total = page.evaluate("document.documentElement.scrollHeight")
    print("  %s: %d px de alto" % (archivo, alto_total))
    for nombre, marcador, delta, alto in recortes:
        if marcador is None:
            y = 0
        else:
            y = page.evaluate(BUSCAR_OFFSET_JS, marcador)
            if y < 0:
                print("     (aviso) marcador no encontrado: %r" % marcador)
                continue
            y = max(0, y - delta)
        alto_ef = min(alto, alto_total - y)
        guardar(
            page,
            nombre,
            full_page=True,
            clip={"x": 0, "y": y, "width": ANCHO, "height": alto_ef},
        )


# --------------------------------------------------------------------------
# Programa
# --------------------------------------------------------------------------


def main():
    print("=" * 74)
    print(" CAPTURAS DE EVIDENCIA")
    print("=" * 74)

    servidor = None
    try:
        servidor = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(ELECTRON_PORT),
             "--bind", "127.0.0.1", "--directory", str(ELECTRON_DIR)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.2)
        print(" servidor del renderer Electron: %s" % ELECTRON_URL)
    except Exception as exc:
        print(" (aviso) no se pudo levantar el servidor del renderer: %s" % exc)

    token, correo = login_para_token()
    if token:
        print(" token real obtenido para las capturas: %s..." % token[:28])
        print(" usuario de la captura: %s" % correo)

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(args=["--force-device-scale-factor=%s" % ESCALA])
        page = navegador.new_page(
            viewport={"width": ANCHO, "height": ALTO},
            device_scale_factor=ESCALA,
        )

        print("\n[1] Informe tipo Postman (flujo JWT completo)")
        capturar_postman(
            page,
            [
                ("01_publico_vs_protegido.png", [1, 2, 3]),
                ("02_login_emite_jwt.png", [7]),
                ("03_crud_bearer.png", [9, 11, 12]),
                ("04_alias_book_insert.png", [13, 14]),
                ("05_session_verify_refresh.png", [15, 16, 17]),
                ("06_refresh_reuse.png", [18]),
                ("07_ataques_rechazados.png", [19, 20, 21, 22]),
                ("08_delete_logout.png", [24, 26, 27, 28]),
            ],
        )

        print("\n[2] Bitacora E2E en consola")
        capturar_terminal(
            page,
            "terminal_e2e.html",
            [
                ("09_terminal_e2e_apertura.png",
                 "EVIDENCIA E2E - AUTORIZACION POR JWT", 40, 1500),
                ("09b_terminal_e2e_publico_vs_protegido.png",
                 "1 y 2. REGLA CLAVE", 40, 1500),
                ("09c_terminal_e2e_login_jwt.png",
                 "3. OBTENCION DEL TOKEN", 40, 1500),
                ("09d_terminal_e2e_crud_bearer.png",
                 "POST /books CON Authorization: Bearer", 70, 1500),
                ("09e_terminal_e2e_refresh.png",
                 "6. SESION Y REFRESCO", 40, 1500),
                ("09f_terminal_e2e_ataques.png",
                 "7. ATAQUES CONTRA EL JWT", 40, 1600),
                ("09g_terminal_e2e_resultado.png",
                 "RESULTADO", 40, 700),
            ],
            "09",
        )

        print("\n[3] Bitacora de la app Python TK")
        capturar_terminal(
            page,
            "terminal_app.html",
            [
                ("10_terminal_app_python.png", None, 0, 3700),
            ],
            "10",
        )

        print("\n[4] Instancia en ejecucion (IP, puertos, /health)")
        page.goto(uri(INFORMES / "instancia.html"))
        page.wait_for_timeout(300)
        guardar(page, "11_instancia.png")

        print("\n[4.b] Corrida de la coleccion Postman con Newman")
        capturar_terminal(
            page,
            "postman_newman.html",
            [
                ("16_postman_newman_apertura.png",
                 "Colección de Postman ejecutada", 30, 1500),
                ("16b_postman_newman_resultado.png", "iterations", 430, 820),
            ],
            "16",
        )

        print("\n[5] Renderer de la aplicacion Electron")
        if servidor:
            page.goto(ELECTRON_URL, wait_until="load")
            page.wait_for_timeout(2500)
            guardar(page, "12_electron_publico.png")
            if token:
                page.evaluate(
                    "(t) => { localStorage.setItem('catalog_api_token', t); }", token
                )
                page.reload(wait_until="load")
                page.wait_for_timeout(2500)
                guardar(page, "13_electron_con_bearer.png")
        else:
            print("  (omitido) no hay servidor para el renderer")

        print("\n[6] Documentacion Swagger de los dos servicios")
        try:
            page.goto(LOGIN_BASE + "/docs", wait_until="load")
            page.wait_for_timeout(2000)
            guardar(page, "14_swagger_login.png")
        except Exception as exc:
            print("  (aviso) Swagger login: %s" % exc)
        try:
            page.goto(BOOKS_BASE + "/docs", wait_until="load")
            page.wait_for_timeout(2000)
            guardar(page, "15_swagger_books.png")
        except Exception as exc:
            print("  (aviso) Swagger libros: %s" % exc)

        navegador.close()

    if servidor:
        servidor.terminate()

    archivos = sorted(CAPTURAS.glob("*.png"))
    print("\n" + "=" * 74)
    print(" LISTO: %d capturas en %s" % (len(archivos), CAPTURAS))
    for f in archivos:
        print("   %-42s %7.1f KB" % (f.name, f.stat().st_size / 1024))
    print("=" * 74)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera la evidencia grafica de la GUI del cliente Tk.

Recorre la aplicacion REAL en ejecucion (no maquetas), guarda un PNG por
pantalla y arma un informe HTML autocontenido con las imagenes en base64.

Se ejecuta con un Python que tenga tkinter y Pillow:

    .venv_shots/Scripts/python.exe docs/evidencia_gui/make_evidence.py

Antes de empezar se fija PYTHON_APP_HOME a un directorio temporal limpio, de
modo que la primera captura muestre el estado inicial (sin sesion).
"""

import base64
import io
import os
import sys
import tempfile
import time

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                       "apps", "Python_app"))
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Runtime limpio ANTES de importar core.config (que calcula RUNTIME_DIR al importar).
RUNTIME = tempfile.mkdtemp(prefix="pythonapp_evidence_")
os.environ["PYTHON_APP_HOME"] = RUNTIME
sys.path.insert(0, APP_DIR)

from PIL import ImageGrab  # noqa: E402

from core.services import ServiceHub  # noqa: E402
from ui.app_window import AppWindow    # noqa: E402

CAPTURAS = []   # (archivo, titulo, pie)


def pump(app, seconds=0.6):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def wait_for(app, predicate, timeout=25.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        app.update()
        time.sleep(0.05)
    return False


def is_usable(img):
    """Descarta capturas en negro (ventana aun sin pintar)."""
    small = img.convert("L").resize((40, 30))
    px = list(small.getdata())
    return (sum(px) / len(px)) > 25


def shot(app, name, title, caption, widget=None):
    # 1180x940: la pantalla de configuracion necesita algo mas de alto que el
    # tamano por defecto (1200x780) para mostrar el formulario completo con sus
    # botones; en uso real la ventana se maximiza.
    app.geometry("1180x940+20+10")
    app.update()
    pump(app, 0.35)

    for _ in range(4):
        grab = ImageGrab.grab()
        sx = grab.width / app.winfo_screenwidth()
        sy = grab.height / app.winfo_screenheight()
        target = widget or app
        x = target.winfo_rootx() * sx
        y = target.winfo_rooty() * sy
        w = target.winfo_width() * sx
        h = target.winfo_height() * sy
        box = (max(0, int(x)), max(0, int(y)),
               min(grab.width, int(x + w)), min(grab.height, int(y + h)))
        img = grab.crop(box)
        if is_usable(img):
            break
        pump(app, 0.5)

    path = os.path.join(OUT_DIR, name + ".png")
    img.save(path)
    CAPTURAS.append((name + ".png", title, caption))
    print("  [OK] %s  (%dx%d)" % (name, img.width, img.height))
    return img


def main():
    print("Runtime temporal:", RUNTIME)
    services = ServiceHub()
    app = AppWindow(services)
    app.deiconify()
    app.attributes("-topmost", True)
    app.lift()
    app.focus_force()
    pump(app, 4.0)

    # --- 1. Pantalla de inicio de sesion -------------------------------------
    app.show("login")
    pump(app, 1.0)
    shot(app, "01_login", "Inicio de sesion",
         "Pantalla de autenticacion. En la cabecera ya se ven los <b>seis semaforos</b> "
         "de los microservicios, uno por servicio.")

    # --- 2. Semaforo en detalle ----------------------------------------------
    app.show("login")
    pump(app, 0.6)
    lights = app.lights["login"].master   # el marco que contiene las 6 luces
    shot(app, "02_semaforo", "Semaforo de los seis microservicios",
         "Los seis indicadores: Login, Libros, Usuarios, Autores, Pedidos y Pagos. "
         "En rojo cuando el servicio no responde (aqui no hay ninguno levantado), "
         "ambar si responde pero su dependencia no, verde si todo esta operativo.",
         widget=lights)

    # --- 3. Configuracion del servidor (pantalla nueva) ----------------------
    app.show("settings")
    pump(app, 1.2)
    shot(app, "03_configuracion", "Configuracion del servidor",
         "Formulario con las direcciones de los <b>seis</b> servicios y, arriba, el "
         "<b>conmutador de esquema</b> http/https: por defecto http, y al cambiarlo se "
         "reescriben todas las direcciones y la preferencia queda guardada en "
         "<code>runtime/config.json</code>.")

    # --- 4. Catalogo ---------------------------------------------------------
    app.show("catalog")
    pump(app, 1.5)
    shot(app, "04_catalogo", "Catalogo de libros",
         "Vista de catalogo. Sin los servicios levantados, la carga falla de forma "
         "controlada y la aplicacion lo informa sin caerse.")

    # --- 5. Semaforo tras la comprobacion automatica -------------------------
    app.show("settings")
    pump(app, 0.8)
    app.check_services_now()
    pump(app, 6.0)
    shot(app, "05_semaforo_en_vivo", "Semáforo tras comprobar los servicios",
         "El semáforo se actualiza solo (o al pulsar <i>Comprobar ahora</i>) consultando "
         "<code>GET /health</code> en los seis servicios. Aquí ninguno está levantado, así "
         "que los seis aparecen en rojo («Sin respuesta») con la hora de la comprobación: "
         "un servicio caído se distingue de uno degradado (ámbar) y de uno operativo (verde).")

    app.destroy()
    build_report()
    print("\nInforme: %s" % os.path.join(OUT_DIR, "informe_gui.html"))


def build_report():
    filas = []
    for archivo, titulo, pie in CAPTURAS:
        ruta = os.path.join(OUT_DIR, archivo)
        with open(ruta, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        filas.append(f"""
    <figure>
      <figcaption><span class="n">{len(filas)+1:02d}</span> {titulo}</figcaption>
      <img src="data:image/png;base64,{b64}" alt="{titulo}">
      <p class="pie">{pie}</p>
    </figure>""")

    doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Evidencia grafica - Cliente Tk</title>
<style>
  @page {{ size: A4 portrait; margin: 14mm 12mm; }}
  body {{ font:14px/1.55 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;
         color:#1c2230; margin:0; padding:28px; background:#f6f8fb; }}
  .hoja {{ max-width:920px; margin:0 auto; }}
  h1 {{ font-size:23px; margin:0 0 4px; }}
  .sub {{ color:#5b6675; font-size:13px; margin-bottom:22px; }}
  figure {{ background:#fff; border:1px solid #e3e7ee; border-radius:10px;
            padding:14px; margin:0 0 20px; page-break-inside:avoid; }}
  figcaption {{ font-weight:700; font-size:14.5px; margin-bottom:10px; }}
  figcaption .n {{ background:#2b5cd9; color:#fff; border-radius:20px;
                   padding:1px 9px; font-size:11.5px; margin-right:8px; }}
  img {{ width:100%; border:1px solid #e3e7ee; border-radius:7px; display:block; }}
  .pie {{ color:#5b6675; font-size:12.8px; margin:10px 2px 0; }}
  code {{ background:#eef1f6; padding:1px 5px; border-radius:4px; font-size:12.5px; }}
</style></head><body><div class="hoja">
  <h1>Evidencia grafica &mdash; cliente de escritorio (Tkinter)</h1>
  <div class="sub">
    Fabi&aacute;n Azaed Orta Singlaterry &middot; matr&iacute;cula 613504 &middot; UDEM SC-2236<br>
    Capturas de la aplicaci&oacute;n <b>real en ejecuci&oacute;n</b>, tomadas con
    <code>ImageGrab</code> (Pillow). Cada pantalla indica qu&eacute; se ve.
  </div>
  {''.join(filas)}
</div></body></html>
"""
    with open(os.path.join(OUT_DIR, "informe_gui.html"), "w", encoding="utf-8") as fh:
        fh.write(doc)


if __name__ == "__main__":
    main()

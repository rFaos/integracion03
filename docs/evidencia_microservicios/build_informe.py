#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el informe HTML de evidencia a partir del log del E2E.

Se ejecuta desde la raíz del repo:

    apps/services/login/venv/Scripts/python.exe \
        docs/evidencia_microservicios/build_informe.py

Lee `e2e_microservicios.log` y produce `informe_e2e.html` autocontenido
(sin recursos externos, imprimible a PDF con Edge headless).
"""

import html
import os
import re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "e2e_microservicios.log")
OUT = os.path.join(BASE, "informe_e2e.html")

SECCIONES = {
    "0. Carga de los servicios": "Carga de los servicios",
    "1. Login real": "Login real",
    "2. Microservicio users": "Servicio de usuarios (5002)",
    "3. Microservicio autores": "Servicio de autores (5003)",
    "4. Microservicio pedidos": "Servicio de pedidos (5004)",
    "5. Microservicio pagos": "Servicio de pagos (5005)",
    "6. Revocacion": "Revocación del token",
    "7. Redis caido": "Redis caído (política de fallo)",
    "Limpieza": "Limpieza de datos de prueba",
}


def leer_lineas():
    with open(LOG, "r", encoding="utf-8") as fh:
        return [ln.rstrip("\n") for ln in fh]


def parsear(lineas):
    """Devuelve [(titulo_seccion, [(ok, texto, detalle)])]."""
    grupos, actual = [], None
    for ln in lineas:
        s = ln.strip()
        if not s:
            continue
        if set(s) == {"="}:          # separador puro (====...), no es un título
            continue
        if s.startswith("==") and s.endswith("=="):
            titulo = s.strip("= ").strip()
            actual = (titulo, [])
            grupos.append(actual)
            continue
        m = re.match(r"^\[(OK|FALLO|ERROR)\s*\]\s*(.*)$", s)
        if m and actual is not None:
            estado, resto = m.group(1), m.group(2)
            texto, _, detalle = resto.partition("  -> ")
            actual[1].append((estado, texto.strip(), detalle.strip()))
    return grupos


def etiqueta(titulo):
    for clave, nombre in SECCIONES.items():
        if clave.lower() in titulo.lower():
            return nombre
    return titulo


def fila(estado, texto, detalle):
    ok = estado == "OK"
    marca = "&#10003;" if ok else "&#10007;"
    clase = "ok" if ok else "bad"
    det = f'<span class="det">{html.escape(detalle)}</span>' if detalle else ""
    return (f'<tr class="{clase}"><td class="ic">{marca}</td>'
            f'<td>{html.escape(texto)}{det}</td></tr>')


def main():
    lineas = leer_lineas()
    grupos = parsear(lineas)

    total = sum(len(c) for _, c in grupos)
    oks = sum(1 for _, c in grupos for e, _, _ in c if e == "OK")
    fallos = total - oks

    bloques = []
    for titulo, checks in grupos:
        if not checks:               # sección sin comprobaciones: no se pinta
            continue
        filas = "\n".join(fila(*c) for c in checks)
        bloques.append(
            f'<section><h2>{html.escape(etiqueta(titulo))}'
            f'<span class="n">{len(checks)}</span></h2>'
            f'<table><tbody>{filas}</tbody></table></section>'
        )

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evidencia E2E &mdash; Microservicios Library</title>
<style>
  :root {{
    --tinta:#1c2230; --suave:#5b6675; --linea:#e3e7ee;
    --fondo:#f6f8fb; --panel:#ffffff; --ok:#0f8a4d; --bad:#c0392b;
    --acento:#2b5cd9;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; padding:48px 24px; background:var(--fondo); color:var(--tinta);
    font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }}
  .hoja {{ max-width:900px; margin:0 auto; }}
  header {{
    border-bottom:3px solid var(--acento); padding-bottom:20px; margin-bottom:28px;
  }}
  h1 {{ margin:0 0 6px; font-size:26px; letter-spacing:-.02em; }}
  .sub {{ color:var(--suave); font-size:14px; }}
  .kpis {{ display:flex; gap:14px; flex-wrap:wrap; margin:24px 0 32px; }}
  .kpi {{
    flex:1 1 150px; background:var(--panel); border:1px solid var(--linea);
    border-radius:10px; padding:16px 18px;
  }}
  .kpi b {{ display:block; font-size:28px; line-height:1.1; }}
  .kpi span {{ color:var(--suave); font-size:12.5px; text-transform:uppercase;
               letter-spacing:.06em; }}
  .kpi.ok b {{ color:var(--ok); }}
  .kpi.bad b {{ color:var(--bad); }}
  section {{
    background:var(--panel); border:1px solid var(--linea); border-radius:10px;
    padding:6px 18px 14px; margin-bottom:16px;
  }}
  h2 {{
    font-size:15px; margin:14px 0 10px; display:flex; align-items:center; gap:10px;
  }}
  h2 .n {{
    background:var(--acento); color:#fff; font-size:11.5px; font-weight:600;
    border-radius:20px; padding:1px 9px;
  }}
  table {{ width:100%; border-collapse:collapse; }}
  td {{ padding:6px 4px; border-top:1px solid var(--linea); vertical-align:top;
        font-size:13.5px; }}
  td.ic {{ width:22px; text-align:center; font-weight:700; }}
  tr.ok td.ic {{ color:var(--ok); }}
  tr.bad td.ic {{ color:var(--bad); }}
  .det {{
    display:inline-block; margin-left:8px; color:var(--suave);
    font-family:"Cascadia Code",Consolas,monospace; font-size:12px;
  }}
  footer {{ color:var(--suave); font-size:12.5px; margin-top:28px; }}
  code {{ background:#eef1f6; padding:1px 5px; border-radius:4px;
          font-size:12.5px; }}
  @media print {{
    body {{ background:#fff; padding:0; }}
    section, .kpi {{ break-inside:avoid; }}
  }}
</style>
</head>
<body>
<div class="hoja">
  <header>
    <h1>Evidencia de integración &mdash; 4 microservicios nuevos</h1>
    <div class="sub">
      Fabián Azaed Orta Singlaterry &middot; matrícula 613504 &middot; UDEM SC-2236<br>
      Prueba extremo a extremo con <strong>login real</strong>, PostgreSQL real y
      Redis compartido. Generado el {ahora}.
    </div>
  </header>

  <div class="kpis">
    <div class="kpi ok"><b>{oks}/{total}</b><span>Comprobaciones OK</span></div>
    <div class="kpi"><b>4</b><span>Servicios nuevos</span></div>
    <div class="kpi bad"><b>{fallos}</b><span>Fallos</span></div>
    <div class="kpi"><b>5</b><span>Servicios con Redis</span></div>
  </div>

  <p style="color:var(--suave);font-size:13.5px">
    La prueba no fabrica tokens: hace <code>POST /login</code> contra el servicio
    real (con CAPTCHA), obtiene un JWT y lo usa contra los cuatro servicios. La
    revocación se propaga por Redis y la política de fallo se comprueba apagando
    Redis a propósito.
  </p>

  {''.join(bloques)}

  <footer>
    Fuente: <code>tests/e2e_microservicios.py</code> &middot;
    log: <code>e2e_microservicios.log</code>.<br>
    El mismo comando que genera este informe es reproducible con
    <code>apps/services/login/venv/Scripts/python.exe tests/e2e_microservicios.py</code>.
  </footer>
</div>
</body>
</html>
"""
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("Informe escrito en %s" % OUT)
    print("Comprobaciones: %d/%d OK, %d fallos." % (oks, total, fallos))


if __name__ == "__main__":
    main()

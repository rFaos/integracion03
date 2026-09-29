"""
==============================================================================
EMPAQUETADO DEL ENTREGABLE JWT
==============================================================================
Arma un .zip con dos cosas:

  1. `entrega_jwt/` completo (reflexion, evidencia, capturas, coleccion Postman,
     pruebas E2E y sus bitacoras, herramientas).
  2. Los ARCHIVOS FUENTE que se modificaron o crearon, conservando su ruta
     relativa dentro del monorepo, para que se pueda ver el diff contra el repo.

No incluye `node_modules/` ni los `venv/`: son dependencias reinstalables.

USO
---
    python entrega_jwt/tools/empaquetar.py
==============================================================================
"""

import os
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DESTINO = ROOT / "entrega_jwt" / "Libreria_JWT_UDEM_613504.zip"
PREFIJO = "Libreria_JWT_UDEM_613504"

# Archivos fuente tocados por esta actividad (rutas relativas al monorepo).
FUENTES = [
    # --- Servicio de login (emisor del JWT) ---
    "apps/services/login/jwt_utils.py",
    "apps/services/login/app.py",
    "apps/services/login/sql/03_migration_jwt.sql",
    "apps/services/login/tests/smoke_test.py",
    "apps/services/login/README.md",
    "apps/services/login/.env.example",
    # --- Servicio de libros (verificador + guardia por metodo) ---
    "apps/services/soap/jwt_auth.py",
    "apps/services/soap/app.py",
    "apps/services/soap/README.md",
    "apps/services/soap/.env.example",
    # --- Cliente Python TK (Bearer + refresco automatico + bitacora) ---
    "apps/Python_app/main.py",
    "apps/Python_app/README.md",
    "apps/Python_app/config.example.json",
    "apps/Python_app/core/trace.py",
    "apps/Python_app/core/http_client.py",
    "apps/Python_app/core/auth_service.py",
    "apps/Python_app/core/session_store.py",
    "apps/Python_app/core/services.py",
    "apps/Python_app/core/config.py",
    # --- Cliente Electron (campo JWT opcional) ---
    "apps/ElectronApp/index.html",
    "apps/ElectronApp/renderer.js",
    "apps/ElectronApp/README.md",
]

LEEME = """ENTREGABLE - AUTORIZACION POR JWT EN LOS MICROSERVICIOS DE LA LIBRERIA
==========================================================================

Integracion de Aplicaciones Computacionales - SC-2236
Fabian Azaed Orta Singlaterry - matricula 613504
Prof. Dr. Raul Morales Salcedo - Universidad de Monterrey

QUE HAY AQUI
------------

  entrega_jwt/
      README.md        indice del entregable
      REFLEXION.md     las cinco trampas del enunciado, la decision por metodo
                       HTTP y por que JWT importa en la arquitectura REST
      EVIDENCIA.md     reporte con las 23 capturas embebidas
      postman/         coleccion + entorno importables (apuntan a la IP)
      capturas/        23 PNG de ejecuciones reales
      informes/        los HTML que alimentan las capturas
      tools/           generadores de informes y capturas
      evidencia_e2e.txt / evidencia_app_python.txt / flujo_e2e.json
      newman_run.txt   corrida de la coleccion Postman con Newman

  apps/...             los archivos fuente que se modificaron o crearon,
                       conservando su ruta dentro del monorepo.

LA REGLA QUE SE IMPLEMENTA
--------------------------

  GET, HEAD, OPTIONS sobre /books y /books/{isbn}  ->  PUBLICO
  POST, PUT, PATCH, DELETE                          ->  Authorization: Bearer <JWT>

  La autorizacion se decide POR METODO HTTP, no por ruta. Es lo unico que cubre a
  la vez el catalogo publico y los alias de escritura (/api/book/insert|update|
  patch|delete), incluido POST /api/book/delete/<isbn>, que es un POST que BORRA.

RESULTADOS DE LAS SUITES
------------------------

  Login (smoke)                      69 / 69 aserciones
  Flujo E2E (28 intercambios)        41 / 41 aserciones
  App Python TK con Bearer           16 / 16 aserciones
  Coleccion Postman (Newman)         28 / 28 peticiones, 45 / 45 aserciones

  Los dos /health reportan la misma huella del secreto: 998b858a0b50

COMO LEVANTARLO
---------------

  1) Servicio de login    ->  python apps/services/login/app.py     (puerto 5000)
  2) Servicio de libros   ->  python apps/services/soap/app.py      (puerto 5001)
  3) Requiere PostgreSQL 17 con la base `library` y las migraciones de
     apps/services/login/sql/ aplicadas (incluida 03_migration_jwt.sql).

  El smoke test del servicio de login necesita su propio entorno virtual:
     apps/services/login/venv/Scripts/python.exe apps/services/login/tests/smoke_test.py

  Para correr la coleccion de Postman sin abrir Postman:
     npx newman run entrega_jwt/postman/Libreria_JWT_UDEM_613504.postman_collection.json \\
       -e entrega_jwt/postman/Libreria_JWT_UDEM_613504.postman_environment.json

NOTA SOBRE EL SECRETO
---------------------

  El .env real NO se incluye (esta en .gitignore). Solo va `.env.example`.
  El secreto HS256 del entorno de Postman es el de la instancia de pruebas: en
  produccion iria en variables de entorno o en un secret manager, nunca en el
  codigo fuente.

  Tampoco se incluye `entrega_jwt/runtime_demo/session.json`, que guarda el correo
  y la contrasena de la cuenta desechable que crea la prueba de la app Python.
  La prueba lo regenera en cada corrida.
"""


def main():
    faltantes = [f for f in FUENTES if not (ROOT / f).exists()]
    if faltantes:
        print("(aviso) no se encontraron estos archivos:")
        for f in faltantes:
            print("   -", f)

    total = 0
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        # 1) el LEEME
        z.writestr(PREFIJO + "/LEEME.txt", LEEME)
        total += 1

        # 2) la carpeta entrega_jwt completa (sin el propio zip)
        #
        #    `runtime_demo/session.json` se excluye a propósito: guarda el correo y
        #    la contraseña de la cuenta desechable que crea la prueba de la app
        #    Python. La prueba lo regenera en cada corrida, así que no aporta nada
        #    al entregable y sí sería un archivo con credenciales dentro.
        excluidos = {"runtime_demo/session.json"}
        for ruta in sorted((ROOT / "entrega_jwt").rglob("*")):
            if ruta.is_dir() or ruta == DESTINO or ruta.suffix == ".pyc":
                continue
            rel = str(ruta.relative_to(ROOT / "entrega_jwt")).replace("\\", "/")
            if rel in excluidos:
                print("  (excluido) %s" % rel)
                continue
            z.write(ruta, PREFIJO + "/" + str(ruta.relative_to(ROOT)).replace("\\", "/"))
            total += 1

        # 3) los archivos fuente modificados
        for rel in FUENTES:
            origen = ROOT / rel
            if origen.exists():
                z.write(origen, PREFIJO + "/" + rel)
                total += 1

    print("escrito: %s" % DESTINO)
    print("archivos: %d" % total)
    print("tamano:   %.1f MB" % (DESTINO.stat().st_size / 1024 / 1024))


if __name__ == "__main__":
    main()

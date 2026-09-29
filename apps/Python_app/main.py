"""Aplicacion de escritorio: cliente de los microservicios de Login y Libros.

Ejecucion:
    python main.py

Requisitos: Python 3.10 o superior con Tkinter (incluido en el instalador
oficial de Windows). No hay dependencias obligatorias de terceros; Pillow es
opcional y solo mejora la carga de portadas.

Este archivo es el unico punto de arranque: arma los servicios, crea la ventana
y entrega el control al bucle de eventos de Tkinter.
"""

import os
import sys
import traceback

# Permite ejecutar `python main.py` desde cualquier directorio.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_python_version():
    if sys.version_info < (3, 10):
        print("Se requiere Python 3.10 o superior. Version actual: "
              f"{sys.version_info.major}.{sys.version_info.minor}")
        return False
    return True


def check_tkinter():
    try:
        import tkinter  # noqa: F401
        return True
    except ImportError:
        print("No se encontro Tkinter, necesario para la interfaz grafica.")
        print("En Windows reinstala Python marcando la opcion 'tcl/tk and IDLE'.")
        print("En Debian/Ubuntu: sudo apt install python3-tk")
        return False


def main():
    if not check_python_version() or not check_tkinter():
        return 2

    from core.services import ServiceHub
    from ui.app_window import AppWindow

    services = ServiceHub()
    # Cabecera de arranque en la terminal: direcciones de los microservicios,
    # esquema de autorizacion (Bearer JWT) y credencial cargada, si la hay.
    services.startup_banner()
    app = AppWindow(services)

    # Cualquier excepcion no controlada se informa sin cerrar la aplicacion de
    # golpe: el requisito de tolerancia a fallos incluye no caerse sola.
    def report_callback_exception(exc_type, exc_value, exc_tb):
        detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(detail, file=sys.stderr)
        try:
            app.handle_error(exc_value, "completar la operacion")
        except Exception:
            pass

    app.report_callback_exception = report_callback_exception
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

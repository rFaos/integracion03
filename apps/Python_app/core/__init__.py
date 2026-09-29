"""Nucleo de la aplicacion de escritorio (configuracion, HTTP, sesion y servicios).

Cada modulo tiene una unica responsabilidad:

    config.py         -> donde viven las direcciones de los microservicios
    http_client.py    -> como se habla HTTP con ellos
    session_store.py  -> que se conserva en el disco del cliente
    auth_service.py   -> microservicio de login (registro, sesion, perfil)
    books_service.py  -> microservicio de libros (catalogo y CRUD)
    health_service.py -> semaforo de estado de los servicios

La interfaz grafica (paquete `ui`) nunca importa `urllib` ni construye
direcciones: siempre pasa por estos modulos.
"""

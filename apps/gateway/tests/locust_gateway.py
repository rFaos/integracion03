"""Carga: mismo escenario directo al servicio de libros y a traves del gateway.

    # directo (sin proxy)
    locust -f locust_gateway.py --headless -u 20 -r 10 -t 30s -H http://127.0.0.1:5001 --csv=../evidencias/carga_directo
    # por nginx (PREFIX=/api/books)
    PREFIX=/api/books locust -f locust_gateway.py --headless -u 20 -r 10 -t 30s -H http://127.0.0.1:8080 --csv=../evidencias/carga_gateway

Nota: el limite de tasa del gateway (20 r/s por IP, burst 40) se alcanza con
este escenario porque todos los usuarios salen de la misma IP; los 429 cuentan
como fallos y son justamente la proteccion que se quiere demostrar.
"""
import os

from locust import HttpUser, between, task

PREFIX = os.environ.get("PREFIX", "")


class Lector(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(3)
    def catalogo(self):
        self.client.get(f"{PREFIX}/books?format=json", name="GET /books")

    @task(1)
    def health(self):
        self.client.get(f"{PREFIX}/health", name="GET /health")

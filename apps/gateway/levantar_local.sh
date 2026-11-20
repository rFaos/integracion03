#!/usr/bin/env bash
# ==============================================================================
# levantar_local.sh - Demo local del Library API Gateway (Windows + Git Bash)
# ==============================================================================
#   ./levantar_local.sh start   -> Redis (Docker), 7 servicios + 2a instancia de
#                                  Libros en :6001, y nginx (Docker) en :8080
#   ./levantar_local.sh stop    -> detiene todo
#   ./levantar_local.sh status  -> /health de cada servicio A TRAVES del gateway
#
# Requisitos: PostgreSQL local con la base "library", Docker Desktop, y un venv
# con las dependencias de los servicios (por defecto el de services/login).
# El .env de cada servicio se queda fuera del repo; solo existe .env.example.
# ==============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SVC="$HERE/../services"
PY="${PY:-$SVC/login/venv/Scripts/python.exe}"
RUN="$HERE/run"; mkdir -p "$RUN" "$HERE/logs"

# nombre|carpeta|puerto
SERVICES=(
  "login|login|5000"
  "books|soap|5001"
  "books2|soap|6001"
  "users|users|5002"
  "autores|autores|5003"
  "pedidos|pedidos|5004"
  "pagos|pagos|5005"
  "rastreo|rastreo|5006"
)

# PID de Windows que escucha en el puerto (vacio si nadie).
port_pid() { netstat -ano | grep LISTENING | grep -E "0\.0\.0\.0:$1 " | awk '{print $5}' | head -1 | grep .; }

start() {
  # Redis con la misma contrasena que usan los servicios (se lee del .env, no se imprime)
  if ! docker ps --format '{{.Names}}' | grep -q '^library-redis$'; then
    RP=$(grep ^REDIS_URL= "$SVC/login/.env" | sed -E 's#^REDIS_URL=redis://:([^@]*)@.*#\1#')
    docker rm -f library-redis >/dev/null 2>&1
    docker run -d --name library-redis -p 127.0.0.1:6379:6379 redis:7-alpine \
      redis-server --requirepass "$RP" >/dev/null && echo "redis       OK"
  fi
  for s in "${SERVICES[@]}"; do
    IFS='|' read -r name dir port <<<"$s"
    if port_pid "$port" >/dev/null; then echo "$name -> :$port ya estaba arriba"; continue; fi
    ( cd "$SVC/$dir" && PORT=$port FLASK_DEBUG=False \
        PEDIDOS_BASE_URL=http://127.0.0.1:5004 \
        nohup "$PY" app.py >"$HERE/logs/$name.log" 2>&1 & echo $! >"$RUN/$name.pid" )
    echo "$name -> :$port (log: logs/$name.log)"
  done
  (cd "$HERE" && docker compose up -d)
}

stop() {
  for s in "${SERVICES[@]}"; do
    IFS='|' read -r name dir port <<<"$s"
    pid=$(port_pid "$port") && taskkill //F //T //PID "$pid" >/dev/null 2>&1 && echo "$name :$port detenido"
  done
  rm -f "$RUN"/*.pid
  (cd "$HERE" && docker compose down)
  docker rm -f library-redis >/dev/null 2>&1
  echo "detenido"
}

status() {
  curl -s http://127.0.0.1:8080/health; echo
  for s in login books users autores pedidos pagos rastreo; do
    printf '%-8s ' "$s"; curl -s -o /dev/null -w '%{http_code}  %{time_total}s\n' "http://127.0.0.1:8080/api/$s/health"
  done
}

# Apaga UNA instancia (para la demo de falla): ./levantar_local.sh kill 5001
kill_port() { pid=$(port_pid "$1") && taskkill //F //T //PID "$pid" >/dev/null 2>&1 && echo ":$1 apagado"; }

case "${1:-status}" in
  start) start;; stop) stop;; status) status;; kill) kill_port "$2";;
  *) echo "uso: $0 start|stop|status|kill <puerto>";;
esac

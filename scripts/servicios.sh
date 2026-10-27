#!/usr/bin/env bash
# ==============================================================================
# servicios.sh - Arranque, parada y estado de TODOS los microservicios de Library
# ==============================================================================
# PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
# AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
# UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236
#
# UBICACION EN LA VM: /opt/udem/integracion03/scripts/servicios.sh
#
# POR QUE EXISTE ESTE SCRIPT
# --------------------------
# Antes cada servicio se levantaba a mano con `flask run` en primer plano, y eso
# obligaba a tener una sesion SSH (o un tmux) POR SERVICIO: con 6 servicios eso
# deja de ser viable. Este script:
#
#   * Levanta cada servicio DESACOPLADO en segundo plano (nohup + exec), asi
#     que sobrevive al cierre de la sesion SSH.
#   * Usa gunicorn (ya esta en los requirements) en vez de `flask run`, que es
#     solo para desarrollo.
#   * Es IDEMPOTENTE: `start` sobre algo que ya corre no lo duplica.
#   * Espera a que cada servicio responda /health antes de decir "OK".
#   * Deja PID por servicio y logs separados, para poder pararlos y depurarlos.
#
# USO
# ---
#   ./scripts/servicios.sh start            # levanta todos
#   ./scripts/servicios.sh stop             # detiene todos
#   ./scripts/servicios.sh restart          # stop + start
#   ./scripts/servicios.sh status           # que esta corriendo y si responde
#   ./scripts/servicios.sh health           # solo la sonda /health
#   ./scripts/servicios.sh logs books       # sigue el log de un servicio
#   ./scripts/servicios.sh redis            # comprueba Redis con la REDIS_URL real
#   ./scripts/servicios.sh deploy           # git pull + restart (el flujo normal)
#
# COMO AGREGAR UN MICROSERVICIO NUEVO
# -----------------------------------
# Solo hay que anadir UNA linea al arreglo SERVICES de abajo. Nada mas cambia:
# el script crea su PID, su log, su sonda /health y su parada automaticamente.
# Por eso cada servicio sigue siendo independiente y desacoplado.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. CONFIGURACION (todo se puede sobreescribir por variable de entorno)
# ------------------------------------------------------------------------------
REPO_DIR="${REPO_DIR:-/opt/udem/integracion03}"
RUN_DIR="${RUN_DIR:-/tmp/integracion03}"
LOG_DIR="${LOG_DIR:-$REPO_DIR/logs}"
VENV_DIR="${VENV_DIR:-}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-25}"   # segundos a esperar por /health
BIND_HOST="${BIND_HOST:-0.0.0.0}"

# Registro de servicios.  Formato:  nombre|subruta|puerto|workers|nota
#
#   * workers = 1 en el login es DELIBERADO: el CAPTCHA de un solo uso y el
#     limitador de peticiones viven en memoria del proceso. Con 2+ workers, un
#     CAPTCHA resuelto en un worker se verifica en otro y falla con
#     CAPTCHA_ALREADY_USED. Cuando ese estado se mueva a Redis, se puede subir.
#     (Es justo la siguiente mejora natural, ahora que Redis ya esta puesto.)
SERVICES=(
  "login|apps/services/login|5000|1|autenticacion, JWT y gestion de usuarios"
  "books|apps/services/soap|5001|2|catalogo de libros (REST + SOAP)"
  # Para agregar otro servicio basta con añadir una línea con el mismo formato.
  "users|apps/services/users|5002|2|usuarios, roles, correos y contrasenas"
  "autores|apps/services/autores|5003|2|autores y su relacion con libros"
  "pedidos|apps/services/pedidos|5004|2|pedidos, lineas, stock y estados"
  "pagos|apps/services/pagos|5005|2|registro de pagos y estado de pedidos"
)

# ------------------------------------------------------------------------------
# 2. COLORES Y UTILIDADES
# ------------------------------------------------------------------------------
if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_ERR=$'\033[31m'; C_WARN=$'\033[33m'
  C_INFO=$'\033[36m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_OK=''; C_ERR=''; C_WARN=''; C_INFO=''; C_BOLD=''; C_OFF=''
fi

info() { printf '%s\n' "${C_INFO}$*${C_OFF}"; }
ok()   { printf '%s\n' "  ${C_OK}[OK]${C_OFF} $*"; }
warn() { printf '%s\n' "  ${C_WARN}[AVISO]${C_OFF} $*"; }
err()  { printf '%s\n' "  ${C_ERR}[ERROR]${C_OFF} $*" >&2; }
title(){ printf '\n%s\n' "${C_BOLD}$*${C_OFF}"; }

# Oculta la contrasena de una URL antes de imprimirla.
mask_url() { printf '%s' "$1" | sed -E 's#(://[^:/@]*:)[^@]*@#\1***@#'; }

# Devuelve el campo N (0-based) de una linea del registro SERVICES.
field() { printf '%s' "$1" | cut -d'|' -f"$2"; }

require_repo() {
  if [ ! -d "$REPO_DIR" ]; then
    err "No existe el repositorio en $REPO_DIR"
    err "Ajusta la ruta con:  REPO_DIR=/ruta/correcta $0 $*"
    exit 1
  fi
}

# ------------------------------------------------------------------------------
# 3. LOCALIZAR PYTHON Y GUNICORN
# ------------------------------------------------------------------------------
PYTHON_BIN=""
GUNICORN_BIN=""

resolve_binaries() {
  local candidate
  if [ -n "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/python" ]; then
    PYTHON_BIN="$VENV_DIR/bin/python"
  elif [ -x "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/.venv/bin/python"
  else
    candidate="$(command -v python3 || true)"
    PYTHON_BIN="$candidate"
  fi

  if [ -z "$PYTHON_BIN" ]; then
    err "No encontre python3. Define VENV_DIR=/ruta/al/venv"
    exit 1
  fi

  # gunicorn se busca junto al python elegido (asi respeta el venv del proyecto).
  local py_dir
  py_dir="$(dirname "$PYTHON_BIN")"
  if [ -x "$py_dir/gunicorn" ]; then
    GUNICORN_BIN="$py_dir/gunicorn"
  else
    GUNICORN_BIN="$(command -v gunicorn || true)"
  fi
}

# ------------------------------------------------------------------------------
# 4. REDIS (capa compartida)
# ------------------------------------------------------------------------------
# Lee la REDIS_URL REAL del .env del login y comprueba con ella, en vez de
# asumir 127.0.0.1:6379. Si la contrasena no coincide, esto lo detecta aqui y no
# en produccion con un 503 incomprensible.
redis_url_from_env() {
  local f="$REPO_DIR/apps/services/login/.env"
  [ -f "$f" ] || return 1
  grep -E '^[[:space:]]*REDIS_URL=' "$f" | tail -1 | sed -E 's/^[^=]*=//' | tr -d '\r'
}

check_redis() {
  title "Redis (capa compartida)"
  if ! command -v redis-cli >/dev/null 2>&1; then
    warn "redis-cli no esta instalado: no puedo comprobar Redis desde aqui."
    return 0
  fi

  local url
  url="$(redis_url_from_env || true)"
  if [ -z "$url" ]; then
    warn "No hay REDIS_URL en apps/services/login/.env"
    warn "Sin ella, login/books responden 503 en sesion, revocacion y escrituras."
    return 0
  fi
  info "  REDIS_URL = $(mask_url "$url")"

  if redis-cli -u "$url" ping >/dev/null 2>&1; then
    ok "Redis responde PONG con esa URL."
    return 0
  fi

  err "Redis NO responde con esa REDIS_URL."
  err "Revisa:  sudo systemctl status redis   |   requirepass en /etc/redis/redis.conf"
  return 1
}

# ------------------------------------------------------------------------------
# 5. GESTION DE CADA SERVICIO
# ------------------------------------------------------------------------------
pid_file() { printf '%s/%s.pid' "$RUN_DIR" "$1"; }
log_file() { printf '%s/%s.log' "$LOG_DIR" "$1"; }

# True si el proceso del servicio esta vivo (valida el PID, no solo el archivo).
is_running() {
  local pf; pf="$(pid_file "$1")"
  [ -f "$pf" ] || return 1
  local pid; pid="$(cat "$pf" 2>/dev/null || true)"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null
}

port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -qE "[:.]${port}[[:space:]]"
  else
    (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null && exec 3>&-
  fi
}

# Comprueba que el .env existe: es el fallo silencioso clasico del proyecto.
check_env() {
  local name="$1" dir="$2"
  if [ -f "$dir/.env" ]; then
    ok "$name: .env presente."
    return 0
  fi
  warn "$name: NO hay .env en $dir"
  warn "        Sin .env, JWT_SECRET queda vacio y TODA escritura responde 401."
  warn "        Crear con:  cp $dir/.env.example $dir/.env  y editar los valores."
  return 1
}

wait_health() {
  local name="$1" port="$2" i
  for i in $(seq 1 "$HEALTH_TIMEOUT"); do
    if curl -fsS --max-time 2 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      return 0
    fi
    if ! is_running "$name"; then
      return 2   # se murio durante el arranque
    fi
    sleep 1
  done
  return 1
}

start_one() {
  local name="$1" subpath="$2" port="$3" workers="$4" note="$5"
  local dir="$REPO_DIR/$subpath"

  if is_running "$name"; then
    ok "$name ya estaba corriendo (PID $(cat "$(pid_file "$name")")). No se toca."
    return 0
  fi

  if [ ! -d "$dir" ]; then
    warn "$name: no existe $dir todavia. Se omite."
    return 0
  fi
  if [ ! -f "$dir/app.py" ]; then
    warn "$name: falta $dir/app.py. Se omite."
    return 0
  fi

  if port_listening "$port"; then
    warn "$name: el puerto $port ya esta ocupado por otro proceso. Se omite."
    warn "        Averigua quien lo tiene con:  sudo ss -ltnp | grep :$port"
    return 1
  fi

  check_env "$name" "$dir" || true

  info "  Arrancando $name  ($note)  ->  ${BIND_HOST}:${port}  [${workers} worker(s)]"

  # Detalle importante: el PID que guardamos tiene que ser el REAL del servicio,
  # porque de el dependen `stop` y `status`. El patron
  #     ( cd dir && exec nohup gunicorn ... ) &
  # lo garantiza: el subshell hace `cd` y luego `exec`, que REEMPLAZA su imagen
  # por la del proceso (mismo PID), y `nohup` a su vez no bifurca: exec la orden
  # en el sitio. Asi `$!` es el PID del gunicorn, no el de un envoltorio que ya
  # murio. (Con `setsid` a secas, `$!` puede apuntar a un proceso que ya termino.)
  # `nohup` + stdin en /dev/null es lo que hace que sobreviva al cierre del SSH.
  ( cd "$dir" && \
    exec nohup "$GUNICORN_BIN" \
      --workers "$workers" \
      --bind "${BIND_HOST}:${port}" \
      --timeout 60 \
      --access-logfile - \
      --error-logfile - \
      app:app \
      >"$(log_file "$name")" 2>&1 </dev/null ) &
  echo $! >"$(pid_file "$name")"

  sleep 1
  wait_health "$name" "$port"
  local rc=$?
  case "$rc" in
    0) ok "$name: arriba y /health responde." ;;
    2) err "$name: el proceso murio al arrancar. Ultimas lineas del log:"
       tail -n 15 "$(log_file "$name")" | sed 's/^/        /' >&2
       return 1 ;;
    *) warn "$name: arranco pero /health no respondio en ${HEALTH_TIMEOUT}s."
       warn "        Puede estar aplicando migraciones. Revisa:  $0 logs $name"
       return 1 ;;
  esac
}

stop_one() {
  local name="$1"
  local pf; pf="$(pid_file "$name")"

  if ! is_running "$name"; then
    ok "$name no estaba corriendo."
    rm -f "$pf"
    return 0
  fi

  local pid; pid="$(cat "$pf")"
  info "  Deteniendo $name (PID $pid)..."
  kill "$pid" 2>/dev/null || true

  local i
  for i in $(seq 1 10); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done

  if kill -0 "$pid" 2>/dev/null; then
    warn "$name no respondio al cierre; se fuerza con SIGKILL."
    kill -9 "$pid" 2>/dev/null || true
  fi

  rm -f "$pf"
  ok "$name detenido."
}

status_one() {
  local name="$1" port="$3"
  # El color se aplica DESPUES de calcular el relleno: si se colorea primero,
  # los codigos ANSI cuentan como caracteres y la columna queda desalineada.
  if is_running "$name"; then
    local pid health=""
    pid="$(cat "$(pid_file "$name")" 2>/dev/null || echo '?')"
    if curl -fsS --max-time 2 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      health="/health OK"
    else
      health="/health sin respuesta"
    fi
    printf '  %-8s %s %-11s %-10s %s\n' \
      "$name" "${C_OK}$(printf '%-9s' ACTIVO)${C_OFF}" "$port" "$pid" "$health"
  else
    printf '  %-8s %s %-11s\n' \
      "$name" "${C_ERR}$(printf '%-9s' DETENIDO)${C_OFF}" "$port"
  fi
}

# ------------------------------------------------------------------------------
# 6. COMANDOS
# ------------------------------------------------------------------------------
cmd_start() {
  require_repo; resolve_binaries
  title "Arrancando microservicios"
  info "  python   = $PYTHON_BIN"
  info "  gunicorn = ${GUNICORN_BIN:-(no encontrado)}"
  if [ -z "$GUNICORN_BIN" ]; then
    err "gunicorn no esta instalado. Instala con:  $PYTHON_BIN -m pip install -r apps/services/login/requirements.txt"
    exit 1
  fi

  mkdir -p "$RUN_DIR" "$LOG_DIR"
  check_redis || true

  local rc=0 line
  for line in "${SERVICES[@]}"; do
    start_one "$(field "$line" 1)" "$(field "$line" 2)" "$(field "$line" 3)" \
              "$(field "$line" 4)" "$(field "$line" 5)" || rc=1
  done

  cmd_status
  return $rc
}

cmd_stop() {
  require_repo
  title "Deteniendo microservicios"
  local line
  for line in "${SERVICES[@]}"; do
    stop_one "$(field "$line" 1)"
  done
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_status() {
  require_repo
  title "Estado de los microservicios"
  printf '  %-8s %-9s %-11s %-10s %s\n' "SERVICIO" "ESTADO" "PUERTO" "PID" "SALUD"
  local line
  for line in "${SERVICES[@]}"; do
    status_one "$(field "$line" 1)" "$(field "$line" 2)" "$(field "$line" 3)"
  done
  printf '\n  Logs: %s\n' "$LOG_DIR"
}

cmd_health() {
  require_repo
  title "Sonda /health"
  local line name port
  for line in "${SERVICES[@]}"; do
    name="$(field "$line" 1)"; port="$(field "$line" 3)"
    if curl -fsS --max-time 3 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      ok "$name (:$port) responde /health"
    else
      err "$name (:$port) NO responde /health"
    fi
  done
}

cmd_logs() {
  require_repo
  local name="${1:-}"
  if [ -z "$name" ]; then
    err "Uso: $0 logs <nombre-de-servicio>"
    err "Disponibles: $(for l in "${SERVICES[@]}"; do printf '%s ' "$(field "$l" 1)"; done)"
    exit 1
  fi
  local lf; lf="$(log_file "$name")"
  [ -f "$lf" ] || { err "No hay log para '$name' en $lf"; exit 1; }
  info "Siguiendo $lf  (Ctrl-C para salir)"
  tail -n 40 -f "$lf"
}

cmd_redis() {
  require_repo
  check_redis
}

# Flujo normal del proyecto: subir a GitHub en local, bajar aqui y reiniciar.
cmd_deploy() {
  require_repo
  title "Actualizando desde GitHub"
  if [ ! -d "$REPO_DIR/.git" ]; then
    err "$REPO_DIR no es un repositorio git."
    exit 1
  fi
  git -C "$REPO_DIR" pull --ff-only
  ok "Repositorio actualizado."
  warn "Recordatorio: los .env NO viajan en git. Si cambio una variable,"
  warn "             hay que editarla a mano en la VM."
  cmd_restart
}

usage() {
  sed -n '3,30p' "$0" | sed 's/^# \{0,1\}//'
  printf '\nComandos: start | stop | restart | status | health | logs <svc> | redis | deploy\n'
}

# ------------------------------------------------------------------------------
# 7. PUNTO DE ENTRADA
# ------------------------------------------------------------------------------
main() {
  case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    health)  cmd_health ;;
    logs)    shift; cmd_logs "${1:-}" ;;
    redis)   cmd_redis ;;
    deploy)  cmd_deploy ;;
    ""|-h|--help|help) usage ;;
    *) err "Comando desconocido: $1"; usage; exit 1 ;;
  esac
}

main "$@"

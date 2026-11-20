#!/usr/bin/env bash
# ==============================================================================
# desplegar_gateway_gcp.sh - Instala el Library API Gateway (nginx) en la VM de
# Google Cloud (Debian/Ubuntu) delante de los microservicios.
# ==============================================================================
# Uso, dentro de la VM (repo clonado en /opt/udem/integracion03):
#
#   cd /opt/udem/integracion03 && git pull
#   sudo bash apps/gateway/gcp/desplegar_gateway_gcp.sh
#
# Que hace:
#   1. Instala nginx si falta.
#   2. Copia nginx.conf, la tabla de rutas y upstreams.local.conf (127.0.0.1).
#   3. Valida con nginx -t y recarga (si la validacion falla, NO toca nada).
#   4. Reinicia los microservicios escuchando SOLO en 127.0.0.1 (+ books2 :6001).
#
# Firewall (una sola vez, desde Cloud Shell o tu PC con gcloud):
#   gcloud compute firewall-rules create library-gateway-8080 \
#       --allow=tcp:8080 --target-tags=library-gateway --direction=INGRESS
#   gcloud compute instances add-tags <NOMBRE_VM> --tags=library-gateway --zone=<ZONA>
#   # y elimina/deshabilita las reglas que abrian 5000-5006:
#   gcloud compute firewall-rules list --filter="allowed[].ports:5000"
# ==============================================================================
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/udem/integracion03}"
GW="$REPO_DIR/apps/gateway/nginx"

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo"; exit 1; }

if ! command -v nginx >/dev/null; then
  apt-get update -y && apt-get install -y nginx
fi

# Respaldo de la configuracion actual, por si hay que volver atras.
BK="/etc/nginx.bak.$(date +%Y%m%d%H%M%S)"
cp -a /etc/nginx "$BK"
echo "Respaldo de /etc/nginx en $BK"

install -m 644 "$GW/nginx.conf"                   /etc/nginx/nginx.conf
install -m 644 "$GW/upstreams.local.conf"         /etc/nginx/upstreams.conf
install -m 644 "$GW/conf.d/library_gateway.conf"  /etc/nginx/conf.d/library_gateway.conf
# El sitio "default" de Debian escucha en :80 y no se necesita.
rm -f /etc/nginx/sites-enabled/default

if nginx -t; then
  systemctl enable nginx >/dev/null 2>&1 || true
  systemctl restart nginx
  echo "nginx OK en :8080"
else
  echo "nginx -t fallo: se restaura el respaldo"
  rm -rf /etc/nginx && cp -a "$BK" /etc/nginx
  exit 1
fi

# Microservicios solo en loopback: el unico puerto publico es el 8080.
SUDO_USER_HOME_RUN="sudo -u ${SUDO_USER:-$USER}"
$SUDO_USER_HOME_RUN env BIND_HOST=127.0.0.1 bash "$REPO_DIR/scripts/servicios.sh" restart || true

echo
echo "Prueba local en la VM:"
for s in login books users autores pedidos pagos; do
  printf '  %-8s ' "$s"; curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:8080/api/$s/health"
done
echo
echo "Desde tu PC: http://<IP_EXTERNA_VM>:8080/health"

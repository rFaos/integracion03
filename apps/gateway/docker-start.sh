#!/bin/sh
# Arranque del contenedor nginx: resuelve SOLO la IPv4 de la maquina anfitriona,
# la escribe en upstreams.conf (en lugar del marcador "library-host"), valida la
# configuracion con nginx -t y arranca nginx en primer plano.
IP=$(getent ahostsv4 host.docker.internal | awk 'NR==1{print $1}')
sed "s/library-host/${IP}/g" /etc/nginx/upstreams.tpl > /etc/nginx/upstreams.conf
echo "upstreams -> ${IP}"
nginx -t && exec nginx -g 'daemon off;'

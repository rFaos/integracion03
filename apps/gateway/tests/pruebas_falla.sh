#!/usr/bin/env bash
# Pruebas de FALLA del Library API Gateway (demo en vivo).
# Apaga la instancia :5001 de Libros y el servicio de Pagos, y muestra lo que
# responde nginx. Despues: ../levantar_local.sh start para volver a levantarlos.
# Salida: consola + ../evidencias/pruebas_falla.log
cd "$(dirname "$0")/.." || exit 1
GW="${GATEWAY:-http://127.0.0.1:8080}"
{
echo "=== Pruebas de FALLA contra $GW ($(date '+%Y-%m-%d %H:%M:%S')) ==="
echo; echo "[RF3] Antes de la falla: round robin normal"
for i in 1 2 3 4; do curl -s -o /dev/null -w "  peticion $i -> %{http_code}  X-Upstream: %header{x-upstream}\n" "$GW/api/books/books?format=json"; done

echo; echo "[RF4] Se apaga la instancia de Libros en :5001 (queda :6001)"
./levantar_local.sh kill 5001 | sed 's/^/  /'; sleep 1
for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w "  peticion $i -> %{http_code}  X-Upstream: %header{x-upstream}  (%{time_total}s)\n" "$GW/api/books/books?format=json"; done
echo "  => el cliente siempre recibe 200: nginx reintenta en :6001 (proxy_next_upstream)"
echo "     y aparta :5001 de la rotacion 10 s (max_fails=2 fail_timeout=10s)"

echo; echo "[RF6] Se apaga Pagos (:5005, instancia unica) -> 503 JSON con request_id"
./levantar_local.sh kill 5005 | sed 's/^/  /'; sleep 1
curl -s -w "\n  HTTP %{http_code}\n" "$GW/api/pagos/health" | sed 's/^/  /'

echo; echo "Registro de nginx (una linea por peticion: request_id, upstream, codigo, tiempos):"
tail -11 logs/gateway_access.log | sed 's/^/  /'
} 2>&1 | tee evidencias/pruebas_falla.log

"""Bitacora de las peticiones HTTP para la TERMINAL.

Requisito de la actividad: la aplicacion debe mostrar en la terminal un log de
las peticiones que realiza, junto con un **encabezado de lo que seria el token**
(la cabecera `Authorization: Bearer ...` y el resumen de sus reclamaciones).

Este modulo se encarga de dos cosas:

  1. `format_block(entry)`  -> bloque multilinea que se imprime en la terminal.
  2. `format_summary(entry)` -> una sola linea, para la bitacora de la interfaz.

IMPORTANTE: `decode_jwt_payload()` decodifica el token SIN verificar la firma.
Es solo para MOSTRAR informacion en la bitacora; el cliente no tiene por que
confiar en lo que el mismo decodifica. La verificacion real (firma, vigencia,
emisor y audiencia) la hace el servidor. Se documenta aqui para que no se
confunda con una validacion.
"""

import base64
import json
import time

ANCHO = 84


# ------------------------------------------------------------------------------
# Inspeccion del token (solo para mostrar)
# ------------------------------------------------------------------------------
def decode_jwt_payload(token):
    """Devuelve el payload del JWT como diccionario, o None si no aplica.

    No valida la firma: se usa unicamente para que la bitacora pueda mostrar
    a quien pertenece el token y cuanto le queda de vida.
    """
    if not token or not isinstance(token, str) or token.count(".") != 2:
        return None
    segment = token.split(".")[1]
    try:
        raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def mask(token, keep=24):
    """Recorta el token para el log: cabeza...cola (nunca se imprime completo)."""
    if not token:
        return None
    if len(token) <= keep * 2:
        return token
    return "%s...%s" % (token[:keep], token[-keep:])


def _human(seconds):
    if seconds is None:
        return "sin exp"
    minutes, secs = divmod(int(seconds), 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return "%dh %02dm" % (hours, minutes)
    return "%dm %02ds" % (minutes, secs)


def token_headline(token):
    """La cabecera HTTP tal como viaja (con el token recortado)."""
    if not token:
        return "Authorization: (sin token: peticion ANONIMA)"
    return "Authorization: Bearer %s" % mask(token)


def describe_claims(token):
    """Resumen legible de las reclamaciones del JWT (para el encabezado del log)."""
    claims = decode_jwt_payload(token)
    if not claims:
        return None
    remaining = None
    if claims.get("exp"):
        remaining = max(int(claims["exp"] - time.time()), 0)
    return {
        "sub": claims.get("sub"),
        "rol": claims.get("role"),
        "iss": claims.get("iss"),
        "aud": claims.get("aud"),
        "sid": claims.get("sid"),
        "jti": (str(claims.get("jti"))[:8] + "...") if claims.get("jti") else None,
        "restante": remaining,
        "restante_texto": _human(remaining),
    }


# ------------------------------------------------------------------------------
# Formato de la bitacora
# ------------------------------------------------------------------------------
def _line(char="-"):
    return char * ANCHO


def format_summary(entry):
    """Una linea para la bitacora en pantalla (la que ya existia)."""
    token = entry.get("token")
    marca = " [Bearer %s]" % mask(token, 10) if token else " [anonima]"
    aviso = ""
    if entry.get("refreshed"):
        aviso = "  <- tras renovar el token"
    if entry.get("retry"):
        aviso += "  (reintento)"
    return "%s %s -> %s en %.0f ms%s%s" % (
        entry.get("method"), entry.get("url"), entry.get("status"),
        entry.get("elapsed_ms") or 0, marca, aviso)


def format_block(entry):
    """Bloque de varias lineas que se imprime en la TERMINAL."""
    lines = [_line("-")]
    lines.append(" [%s] %s %s" % (entry.get("time", "--:--:--"),
                                  entry.get("method"), entry.get("url")))
    if entry.get("note"):
        lines.append("   (%s)" % entry["note"])

    # --- Encabezado del token: lo que pide la actividad ------------------------
    lines.append("   +-- AUTENTICACION " + "-" * (ANCHO - 20))
    lines.append("   | " + token_headline(entry.get("token")))
    claims = describe_claims(entry.get("token"))
    if claims:
        lines.append("   | JWT %s  sub=%s  rol=%s  sid=%s  jti=%s" % (
            claims.get("iss"), claims.get("sub"), claims.get("rol"),
            claims.get("sid"), claims.get("jti")))
        lines.append("   | aud=%s   expira en %s" % (claims.get("aud"),
                                                     claims.get("restante_texto")))
    elif entry.get("token"):
        lines.append("   | (el valor no tiene forma de JWT: token opaco)")
    else:
        lines.append("   | (endpoint publico: no requiere token)")
    if entry.get("refreshed"):
        lines.append("   | ^ se renovo el token con POST /refresh (rotacion)")
    lines.append("   +" + "-" * (ANCHO - 5))

    # --- Resultado -------------------------------------------------------------
    ct = entry.get("content_type") or ""
    lines.append("   <<< HTTP %s en %.0f ms   %s" % (entry.get("status"),
                                                    entry.get("elapsed_ms") or 0, ct))
    lines.append(_line("-"))
    return lines

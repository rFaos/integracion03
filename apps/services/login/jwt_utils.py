"""
==============================================================================
JWT UTILS - Implementacion propia de JSON Web Tokens (RFC 7519) con HS256
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236

POR QUE SE IMPLEMENTA A MANO
----------------------------
El microservicio ya venia firmando sus CAPTCHA con HMAC-SHA256 (`hmac` +
`hashlib`) y guardando tokens con SHA-256. El JWT que exige el nuevo
requerimiento usa exactamente las mismas primitivas, asi que se implementa con
la biblioteca estandar: no se agrega una dependencia nueva y queda a la vista
el formato real del token (header.payload.signature), que es justo lo que se
quiere demostrar.

CONTRATO DEL TOKEN (lo unico que comparten los dos microservicios)
------------------------------------------------------------------
  header  = {"alg": "HS256", "typ": "JWT"}
  payload = { iss, aud, sub, sid, jti, email, role, typ, iat, nbf, exp }
  firma   = HMAC-SHA256(base64url(header) + "." + base64url(payload), secreto)

El servicio de libros NO importa este archivo: implementa su propio verificador
a partir del mismo contrato. Lo compartido es el estandar, no el codigo.

REGLAS DE SEGURIDAD QUE SE APLICAN AQUI
---------------------------------------
  1. El algoritmo NO se toma del token: se fija en el servidor (`algorithms`).
     Asi se bloquea el ataque clasico `alg: none` y la confusion de algoritmos
     (pedir HS256 cuando el servidor espera RS256, o firmar con la clave publica).
  2. La firma se compara en tiempo constante (`hmac.compare_digest`).
  3. Se validan `exp`, `nbf`, `iat`, `iss`, `aud` y la presencia de `sub`.
  4. Cualquier fallo se traduce a `JWTError` con codigo y mensaje en espanol,
     de modo que el endpoint solo tenga que decidir el codigo HTTP.
==============================================================================
"""

import base64
import hashlib
import hmac
import json
import time

# Algoritmo por omision. El enunciado pide HMAC-SHA256 (simetrico).
DEFAULT_ALGORITHM = "HS256"


class JWTError(Exception):
    """Token invalido. `code` viaja en la respuesta, `status` define el HTTP."""

    def __init__(self, code, message, status=401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ------------------------------------------------------------------------------
# Codificacion base64url sin relleno (como exige el RFC 7515 para los segmentos)
# ------------------------------------------------------------------------------
def b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(segment):
    # El relleno "=" se quita al firmar, hay que reponerlo para decodificar.
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (ValueError, TypeError):
        raise JWTError("MALFORMED_TOKEN", "El token no tiene una codificacion base64url valida.")


def _json_segment(raw):
    """Decodifica un segmento JSON; falla con un mensaje claro si no lo es."""
    try:
        value = json.loads(b64url_decode(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise JWTError("MALFORMED_TOKEN", "El token no contiene JSON valido.")
    if not isinstance(value, dict):
        raise JWTError("MALFORMED_TOKEN", "El token no contiene un objeto JSON.")
    return value


def looks_like_jwt(token):
    """True si el valor tiene la forma de un JWT (tres segmentos).

    Solo se exige que el encabezado y el payload existan: la firma puede venir
    vacía (caso del ataque `alg: none`) y es justamente el verificador el que
    debe rechazarla con un motivo explícito, no este heurístico.
    """
    if not token or not isinstance(token, str):
        return False
    parts = token.split(".")
    return len(parts) == 3 and bool(parts[0]) and bool(parts[1])


# ------------------------------------------------------------------------------
# Firma
# ------------------------------------------------------------------------------
def _sign(signing_input, secret, algorithm):
    if algorithm != "HS256":
        raise JWTError("UNSUPPORTED_ALGORITHM", "Algoritmo no soportado: %s." % algorithm, status=500)
    return hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()


def encode_jwt(payload, secret, algorithm=DEFAULT_ALGORITHM, header=None):
    """Construye y firma un JWT compacto (`header.payload.signature`)."""
    if not secret:
        raise JWTError("SERVER_MISCONFIGURED", "El servicio no tiene configurado el secreto JWT.", status=500)

    head = dict(header or {})
    head["alg"] = algorithm
    head["typ"] = "JWT"

    segments = [
        b64url_encode(json.dumps(head, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")),
    ]
    signing_input = ".".join(segments)
    signature = b64url_encode(_sign(signing_input, secret, algorithm))
    return signing_input + "." + signature


# ------------------------------------------------------------------------------
# Verificacion
# ------------------------------------------------------------------------------
def decode_jwt(token, secret, algorithms=(DEFAULT_ALGORITHM,), issuer=None,
               audience=None, leeway=0, verify_exp=True, verify_nbf=True,
               now=None):
    """Verifica firma y reclamaciones. Devuelve el payload (dict) o lanza JWTError.

    Parametros relevantes:
      algorithms  -> lista blanca. Si el token dice otro algoritmo, se rechaza.
      leeway      -> tolerancia en segundos para desajustes de reloj entre hosts.
      verify_exp  -> se desactiva SOLO en /logout, donde interesa revocar una
                     sesion cuyo access token acaba de expirar.
    """
    if not secret:
        raise JWTError("SERVER_MISCONFIGURED", "El servicio no tiene configurado el secreto JWT.", status=500)
    if not token or not isinstance(token, str):
        raise JWTError("MISSING_TOKEN", "No se envio el token.")

    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("MALFORMED_TOKEN", "El token no tiene el formato header.payload.signature.")

    header_segment, payload_segment, signature_segment = parts
    header = _json_segment(header_segment)
    payload = _json_segment(payload_segment)

    # --- 1. Algoritmo: se decide en el servidor, nunca se confia en el token ---
    alg = header.get("alg")
    if not alg:
        raise JWTError("MALFORMED_TOKEN", "El token no declara el algoritmo en su encabezado.")
    if alg.lower() == "none":
        # Ataque clasico: token sin firma. Se rechaza de forma explicita para
        # que quede documentado en la evidencia.
        raise JWTError("ALGORITHM_NONE_REJECTED",
                       "El token declara alg=none (sin firma): se rechaza por politica.")
    if alg not in algorithms:
        raise JWTError("UNSUPPORTED_ALGORITHM",
                       "El algoritmo '%s' del token no esta permitido por el servidor." % alg)

    # --- 2. Firma en tiempo constante -----------------------------------------
    expected = b64url_encode(_sign(header_segment + "." + payload_segment, secret, alg))
    if not hmac.compare_digest(expected, signature_segment):
        raise JWTError("INVALID_SIGNATURE", "La firma del token no es valida.")

    # --- 3. Reclamaciones temporales ------------------------------------------
    current = int(now if now is not None else time.time())

    exp = payload.get("exp")
    if exp is None:
        raise JWTError("MALFORMED_TOKEN", "El token no incluye la reclamacion 'exp'.")
    if verify_exp and current > int(exp) + leeway:
        raise JWTError("TOKEN_EXPIRED", "El token expiro. Solicita uno nuevo con /refresh.")

    if verify_nbf and payload.get("nbf") is not None:
        if current + leeway < int(payload["nbf"]):
            raise JWTError("TOKEN_NOT_YET_VALID", "El token aun no es valido (nbf en el futuro).")

    if payload.get("iat") is not None and current + leeway < int(payload["iat"]):
        raise JWTError("TOKEN_NOT_YET_VALID", "El token fue emitido en el futuro (iat inconsistente).")

    # --- 4. Emisor y audiencia ------------------------------------------------
    if issuer is not None and payload.get("iss") != issuer:
        raise JWTError("INVALID_ISSUER",
                       "El token no fue emitido por este servicio (iss inesperado).")
    if audience is not None:
        aud = payload.get("aud")
        aud_values = aud if isinstance(aud, list) else [aud]
        if audience not in aud_values:
            raise JWTError("INVALID_AUDIENCE", "El token no esta dirigido a esta API (aud inesperado).")

    # --- 5. Sujeto ------------------------------------------------------------
    if not payload.get("sub"):
        raise JWTError("MALFORMED_TOKEN", "El token no identifica al sujeto ('sub').")

    return payload


# ------------------------------------------------------------------------------
# Resumen del token para logs y evidencia (sin filtrar la firma completa)
# ------------------------------------------------------------------------------
def describe_token(token, keep=18):
    """Recorta el token para mostrarlo en una bitacora: cabeza...cola.

    En la evidencia del flujo se necesita VER el token, pero en un log de
    produccion no conviene volcarlo completo: esta funcion sirve para ambos.
    """
    if not token:
        return "(sin token)"
    if len(token) <= keep * 2:
        return token
    return "%s...%s" % (token[:keep], token[-keep:])

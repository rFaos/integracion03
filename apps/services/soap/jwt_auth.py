"""
==============================================================================
JWT AUTH - Verificador SIN ESTADO para el microservicio de libros
==============================================================================
PROYECTO: INTEGRACION03 - Microservicios de la libreria en linea
AUTOR: Fabian Azaed Orta Singlaterry (Matricula: 613504)
UNIVERSIDAD DE MONTERREY (UDEM) - SC-2236

POR QUE ESTE ARCHIVO ES UNA COPIA DELIBERADA (Y NO UNA LIBRERIA COMPARTIDA)
---------------------------------------------------------------------------
El servicio de libros NO importa el codigo del servicio de login. Lo unico que
comparte con el es el CONTRATO del token, que no es inventado: es el RFC 7519.
Asi, el dia que el equipo de autenticacion cambie de implementacion (por
ejemplo a RS256 con clave publica), este servicio solo necesita cambiar la
verificacion, no acoplarse a su repositorio.

Por eso aqui solo existe lo que un verificador necesita: nada de emitir tokens.
El secreto (JWT_SECRET) es lo unico realmente compartido, y viaja por variable
de entorno, nunca en el codigo.

Este es el punto central del requerimiento: **la escritura se autoriza sin
consultar la base de datos de sesiones**. El servicio de libros no sabe si el
usuario tiene una sesion abierta; sabe que el token esta firmado por quien
debe, que no ha expirado y que va dirigido a esta API.

LIMITACION ACEPTADA (y por que es aceptable)
--------------------------------------------
Al no compartir estado, este servicio no puede enterarse de un /logout
inmediato. La ventana de desfase es como maximo la vida del access token
(JWT_ACCESS_MINUTES = 15 min). Es el precio conocido de la arquitectura sin
estado y se compensa con vidas cortas + refresh token rotativo. El servicio de
login, que SI tiene la sesion en la base, revoca de inmediato.
==============================================================================
"""

import base64
import hashlib
import hmac
import json
import time

DEFAULT_ALGORITHM = "HS256"


class JWTError(Exception):
    """Token invalido. `code` viaja en la respuesta, `status` define el HTTP."""

    def __init__(self, code, message, status=401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(segment):
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (ValueError, TypeError):
        raise JWTError("MALFORMED_TOKEN", "El token no tiene una codificacion base64url valida.")


def _json_segment(raw):
    try:
        value = json.loads(b64url_decode(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise JWTError("MALFORMED_TOKEN", "El token no contiene JSON valido.")
    if not isinstance(value, dict):
        raise JWTError("MALFORMED_TOKEN", "El token no contiene un objeto JSON.")
    return value


def looks_like_jwt(token):
    """True si el valor tiene la forma de un JWT (encabezado y payload presentes)."""
    if not token or not isinstance(token, str):
        return False
    parts = token.split(".")
    return len(parts) == 3 and bool(parts[0]) and bool(parts[1])


def decode_jwt(token, secret, algorithms=(DEFAULT_ALGORITHM,), issuer=None,
               audience=None, leeway=0, verify_exp=True, now=None):
    """Verifica firma y reclamaciones. Devuelve el payload o lanza JWTError."""
    if not secret:
        raise JWTError("SERVER_MISCONFIGURED",
                       "El servicio de libros no tiene configurado JWT_SECRET.", status=500)
    if not token or not isinstance(token, str):
        raise JWTError("TOKEN_REQUIRED", "No se envio el token de acceso.")

    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("MALFORMED_TOKEN", "El token no tiene el formato header.payload.signature.")

    header_segment, payload_segment, signature_segment = parts
    header = _json_segment(header_segment)
    payload = _json_segment(payload_segment)

    # 1. El algoritmo se decide AQUI, nunca se obedece al token.
    alg = header.get("alg")
    if not alg:
        raise JWTError("MALFORMED_TOKEN", "El token no declara el algoritmo en su encabezado.")
    if alg.lower() == "none":
        raise JWTError("ALGORITHM_NONE_REJECTED",
                       "El token declara alg=none (sin firma): se rechaza por politica.")
    if alg not in algorithms:
        raise JWTError("UNSUPPORTED_ALGORITHM",
                       "El algoritmo '%s' del token no esta permitido por el servidor." % alg)

    # 2. Firma en tiempo constante.
    expected = b64url_encode(hmac.new(secret.encode("utf-8"),
                                     (header_segment + "." + payload_segment).encode("ascii"),
                                     hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature_segment):
        raise JWTError("INVALID_SIGNATURE", "La firma del token no es valida.")

    # 3. Reclamaciones temporales.
    current = int(now if now is not None else time.time())
    exp = payload.get("exp")
    if exp is None:
        raise JWTError("MALFORMED_TOKEN", "El token no incluye la reclamacion 'exp'.")
    if verify_exp and current > int(exp) + leeway:
        raise JWTError("TOKEN_EXPIRED",
                       "El access token expiro. Renueva con POST /refresh del servicio de login.")
    if payload.get("nbf") is not None and current + leeway < int(payload["nbf"]):
        raise JWTError("TOKEN_NOT_YET_VALID", "El token aun no es valido (nbf en el futuro).")
    if payload.get("iat") is not None and current + leeway < int(payload["iat"]):
        raise JWTError("TOKEN_NOT_YET_VALID", "El token fue emitido en el futuro (iat inconsistente).")

    # 4. Emisor y audiencia: evita aceptar tokens de otra aplicacion que
    #    casualmente comparta el secreto.
    if issuer is not None and payload.get("iss") != issuer:
        raise JWTError("INVALID_ISSUER", "El token no fue emitido por el servicio de login esperado.")
    if audience is not None:
        aud = payload.get("aud")
        aud_values = aud if isinstance(aud, list) else [aud]
        if audience not in aud_values:
            raise JWTError("INVALID_AUDIENCE", "El token no esta dirigido a esta API (aud inesperado).")

    # 5. Sujeto.
    if not payload.get("sub"):
        raise JWTError("MALFORMED_TOKEN", "El token no identifica al sujeto ('sub').")

    return payload


def describe_token(token, keep=18):
    """Recorta el token para mostrarlo en una bitacora: cabeza...cola."""
    if not token:
        return "(sin token)"
    if len(token) <= keep * 2:
        return token
    return "%s...%s" % (token[:keep], token[-keep:])

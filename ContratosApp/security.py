"""Autorizacion temporal y sesiones firmadas para contratos."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid


ACCESS_TTL_SECONDS = 30 * 60
SESSION_COOKIE_NAME = "contrato_session"


def registro_valido(registro_id: str) -> bool:
    try:
        uuid.UUID(registro_id)
    except (AttributeError, ValueError):
        return False
    return True


def firma_acceso(registro_id: str, expiracion: int, secreto: str) -> str:
    contenido = f"{registro_id}:{expiracion}".encode("utf-8")
    return hmac.new(secreto.encode("utf-8"), contenido, hashlib.sha256).hexdigest()


def expiracion_valida(expiracion: str, ahora: int | None = None) -> int | None:
    try:
        valor = int(expiracion)
    except (TypeError, ValueError):
        return None
    momento = int(time.time()) if ahora is None else ahora
    if valor < momento or valor > momento + ACCESS_TTL_SECONDS:
        return None
    return valor


def token_acceso_valido(
    registro_id: str, expiracion: str, token: str, secreto: str, ahora: int | None = None,
) -> bool:
    if not secreto or not registro_valido(registro_id):
        return False
    expiracion_entera = expiracion_valida(expiracion, ahora)
    if expiracion_entera is None:
        return False
    esperado = firma_acceso(registro_id, expiracion_entera, secreto)
    return hmac.compare_digest(esperado, token)


def crear_cookie_sesion(registro_id: str, expiracion: int, secreto: str) -> str:
    carga = {
        "registro": registro_id,
        "exp": expiracion,
        "nonce": secrets.token_urlsafe(16),
    }
    datos = base64.urlsafe_b64encode(json.dumps(carga, separators=(",", ":")).encode()).rstrip(b"=")
    firma = hmac.new(secreto.encode("utf-8"), datos, hashlib.sha256).hexdigest().encode()
    return f"{datos.decode()}.{firma.decode()}"


def registro_desde_cookie(cookie: str | None, secreto: str, ahora: int | None = None) -> str | None:
    if not cookie or not secreto or "." not in cookie:
        return None
    datos_codificados, firma = cookie.rsplit(".", 1)
    try:
        datos = datos_codificados.encode()
        firma_esperada = hmac.new(secreto.encode("utf-8"), datos, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma_esperada, firma):
            return None
        padding = "=" * (-len(datos_codificados) % 4)
        carga = json.loads(base64.urlsafe_b64decode((datos_codificados + padding).encode()))
        registro_id = carga["registro"]
        expiracion = int(carga["exp"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    momento = int(time.time()) if ahora is None else ahora
    if expiracion < momento or not registro_valido(registro_id):
        return None
    return registro_id
"""Utilidades seguras para la integración opcional con ONLYOFFICE Docs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlparse

import httpx


class ErrorOnlyOffice(Exception):
    """Error seguro para mostrar al usuario sin revelar secretos."""


RUTA_API_JS = "/web-apps/apps/api/documents/api.js"


def url_api_javascript(document_server_url: str) -> str:
    """Acepta URL base del Document Server o la URL completa de api.js."""
    url = document_server_url.rstrip("/")
    return url if url.endswith(RUTA_API_JS) else url + RUTA_API_JS


def editor_configurado(document_server_url: str, signing_secret: str, app_base_url: str) -> bool:
    return bool(document_server_url and signing_secret and app_base_url)


def _b64(valor: bytes) -> str:
    return base64.urlsafe_b64encode(valor).rstrip(b"=").decode("ascii")


def _unb64(valor: str) -> bytes:
    return base64.urlsafe_b64decode(valor + "=" * (-len(valor) % 4))


def crear_token_url(registro_id: str, secreto: str, *, proposito: str, ttl_segundos: int = 8 * 3600) -> str:
    carga = json.dumps({"r": registro_id, "p": proposito, "exp": int(time.time()) + ttl_segundos}, separators=(",", ":")).encode()
    cuerpo = _b64(carga)
    firma = _b64(hmac.new(secreto.encode(), cuerpo.encode(), hashlib.sha256).digest())
    return f"{cuerpo}.{firma}"


def validar_token_url(token: str, registro_id: str, secreto: str, *, proposito: str) -> bool:
    try:
        cuerpo, firma = token.split(".", 1)
        esperada = _b64(hmac.new(secreto.encode(), cuerpo.encode(), hashlib.sha256).digest())
        carga = json.loads(_unb64(cuerpo))
        return (
            hmac.compare_digest(firma, esperada)
            and carga.get("r") == registro_id
            and carga.get("p") == proposito
            and int(carga.get("exp", 0)) >= int(time.time())
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def clave_documento(registro_id: str, file_id: str, modified_time: str = "") -> str:
    """Clave corta, determinística y versionada para evitar caché de ONLYOFFICE."""
    valor = f"{registro_id}:{file_id}:{modified_time}".encode()
    return "ct-" + hashlib.sha256(valor).hexdigest()[:40]


def crear_jwt(carga: dict, secreto: str) -> str:
    encabezado = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    cuerpo = _b64(json.dumps(carga, separators=(",", ":")).encode())
    firma = _b64(hmac.new(secreto.encode(), f"{encabezado}.{cuerpo}".encode(), hashlib.sha256).digest())
    return f"{encabezado}.{cuerpo}.{firma}"


def jwt_valido(token: str, secreto: str) -> bool:
    try:
        encabezado, cuerpo, firma = token.split(".")
        esperada = _b64(hmac.new(secreto.encode(), f"{encabezado}.{cuerpo}".encode(), hashlib.sha256).digest())
        return hmac.compare_digest(firma, esperada)
    except (ValueError, TypeError):
        return False


def descargar_docx_editado(url: str, document_server_url: str, max_bytes: int) -> bytes:
    """Descarga sólo documentos provenientes del Document Server configurado."""
    origen, destino = urlparse(document_server_url), urlparse(url)
    if destino.scheme not in {"https", "http"} or destino.netloc != origen.netloc:
        raise ErrorOnlyOffice("La URL de guardado de ONLYOFFICE no es válida.")
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as cliente:
            with cliente.stream("GET", url) as respuesta:
                respuesta.raise_for_status()
                partes, tamano = [], 0
                for parte in respuesta.iter_bytes():
                    tamano += len(parte)
                    if tamano > max_bytes:
                        raise ErrorOnlyOffice("El documento editado excede el tamaño permitido.")
                    partes.append(parte)
        contenido = b"".join(partes)
    except ErrorOnlyOffice:
        raise
    except httpx.HTTPError as error:
        raise ErrorOnlyOffice("No se pudo descargar la versión editada del contrato.") from error
    if len(contenido) < 4 or contenido[:2] != b"PK":
        raise ErrorOnlyOffice("ONLYOFFICE no entregó un DOCX válido.")
    return contenido


def convertir_docx_a_pdf(
    url_docx: str, document_server_url: str, clave: str, titulo: str,
    jwt_secret: str = "", max_bytes: int = 20 * 1024 * 1024,
) -> bytes:
    """Convierte el DOCX guardado por ONLYOFFICE a PDF mediante su Conversion API."""
    origen, destino = urlparse(document_server_url), urlparse(url_docx)
    if (
        origen.scheme not in {"https", "http"} or not origen.netloc
        or destino.scheme not in {"https", "http"} or destino.netloc != origen.netloc
    ):
        raise ErrorOnlyOffice("La URL del documento editado no es valida.")

    carga = {
        "async": False,
        "filetype": "docx",
        "key": clave,
        "outputtype": "pdf",
        "title": titulo if titulo.lower().endswith(".docx") else f"{titulo}.docx",
        "url": url_docx,
    }
    if jwt_secret:
        # Con JWT habilitado, ONLYOFFICE exige que el payload vaya firmado.
        carga = {"token": crear_jwt(carga, jwt_secret)}
    try:
        with httpx.Client(timeout=70, follow_redirects=False) as cliente:
            respuesta = cliente.post(
                document_server_url.rstrip("/") + f"/converter?shardkey={clave}",
                json=carga,
                headers={"Accept": "application/json"},
            )
            respuesta.raise_for_status()
            resultado = respuesta.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ErrorOnlyOffice("No se pudo convertir el documento editado a PDF.") from error
    if not isinstance(resultado, dict) or resultado.get("error") or not resultado.get("endConvert"):
        raise ErrorOnlyOffice("ONLYOFFICE no pudo completar la conversion a PDF.")
    url_pdf = resultado.get("fileUrl")
    if not isinstance(url_pdf, str) or not url_pdf:
        raise ErrorOnlyOffice("ONLYOFFICE no entrego el PDF convertido.")

    destino_pdf = urlparse(url_pdf)
    if destino_pdf.scheme not in {"https", "http"} or destino_pdf.netloc != origen.netloc:
        raise ErrorOnlyOffice("La URL del PDF convertido no es valida.")
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as cliente:
            with cliente.stream("GET", url_pdf) as respuesta:
                respuesta.raise_for_status()
                partes, tamano = [], 0
                for parte in respuesta.iter_bytes():
                    tamano += len(parte)
                    if tamano > max_bytes:
                        raise ErrorOnlyOffice("El PDF convertido excede el tamaÃ±o permitido.")
                    partes.append(parte)
        contenido = b"".join(partes)
    except ErrorOnlyOffice:
        raise
    except httpx.HTTPError as error:
        raise ErrorOnlyOffice("No se pudo descargar el PDF convertido.") from error
    if len(contenido) < 5 or not contenido.startswith(b"%PDF"):
        raise ErrorOnlyOffice("ONLYOFFICE no entrego un PDF valido.")
    return contenido

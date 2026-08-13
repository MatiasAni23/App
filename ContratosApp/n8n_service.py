"""Envío explícito del PDF definitivo al webhook de n8n."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import logging
from urllib.parse import urlparse

import requests

from utils import email_valido


LOGGER = logging.getLogger(__name__)
TIMEOUT_SEGUNDOS = 60


class ErrorN8N(Exception):
    """Error seguro para presentar en la interfaz, sin incluir datos del PDF."""


@dataclass(frozen=True)
class ResultadoN8N:
    ok: bool
    mensaje: str
    registro_id: str | None = None
    estado: str | None = None


def validar_pdf(nombre_archivo: str, pdf_bytes: bytes, max_size_bytes: int) -> None:
    """Verifica extensión, contenido mínimo y tamaño antes de enviar."""
    if not nombre_archivo or not nombre_archivo.lower().endswith(".pdf"):
        raise ErrorN8N("El documento debe ser un archivo PDF.")
    if not pdf_bytes:
        raise ErrorN8N("El archivo PDF está vacío.")
    if not pdf_bytes.startswith(b"%PDF"):
        raise ErrorN8N("El archivo seleccionado no parece ser un PDF válido.")
    if len(pdf_bytes) > max_size_bytes:
        limite_mb = max_size_bytes // (1024 * 1024)
        raise ErrorN8N(f"El PDF supera el límite permitido de {limite_mb} MB.")


def enviar_pdf_a_firma(
    webhook_url: str, registro_id: str, nombre: str, email: str,
    nombre_archivo: str, pdf_bytes: bytes, *, webhook_secret: str | None = None,
    max_size_bytes: int,
) -> ResultadoN8N:
    """Publica el payload mínimo acordado a n8n; nunca llama directamente a ZapSign."""
    url_parseada = urlparse(webhook_url)
    if not webhook_url or url_parseada.scheme not in {"http", "https"} or not url_parseada.netloc:
        raise ErrorN8N("No está configurada la URL del webhook de n8n.")
    if not registro_id:
        raise ErrorN8N("No se encontró el identificador del registro para enviar a firma.")
    if not nombre.strip():
        raise ErrorN8N("El nombre del firmante es obligatorio.")
    if not email_valido(email):
        raise ErrorN8N("Ingresa un correo electrónico válido antes de enviar a firma.")
    validar_pdf(nombre_archivo, pdf_bytes, max_size_bytes)

    payload = {
        "registro_id": registro_id,
        "nombre": nombre.strip(),
        "email": email.strip(),
        "nombre_archivo": nombre_archivo,
        "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
    }
    headers = {"Content-Type": "application/json"}
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret
    try:
        respuesta = requests.post(webhook_url, json=payload, headers=headers, timeout=TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
    except requests.Timeout as error:
        LOGGER.warning("Timeout al enviar contrato a n8n")
        raise ErrorN8N("No fue posible enviar el contrato a firma. Puedes volver a intentarlo.") from error
    except requests.RequestException as error:
        LOGGER.warning("Error HTTP/red al enviar contrato a n8n: %s", type(error).__name__)
        raise ErrorN8N("No fue posible enviar el contrato a firma. Puedes volver a intentarlo.") from error
    try:
        cuerpo = respuesta.json()
    except ValueError as error:
        LOGGER.warning("n8n respondió contenido no JSON")
        raise ErrorN8N("No fue posible confirmar el envío a firma. Puedes volver a intentarlo.") from error
    if not isinstance(cuerpo, dict) or cuerpo.get("ok") is not True:
        LOGGER.warning("n8n informó un envío no exitoso")
        raise ErrorN8N("No fue posible enviar el contrato a firma. Puedes volver a intentarlo.")
    return ResultadoN8N(
        ok=True, mensaje=str(cuerpo.get("mensaje", "Contrato enviado correctamente a firma.")),
        registro_id=cuerpo.get("registro_id"), estado=cuerpo.get("estado"),
    )

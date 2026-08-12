"""Integración reutilizable con Google Drive, independiente de Streamlit."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from config import CREDENTIALS_PATH, TOKEN_PATH


LOGGER = logging.getLogger(__name__)
# Se requiere acceso a una carpeta existente que la app no creó; por eso Drive completo.
SCOPES = ["https://www.googleapis.com/auth/drive"]
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_GOOGLE_DOC = "application/vnd.google-apps.document"


class ErrorDrive(Exception):
    """Error técnico de Drive con un mensaje seguro para la interfaz."""


class CredencialesNoEncontradas(ErrorDrive):
    pass


class CarpetaNoEncontrada(ErrorDrive):
    pass


class SinPermisoCarpeta(ErrorDrive):
    pass


class TokenCloudNoConfigurado(ErrorDrive):
    pass


@dataclass(frozen=True)
class ResultadoDrive:
    id: str
    nombre: str
    web_view_link: str
    folder_id: str
    duplicado: bool = False


def obtener_credenciales(
    credentials_path: Path = CREDENTIALS_PATH, token_path: Path = TOKEN_PATH
) -> Credentials:
    """Carga, renueva o solicita OAuth local y guarda el token sin registrarlo."""
    credenciales = _obtener_credenciales_desde_secreto()
    token_desde_secreto = credenciales is not None
    if credenciales is None and token_path.exists():
        try:
            credenciales = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as error:
            LOGGER.warning("No se pudo cargar el token local: %s", type(error).__name__)

    if credenciales and credenciales.valid:
        return credenciales
    if credenciales and credenciales.expired and credenciales.refresh_token:
        try:
            credenciales.refresh(Request())
        except Exception as error:
            LOGGER.warning("No se pudo renovar el token: %s", type(error).__name__)
            credenciales = None

    if credenciales and credenciales.valid:
        if not token_desde_secreto:
            token_path.write_text(credenciales.to_json(), encoding="utf-8")
        return credenciales
    if os.getenv("GOOGLE_OAUTH_CLIENT_CONFIG"):
        raise TokenCloudNoConfigurado(
            "Falta configurar GOOGLE_OAUTH_TOKEN en los Secrets de Streamlit Cloud."
        )
    if not credentials_path.exists():
        raise CredencialesNoEncontradas("No se encontró credentials.json.")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        credenciales = flow.run_local_server(port=0)
        token_path.write_text(credenciales.to_json(), encoding="utf-8")
        return credenciales
    except Exception as error:
        LOGGER.exception("No fue posible completar OAuth: %s", type(error).__name__)
        raise ErrorDrive("No fue posible iniciar sesión en Google.") from error


def _obtener_credenciales_desde_secreto() -> Credentials | None:
    """Lee el token OAuth de Secrets sin depender de Streamlit."""
    token_json = os.getenv("GOOGLE_OAUTH_TOKEN")
    if not token_json:
        return None
    try:
        return Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except (ValueError, json.JSONDecodeError) as error:
        LOGGER.warning("El token OAuth configurado como secreto no es válido: %s", type(error).__name__)
        raise TokenCloudNoConfigurado("El secreto GOOGLE_OAUTH_TOKEN no tiene un formato válido.") from error


def crear_servicio_drive(credenciales: Credentials | None = None):
    """Crea un cliente de Google Drive autenticado."""
    try:
        return build("drive", "v3", credentials=credenciales or obtener_credenciales())
    except ErrorDrive:
        raise
    except Exception as error:
        LOGGER.exception("No fue posible crear el servicio Drive: %s", type(error).__name__)
        raise ErrorDrive("No fue posible conectar con Google Drive.") from error


def verificar_carpeta(servicio, folder_id: str) -> dict:
    """Comprueba que la carpeta exista y permita crear documentos."""
    if not folder_id:
        raise CarpetaNoEncontrada("Debes configurar DRIVE_REVIEW_FOLDER_ID.")
    try:
        carpeta = servicio.files().get(
            fileId=folder_id,
            fields="id,name,mimeType,capabilities",
            supportsAllDrives=True,
        ).execute()
    except HttpError as error:
        LOGGER.warning("No se pudo consultar la carpeta Drive: estado=%s", error.resp.status)
        if error.resp.status == 404:
            raise CarpetaNoEncontrada("No se encontró la carpeta configurada de Google Drive.") from error
        if error.resp.status in (401, 403):
            raise SinPermisoCarpeta("No tienes acceso a la carpeta configurada de Google Drive.") from error
        raise ErrorDrive("No fue posible validar la carpeta de Google Drive.") from error
    if carpeta.get("mimeType") != "application/vnd.google-apps.folder":
        raise CarpetaNoEncontrada("El ID configurado no corresponde a una carpeta de Google Drive.")
    if not carpeta.get("capabilities", {}).get("canAddChildren", False):
        raise SinPermisoCarpeta("No tienes permisos para crear archivos en la carpeta configurada de Google Drive.")
    return carpeta


def obtener_url_documento(documento: dict) -> str:
    """Devuelve el enlace editable, usando una URL segura de respaldo."""
    return documento.get("webViewLink") or f"https://docs.google.com/document/d/{documento['id']}/edit"


def buscar_documento_duplicado(servicio, folder_id: str, nombre: str) -> dict | None:
    """Busca un Google Docs con el mismo nombre dentro de la carpeta destino."""
    nombre_escapado = nombre.replace("'", "\\'")
    consulta = (
        f"'{folder_id}' in parents and name = '{nombre_escapado}' "
        f"and mimeType = '{MIME_GOOGLE_DOC}' and trashed = false"
    )
    respuesta = servicio.files().list(
        q=consulta, spaces="drive", fields="files(id,name,mimeType,webViewLink,parents)",
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    archivos = respuesta.get("files", [])
    return archivos[0] if archivos else None


def subir_docx_como_google_docs(
    servicio, contenido_docx: bytes, nombre_archivo: str, folder_id: str, *, permitir_duplicado: bool = False
) -> ResultadoDrive:
    """Importa un DOCX en memoria como Google Docs editable, sin archivos temporales."""
    verificar_carpeta(servicio, folder_id)
    nombre = nombre_archivo.removesuffix(".docx")
    duplicado = buscar_documento_duplicado(servicio, folder_id, nombre)
    if duplicado and not permitir_duplicado:
        return ResultadoDrive(
            id=duplicado["id"], nombre=duplicado["name"], web_view_link=obtener_url_documento(duplicado),
            folder_id=folder_id, duplicado=True,
        )
    try:
        metadata = {"name": nombre, "mimeType": MIME_GOOGLE_DOC, "parents": [folder_id]}
        media = MediaIoBaseUpload(BytesIO(contenido_docx), mimetype=MIME_DOCX, resumable=False)
        creado = servicio.files().create(
            body=metadata, media_body=media, fields="id,name,mimeType,webViewLink,parents",
            supportsAllDrives=True,
        ).execute()
        LOGGER.info("Documento creado en Drive: id=%s nombre=%s", creado["id"], creado["name"])
        return ResultadoDrive(
            id=creado["id"], nombre=creado["name"], web_view_link=obtener_url_documento(creado),
            folder_id=folder_id,
        )
    except HttpError as error:
        LOGGER.warning("Falló la subida a Drive: estado=%s", error.resp.status)
        if error.resp.status in (401, 403):
            raise SinPermisoCarpeta("No tienes permisos para crear archivos en la carpeta configurada de Google Drive.") from error
        raise ErrorDrive("No se pudo guardar el contrato en Google Drive.") from error
    except Exception as error:
        LOGGER.exception("Falló la subida a Drive: %s", type(error).__name__)
        raise ErrorDrive("No se pudo guardar el contrato en Google Drive.") from error

"""Acceso a Contratos_Pendientes en Google Sheets, sin dependencia de Streamlit."""

from __future__ import annotations

import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import SPREADSHEET_ID


LOGGER = logging.getLogger(__name__)
RANGO_CONTRATOS = "Contratos_Pendientes!A:M"
NOMBRES_COLUMNAS = (
    "id", "fecha", "nombres", "apellidos", "dni", "celular", "email",
    "ciudad", "pais", "monto", "banco", "productos", "estado",
)


class ErrorSheets(Exception):
    """Error de Sheets que puede mostrarse sin detalles técnicos."""


class SpreadsheetNoConfigurado(ErrorSheets):
    pass


def crear_servicio_sheets(credentials):
    """Crea el cliente de Sheets con las mismas credenciales OAuth de Drive."""
    try:
        return build("sheets", "v4", credentials=credentials)
    except Exception as error:
        LOGGER.exception("No fue posible crear servicio Sheets: %s", type(error).__name__)
        raise ErrorSheets("No fue posible conectar con Google Sheets.") from error


def _validar_spreadsheet_id(spreadsheet_id: str) -> None:
    if not spreadsheet_id:
        raise SpreadsheetNoConfigurado("Debes configurar SPREADSHEET_ID para cargar registros desde Google Sheets.")


def _normalizar_fila(fila: list[str]) -> dict[str, str]:
    valores = list(fila[:len(NOMBRES_COLUMNAS)]) + [""] * max(0, len(NOMBRES_COLUMNAS) - len(fila))
    return dict(zip(NOMBRES_COLUMNAS, valores, strict=True))


def _leer_filas(servicio, spreadsheet_id: str) -> list[list[str]]:
    _validar_spreadsheet_id(spreadsheet_id)
    try:
        respuesta = servicio.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=RANGO_CONTRATOS,
        ).execute()
        return respuesta.get("values", [])
    except HttpError as error:
        LOGGER.warning("Error consultando Sheets: estado=%s", error.resp.status)
        if error.resp.status in (401, 403):
            raise ErrorSheets("No tienes permisos para leer Google Sheets o la API no está habilitada.") from error
        if error.resp.status == 404:
            raise ErrorSheets("No se encontró el spreadsheet o la hoja Contratos_Pendientes.") from error
        raise ErrorSheets("No fue posible consultar Google Sheets.") from error
    except Exception as error:
        LOGGER.exception("Error consultando Sheets: %s", type(error).__name__)
        raise ErrorSheets("No fue posible consultar Google Sheets.") from error


def obtener_contrato_pendiente(servicio, registro_id: str, spreadsheet_id: str = SPREADSHEET_ID) -> dict[str, str] | None:
    """Busca exactamente el UUID en columna A y tolera celdas vacías."""
    for fila in _leer_filas(servicio, spreadsheet_id):
        registro = _normalizar_fila(fila)
        if registro["id"] == registro_id:
            return registro
    return None


def actualizar_estado_contrato(
    servicio, registro_id: str, nuevo_estado: str, spreadsheet_id: str = SPREADSHEET_ID,
) -> bool:
    """Actualiza sólo la columna M de la fila correspondiente al UUID."""
    filas = _leer_filas(servicio, spreadsheet_id)
    for indice, fila in enumerate(filas, start=1):
        if fila and fila[0] == registro_id:
            try:
                servicio.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id, range=f"Contratos_Pendientes!M{indice}",
                    valueInputOption="RAW", body={"values": [[nuevo_estado]]},
                ).execute()
                return True
            except HttpError as error:
                LOGGER.warning("Error actualizando estado en Sheets: estado=%s", error.resp.status)
                raise ErrorSheets("No fue posible actualizar el estado en Google Sheets.") from error
    return False

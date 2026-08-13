"""Configuración centralizada de la aplicación."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# Carpeta usada por el notebook original. No es una credencial OAuth.
DRIVE_REVIEW_FOLDER_ID = os.getenv("DRIVE_REVIEW_FOLDER_ID", "1L3igm-hM-AEN7Hnmf4EJo9IdQ4RSVbvq")
# ID del libro que contiene la pestaña Contratos_Pendientes. Configúralo como
# variable de entorno/Secret en Cloud o directamente aquí para uso local.
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID","1banOMM_N4QD6y0eR_xahpLA7hYZKSfnjPbGDixC3iTo",)
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"


#ID CARPETA REAL: 1GLxHxL7XV5JpwPTiCguyFalac3CAQnug

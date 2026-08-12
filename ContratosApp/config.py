"""Configuración centralizada de la aplicación."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# Carpeta usada por el notebook original. No es una credencial OAuth.
DRIVE_REVIEW_FOLDER_ID = "1L3igm-hM-AEN7Hnmf4EJo9IdQ4RSVbvq"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"


#ID CARPETA REAL: 1GLxHxL7XV5JpwPTiCguyFalac3CAQnug
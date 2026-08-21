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
# Configurar en .env/local o en Streamlit Cloud Secrets; nunca hardcodear URLs
# de producción ni secretos en el repositorio.
N8N_ZAPSIGN_WEBHOOK_URL = os.getenv("N8N_ZAPSIGN_WEBHOOK_URL", "https://movizzon.app.n8n.cloud/webhook/enviar-contrato-zapsign")
N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "")
MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB, límite razonable para webhook.

ONLYOFFICE_DOCUMENT_SERVER_URL = os.getenv("ONLYOFFICE_DOCUMENT_SERVER_URL", "").rstrip("/")
ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET", "")
ONLYOFFICE_JWT_HEADER = os.getenv("ONLYOFFICE_JWT_HEADER", "Authorization")
ONLYOFFICE_URL_SIGNING_SECRET = os.getenv("ONLYOFFICE_URL_SIGNING_SECRET", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")
APP_ACCESS_SECRET = os.getenv("APP_ACCESS_SECRET", "")
# Solo para la vista previa local por HTTP. En producción debe permanecer vacío.
LOCAL_DEV_INSECURE_COOKIES = os.getenv("LOCAL_DEV_INSECURE_COOKIES", "").strip().lower() in {"1", "true", "yes"}
# Omite la sesión firmada únicamente para una vista previa ligada a localhost.
LOCAL_DEV_BYPASS_AUTH = os.getenv("LOCAL_DEV_BYPASS_AUTH", "").strip().lower() in {"1", "true", "yes"}
MAX_DOCX_SIZE_BYTES = 5 * 1024 * 1024

#ID CARPETA REAL: 1GLxHxL7XV5JpwPTiCguyFalac3CAQnug
#

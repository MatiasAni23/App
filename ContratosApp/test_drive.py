"""Diagnóstico manual de Google Drive; no sube ningún documento."""

import logging

from config import DRIVE_REVIEW_FOLDER_ID
from drive_service import ErrorDrive, crear_servicio_drive, verificar_carpeta


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        servicio = crear_servicio_drive()
        carpeta = verificar_carpeta(servicio, DRIVE_REVIEW_FOLDER_ID)
    except ErrorDrive as error:
        print(f"Google Drive API: ERROR\nMotivo: {error}")
        return
    print("Google Drive API: OK")
    print("OAuth: OK")
    print(f"Carpeta encontrada: {carpeta['name']}")
    print("Permiso de creación: OK")


if __name__ == "__main__":
    main()

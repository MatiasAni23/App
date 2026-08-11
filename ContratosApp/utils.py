"""Utilidades compartidas que no dependen de Streamlit ni de Word."""

import re
from datetime import date


CARACTERES_INVALIDOS_WINDOWS = r'[<>:"/\\|?*]'


def sanitizar_nombre_archivo(nombre: str) -> str:
    """Quita caracteres no permitidos por Windows sin perder legibilidad."""
    nombre = re.sub(CARACTERES_INVALIDOS_WINDOWS, "", nombre)
    return re.sub(r"\s+", " ", nombre).strip().rstrip(".")


def email_valido(email: str) -> bool:
    """Validación básica y deliberadamente simple para el formulario."""
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()))


def fecha_hoy() -> date:
    """Punto único de acceso a la fecha actual, útil para UI y pruebas."""
    return date.today()

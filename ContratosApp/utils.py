"""Utilidades compartidas que no dependen de Streamlit ni de Word."""

import re
import unicodedata
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


ETIQUETAS_EXCEL = {
    "nombres": "nombres", "apellidos": "apellidos", "dni": "dni",
    "dni documento": "dni", "documento": "dni", "celular": "celular",
    "celular de contacto": "celular", "email": "email", "email personal": "email",
    "correo": "email", "correo electronico": "email", "ciudad": "ciudad",
    "pais": "pais", "monto": "monto", "banco": "banco", "productos": "productos",
}


def _normalizar_etiqueta(etiqueta: str) -> str:
    texto = unicodedata.normalize("NFD", etiqueta.strip().lower())
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    return re.sub(r"\s+", " ", texto)


def parsear_datos_pegados(texto: str) -> tuple[dict[str, str], list[str]]:
    """Clasifica datos pegados desde Excel como ``Campo: valor`` o dos columnas."""
    campos: dict[str, str] = {}
    no_reconocidas: list[str] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if ":" in linea:
            etiqueta, valor = linea.split(":", 1)
        elif "\t" in linea:
            etiqueta, valor = linea.split("\t", 1)
        else:
            no_reconocidas.append(linea)
            continue
        campo = ETIQUETAS_EXCEL.get(_normalizar_etiqueta(etiqueta))
        if campo and valor.strip():
            campos[campo] = valor.strip()
        elif not campo:
            no_reconocidas.append(linea)
    return campos, no_reconocidas

"""Modelos de dominio para la generación de contratos."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DatosContrato:
    """Datos que utiliza actualmente la plantilla de contratos."""

    nombres: str
    apellidos: str
    dni: str
    celular_contacto: str
    email_personal: str
    ciudad: str
    pais: str
    monto: str
    banco: str
    productos: str
    fecha: date

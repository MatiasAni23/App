"""Utilidades compartidas que no dependen de Streamlit ni de Word."""

import json
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
    return re.sub(r"[\s_-]+", " ", texto).strip(" :")


def _parsear_datos_etiquetados(texto: str) -> tuple[dict[str, str], list[str]]:
    """Clasifica pares verticales o una tabla copiada desde Excel."""
    campos: dict[str, str] = {}
    no_reconocidas: list[str] = []
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]

    # Excel suele pegar una fila de encabezados seguida por una fila de valores.
    # Solo la tratamos como tabla si hay al menos dos encabezados reconocidos; así
    # no confundimos el formato vertical ``Nombres<TAB>María``.
    if len(lineas) >= 2 and "\t" in lineas[0] and "\t" in lineas[1]:
        encabezados = lineas[0].split("\t")
        valores = lineas[1].split("\t")
        reconocidos = [ETIQUETAS_EXCEL.get(_normalizar_etiqueta(etiqueta)) for etiqueta in encabezados]
        if sum(campo is not None for campo in reconocidos) >= 2:
            for campo, valor in zip(reconocidos, valores):
                if campo and valor.strip():
                    campos[campo] = valor.strip()
            return campos, no_reconocidas

    for linea in lineas:
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


_ALIAS = {
    "nombre": "nombres", "nombres": "nombres", "apellido": "apellidos", "apellidos": "apellidos",
    "rut": "dni", "run": "dni", "documento identidad": "dni", "documento de identidad": "dni",
    "cc": "dni", "cedula": "dni", "telefono": "celular", "fono": "celular", "movil": "celular",
    "whatsapp": "celular", "correo electronico": "email", "mail": "email", "localidad": "ciudad",
    "country": "pais", "importe": "monto", "valor": "monto", "entidad bancaria": "banco",
    "producto": "productos", "tipo de cuenta": "productos",
}
ETIQUETAS_COMPLETAS = {**ETIQUETAS_EXCEL, **_ALIAS}
NOMBRE_COMPLETO = {"nombre completo", "nombre colaborador", "colaborador"}


def _limpiar_texto(valor: str) -> str:
    texto = re.sub(r"\s+", " ", str(valor or "")).strip()
    return texto.lower().title() if texto and (texto.isupper() or texto.islower()) else texto


def _limpiar_telefono(valor: str) -> str:
    texto = str(valor or "").strip()
    digitos = re.sub(r"\D", "", texto)
    if len(digitos) < 8:
        return re.sub(r"\s+", " ", texto)
    return ("+" if texto.startswith("+") and digitos else "") + digitos


def _limpiar_campos(campos: dict[str, str]) -> dict[str, str]:
    resultado: dict[str, str] = {}
    for campo, valor in campos.items():
        valor = str(valor or "").strip()
        if not valor:
            continue
        if campo == "email":
            coincidencia = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", valor, re.I)
            resultado[campo] = coincidencia.group(0).lower() if coincidencia else valor
        elif campo == "celular":
            resultado[campo] = _limpiar_telefono(valor)
        elif campo == "dni":
            resultado[campo] = re.sub(r"\s+", " ", valor).upper()
        elif campo in {"nombres", "apellidos", "ciudad", "pais"}:
            resultado[campo] = _limpiar_texto(valor)
        else:
            resultado[campo] = valor
    return resultado


def _separar_nombre_completo(valor: str) -> tuple[str, str]:
    partes = _limpiar_texto(valor).split()
    if len(partes) < 2:
        return " ".join(partes), ""
    inicio = len(partes) - 2 if len(partes) >= 3 else 1
    particulas = {"de", "del", "la", "las", "los", "da", "das", "do", "dos", "van", "von"}
    while inicio > 1 and partes[inicio - 1].lower() in particulas:
        inicio -= 1
    return " ".join(partes[:inicio]), " ".join(partes[inicio:])


def _parece_email(valor: str) -> bool:
    return bool(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", valor, re.I))


def _parece_documento(valor: str) -> bool:
    texto = re.sub(r"[.\s]", "", valor)
    return bool(re.fullmatch(r"\d{7,9}-[\dKk]", texto) or (re.fullmatch(r"[A-Za-z0-9-]{6,20}", texto) and any(caracter.isdigit() for caracter in texto)))


def _parece_telefono(valor: str) -> bool:
    return not ("-" in valor and _parece_documento(valor)) and 8 <= len(re.sub(r"\D", "", valor)) <= 15


def _agregar(campos: dict[str, str], etiqueta: str, valor: object) -> bool:
    etiqueta = _normalizar_etiqueta(etiqueta)
    valor = str(valor or "").strip()
    if not valor:
        return False
    if etiqueta in NOMBRE_COMPLETO:
        nombres, apellidos = _separar_nombre_completo(valor)
        campos.setdefault("nombres", nombres)
        campos.setdefault("apellidos", apellidos)
        return True
    campo = ETIQUETAS_COMPLETAS.get(etiqueta)
    if not campo:
        return False
    campos[campo] = valor
    return True


def _campos_json(texto: str) -> dict[str, str] | None:
    try:
        objeto = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(objeto, list):
        objeto = next((item for item in objeto if isinstance(item, dict)), None)
    if not isinstance(objeto, dict):
        return {}
    if len(objeto) == 1 and isinstance(next(iter(objeto.values())), dict):
        objeto = next(iter(objeto.values()))
    campos: dict[str, str] = {}
    for etiqueta, valor in objeto.items():
        if not isinstance(valor, (dict, list)):
            _agregar(campos, etiqueta, valor)
    return campos


def _lineas(texto: str) -> list[str]:
    resultado: list[str] = []
    for linea in texto.replace("\r", "").split("\n"):
        for parte in re.split(r"\s*\|\s*", linea):
            parte = re.sub(r"^[\s\-•●▪►]+", "", parte).strip()
            if parte:
                resultado.append(parte)
    return resultado


def _campos_tabla(lineas: list[str]) -> dict[str, str]:
    if len(lineas) < 2 or "\t" not in lineas[0] or "\t" not in lineas[1]:
        return {}
    encabezados, valores = lineas[0].split("\t"), lineas[1].split("\t")
    if sum(_normalizar_etiqueta(etiqueta) in ETIQUETAS_COMPLETAS for etiqueta in encabezados) < 2:
        return {}
    campos: dict[str, str] = {}
    for etiqueta, valor in zip(encabezados, valores):
        _agregar(campos, etiqueta, valor)
    return campos


def _extraer(lineas: list[str]) -> tuple[dict[str, str], list[str]]:
    campos: dict[str, str] = {}
    restantes: list[str] = []
    etiquetas = sorted((*ETIQUETAS_COMPLETAS, *NOMBRE_COMPLETO), key=len, reverse=True)
    for linea in lineas:
        coincidencia = re.match(r"^(.+?)(?:\s*[:=]\s*|\t)(.+)$", linea)
        if coincidencia and _agregar(campos, coincidencia.group(1), coincidencia.group(2)):
            continue
        normalizada = _normalizar_etiqueta(linea)
        etiqueta = next((item for item in etiquetas if normalizada.startswith(item + " ")), None)
        if etiqueta and _agregar(campos, etiqueta, linea[len(etiqueta):].strip(" :-")):
            continue
        restantes.append(linea)
    return campos, restantes


def _inferir(campos: dict[str, str], valores: list[str]) -> None:
    valores = [valor.strip() for valor in valores if valor.strip()]
    if not campos and len(valores) >= 7 and _parece_documento(valores[2]) and _parece_telefono(valores[3]) and _parece_email(valores[4]):
        campos.update(dict(zip(("nombres", "apellidos", "dni", "celular", "email", "ciudad", "pais"), valores[:7])))
        return
    if not campos and len(valores) >= 6 and _parece_documento(valores[1]) and _parece_telefono(valores[2]) and _parece_email(valores[3]):
        nombres, apellidos = _separar_nombre_completo(valores[0])
        campos.update({"nombres": nombres, "apellidos": apellidos, "dni": valores[1], "celular": valores[2], "email": valores[3], "ciudad": valores[4], "pais": valores[5]})
        return
    restantes = list(valores)
    for campo, detector in (("email", _parece_email), ("dni", _parece_documento), ("celular", _parece_telefono)):
        if not campos.get(campo):
            indice = next((indice for indice, valor in enumerate(restantes) if detector(valor)), None)
            if indice is not None:
                campos[campo] = restantes.pop(indice)
    if not campos.get("nombres") and restantes:
        campos["nombres"], campos["apellidos"] = _separar_nombre_completo(restantes.pop(0))
    for campo in ("ciudad", "pais"):
        if not campos.get(campo) and restantes:
            campos[campo] = restantes.pop(0)


def parsear_datos_pegados(texto: str) -> tuple[dict[str, str], list[str]]:
    """Reconoce texto libre, etiquetas, tablas de Excel y objetos JSON."""
    texto = str(texto or "").strip()
    if not texto:
        return {}, []
    campos_json = _campos_json(texto)
    if campos_json is not None:
        return _limpiar_campos(campos_json), []
    lineas = _lineas(texto)
    campos = _campos_tabla(lineas)
    if campos:
        return _limpiar_campos(campos), []
    campos, restantes = _extraer(lineas)
    _inferir(campos, restantes)
    campos = _limpiar_campos(campos)
    return campos, [] if campos else restantes

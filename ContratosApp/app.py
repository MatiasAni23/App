"""Aplicación FastAPI para generación de borradores y envío a firma."""

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import DRIVE_REVIEW_FOLDER_ID, MAX_PDF_SIZE_BYTES, N8N_WEBHOOK_SECRET, N8N_ZAPSIGN_WEBHOOK_URL
from drive_service import ErrorDrive, crear_servicio_drive, obtener_credenciales, subir_docx_como_google_docs
from generador import generar_contrato
from modelos import DatosContrato
from n8n_service import ErrorN8N, enviar_pdf_a_firma
from sheets_service import ErrorSheets, actualizar_estado_contrato, crear_servicio_sheets, obtener_contrato_pendiente
from utils import email_valido, fecha_hoy, parsear_datos_pegados


BASE_DIR = Path(__file__).resolve().parent
DIRECTORIO_PLANTILLAS = BASE_DIR / "plantillas"
app = FastAPI(title="Generación de borradores de contrato")
app.mount("/public", StaticFiles(directory=BASE_DIR / "public"), name="public")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _plantillas_disponibles() -> list[Path]:
    return sorted(DIRECTORIO_PLANTILLAS.glob("*.docx"))


def _fecha(valor: str) -> date:
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor, formato).date()
        except (TypeError, ValueError):
            continue
    return fecha_hoy()


def _datos_vacios() -> dict[str, str]:
    return {campo: "" for campo in ("nombres", "apellidos", "dni", "celular", "email", "ciudad", "pais", "monto", "banco", "productos")}


def _obtener_registro(registro_id: str | None) -> tuple[dict[str, str] | None, str | None]:
    if not registro_id:
        return None, None
    try:
        servicio = crear_servicio_sheets(obtener_credenciales())
        registro = obtener_contrato_pendiente(servicio, registro_id)
    except (ErrorDrive, ErrorSheets) as error:
        return None, str(error)
    if registro is None:
        return None, "No se encontró el registro solicitado en Google Sheets."
    return registro, None


def _render(request: Request, *, registro_id: str | None = None, datos: dict[str, str] | None = None,
            error: str | None = None, mensaje: str | None = None, enviado: bool = False, status_code: int = 200):
    registro, error_registro = _obtener_registro(registro_id) if datos is None else (None, None)
    datos_finales = datos or registro or _datos_vacios()
    return templates.TemplateResponse(request, "index.html", {
        "registro_id": registro_id,
        "datos": datos_finales,
        "fecha": _fecha(datos_finales.get("fecha", "")) if datos_finales else fecha_hoy(),
        "plantillas": [plantilla.name for plantilla in _plantillas_disponibles()],
        "estado_generado": datos_finales.get("estado") == "Generado",
        "error": error or error_registro,
        "mensaje": mensaje,
        "enviado": enviado,
    }, status_code=status_code)


@app.get("/", response_class=HTMLResponse)
async def inicio(request: Request, registro: str | None = None):
    return _render(request, registro_id=registro)


@app.post("/datos/pegar", response_class=HTMLResponse)
async def cargar_datos_pegados(
    request: Request, datos_pegados: str = Form(""), registro_id: str = Form("")
):
    """Clasifica las filas copiadas desde Excel y las deja listas para revisar."""
    campos, no_reconocidas = parsear_datos_pegados(datos_pegados)
    if not campos:
        return _render(
            request, registro_id=registro_id or None,
            error="No se reconocieron datos. Usa líneas como: Nombres: María Ejemplo.",
            status_code=422,
        )
    datos = _datos_vacios()
    if registro_id:
        registro, _ = _obtener_registro(registro_id)
        if registro:
            datos.update(registro)
    datos.update(campos)
    mensaje = "Datos cargados en el formulario. Revísalos antes de generar el borrador."
    if no_reconocidas:
        mensaje += f" Se omitieron {len(no_reconocidas)} línea(s) sin etiqueta reconocida."
    return _render(request, registro_id=registro_id or None, datos=datos, mensaje=mensaje)


@app.post("/contrato/generar")
async def generar_borrador(
    request: Request,
    registro_id: str = Form(""), nombres: str = Form(""), apellidos: str = Form(""),
    dni: str = Form(""), celular: str = Form(""), email: str = Form(""), ciudad: str = Form(""),
    pais: str = Form(""), monto: str = Form(""), banco: str = Form(""), productos: str = Form(""),
    fecha: str = Form(""), plantilla_guardada: str = Form(""), plantilla_personalizada: UploadFile | None = File(None),
):
    datos_formulario = {"nombres": nombres, "apellidos": apellidos, "dni": dni, "celular": celular, "email": email,
                        "ciudad": ciudad, "pais": pais, "monto": monto, "banco": banco, "productos": productos, "fecha": fecha}
    if not all((nombres.strip(), apellidos.strip(), dni.strip(), banco.strip())) or not email_valido(email):
        return _render(request, registro_id=registro_id or None, datos=datos_formulario, error="Completa los campos obligatorios con un correo válido.", status_code=422)
    if plantilla_personalizada and plantilla_personalizada.filename:
        if not plantilla_personalizada.filename.lower().endswith(".docx"):
            return _render(request, registro_id=registro_id or None, datos=datos_formulario, error="La plantilla personalizada debe ser un archivo DOCX.", status_code=422)
        plantilla = await plantilla_personalizada.read()
    elif plantilla_guardada in {archivo.name for archivo in _plantillas_disponibles()}:
        plantilla = DIRECTORIO_PLANTILLAS / plantilla_guardada
    else:
        return _render(request, registro_id=registro_id or None, datos=datos_formulario, error="Selecciona o sube una plantilla DOCX.", status_code=422)
    try:
        resultado = generar_contrato(plantilla, DatosContrato(
            nombres=nombres.strip(), apellidos=apellidos.strip(), dni=dni.strip(), celular_contacto=celular.strip(),
            email_personal=email.strip(), ciudad=ciudad.strip(), pais=pais.strip(), monto=monto.strip(),
            banco=banco.strip(), productos=productos.strip(), fecha=_fecha(fecha),
        ))
    except Exception:
        return _render(request, registro_id=registro_id or None, datos=datos_formulario, error="No fue posible generar el borrador. Verifica la plantilla e inténtalo nuevamente.", status_code=500)
    if registro_id:
        try:
            servicio = crear_servicio_sheets(obtener_credenciales())
            actualizar_estado_contrato(servicio, registro_id, "Generado")
        except (ErrorDrive, ErrorSheets):
            # El DOCX fue creado correctamente y se entrega; el estado podrá revisarse después.
            pass
    # También se conserva una copia editable para revisión en Google Drive.
    # Un fallo de Drive no impide la descarga inmediata del borrador.
    drive_url = ""
    try:
        documento_drive = subir_docx_como_google_docs(
            crear_servicio_drive(), resultado.contenido, resultado.nombre_archivo,
            DRIVE_REVIEW_FOLDER_ID,
        )
        drive_url = documento_drive.web_view_link
    except ErrorDrive:
        pass
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(resultado.nombre_archivo)}"}
    if drive_url:
        headers["X-Google-Drive-Url"] = drive_url
    return StreamingResponse(
        BytesIO(resultado.contenido), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@app.post("/contrato/enviar", response_class=HTMLResponse)
async def enviar_a_firma(request: Request, registro_id: str = Form(""), pdf_final: UploadFile = File(...)):
    registro, error = _obtener_registro(registro_id)
    if error or registro is None:
        return _render(request, registro_id=registro_id or None, error=error or "No se encontró el contrato para enviar.", status_code=404)
    if registro.get("estado") != "Generado":
        return _render(request, registro_id=registro_id, error="El contrato debe estar generado antes de enviarlo a firma.", status_code=409)
    pdf_bytes = await pdf_final.read()
    nombre = f"{registro.get('nombres', '').strip()} {registro.get('apellidos', '').strip()}".strip()
    try:
        resultado = enviar_pdf_a_firma(
            N8N_ZAPSIGN_WEBHOOK_URL, registro_id, nombre, registro.get("email", ""),
            pdf_final.filename or "", pdf_bytes, webhook_secret=N8N_WEBHOOK_SECRET or None,
            max_size_bytes=MAX_PDF_SIZE_BYTES,
        )
    except ErrorN8N as error_n8n:
        return _render(request, registro_id=registro_id, error=str(error_n8n), status_code=422)
    return _render(request, registro_id=registro_id, mensaje=resultado.mensaje, enviado=True)

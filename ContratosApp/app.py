"""Aplicación FastAPI para generación de borradores y envío a firma."""

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import Environment, select_autoescape

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


PAGE_TEMPLATE = Environment(autoescape=select_autoescape(default=True)).from_string("""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Generación de borradores de contrato</title><style>
:root{font-family:Inter,system-ui,sans-serif;color:#18212f;background:#f7f9fc}.container{max-width:900px;margin:0 auto;padding:48px 20px}h1{font-size:2.2rem;margin:0 0 28px}h2{font-size:1.1rem;margin-top:0}.card,details{background:#fff;border:1px solid #dce3ed;border-radius:12px;padding:22px;margin:20px 0}summary{font-weight:700;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}label{display:grid;gap:7px;font-weight:600;margin:14px 0}input,select,textarea{border:1px solid #cbd5e1;border-radius:8px;padding:10px;font:inherit;background:#fff}textarea{resize:vertical;min-height:160px}button{width:100%;border:0;border-radius:8px;background:#2563eb;color:#fff;font-weight:700;padding:13px;cursor:pointer;margin-top:10px}.secondary{background:#fff;color:#1d4ed8;border:1px solid #bfdbfe}.hint{color:#64748b;font-size:.9rem}.notice{padding:12px 14px;border-radius:8px;margin:14px 0}.success{background:#dcfce7;color:#166534}.error{background:#fee2e2;color:#991b1b}.info{background:#dbeafe;color:#1e40af}@media(max-width:640px){.grid{grid-template-columns:1fr}.container{padding:28px 14px}}
</style></head><body><main class="container"><h1>Generación de borradores de contrato</h1>
{% if mensaje %}<div class="notice success">✓ {{ mensaje }}</div>{% endif %}{% if error %}<div class="notice error">{{ error }}</div>{% endif %}{% if registro_id %}<div class="notice info">Datos cargados desde Google Sheets.</div>{% endif %}
<details class="paste-data"><summary>Pegar datos desde Excel (opcional)</summary><form action="/datos/pegar" method="post"><input type="hidden" name="registro_id" value="{{ registro_id or '' }}"><p class="hint">Pega las filas copiadas desde Excel. Identificamos automáticamente cada campo.</p><label>Datos copiados<textarea name="datos_pegados" rows="9" placeholder="Nombres: María Ejemplo&#10;Apellidos: Pérez Soto&#10;DNI: DOC-12345678&#10;Celular: +56 9 1111 2222&#10;Email personal: maria.ejemplo@correo.test&#10;Ciudad: Santiago&#10;País: Chile&#10;Monto: 350&#10;Banco: Banco Demo&#10;Productos: Cuenta corriente"></textarea></label><button type="submit" class="secondary">CARGAR DATOS EN EL FORMULARIO</button></form></details>
<form action="/contrato/generar" method="post" enctype="multipart/form-data"><input type="hidden" name="registro_id" value="{{ registro_id or '' }}"><details {% if not registro_id %}open{% endif %}><summary>¿Quieres verificar los datos?</summary><p class="hint">Puedes revisar o corregir la información antes de crear el borrador.</p><div class="grid"><label>Nombres *<input name="nombres" required value="{{ datos.nombres }}"></label><label>Apellidos *<input name="apellidos" required value="{{ datos.apellidos }}"></label><label>DNI / Documento *<input name="dni" required value="{{ datos.dni }}"></label><label>Celular<input name="celular" value="{{ datos.celular }}"></label><label>Email *<input name="email" type="email" required value="{{ datos.email }}"></label><label>Ciudad<input name="ciudad" value="{{ datos.ciudad }}"></label><label>País<input name="pais" value="{{ datos.pais }}"></label><label>Monto<input name="monto" value="{{ datos.monto }}"></label><label>Banco *<input name="banco" required value="{{ datos.banco }}"></label><label>Productos<input name="productos" value="{{ datos.productos }}"></label></div><label>Fecha *<input name="fecha" type="date" required value="{{ fecha.isoformat() }}"></label></details><section class="card"><h2>Plantilla del contrato</h2><label>Plantilla guardada<select name="plantilla_guardada"><option value="">Seleccione una plantilla</option>{% for plantilla in plantillas %}<option value="{{ plantilla }}">{{ plantilla }}</option>{% endfor %}</select></label><label>Subir plantilla personalizada<input name="plantilla_personalizada" type="file" accept=".docx"></label><p class="hint">La plantilla subida tiene prioridad sobre la plantilla guardada.</p><button type="submit">GENERAR BORRADOR DE CONTRATO</button></section></form>
{% if estado_generado or enviado %}<section class="card"><h2>Documento final para firma</h2>{% if enviado %}<div class="notice success">✓ Enviado a firma</div>{% else %}<form action="/contrato/enviar" method="post" enctype="multipart/form-data"><input type="hidden" name="registro_id" value="{{ registro_id }}"><p><strong>Firmante:</strong> {{ datos.nombres }} {{ datos.apellidos }}</p><p><strong>Correo:</strong> {{ datos.email }}</p><label>Subir documento PDF final<input name="pdf_final" type="file" accept=".pdf" required></label><p class="hint">El PDF definitivo se envía sólo después de confirmar esta acción.</p><button type="submit">APROBAR Y ENVIAR A FIRMA</button></form>{% endif %}</section>{% endif %}
</main><script>
const formGenerar = document.querySelector('form[action="/contrato/generar"]');
formGenerar?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const boton = event.submitter;
  const pestañaDrive = window.open('', '_blank');
  boton.disabled = true;
  boton.textContent = 'GENERANDO BORRADOR...';
  try {
    const respuesta = await fetch('/contrato/generar', { method: 'POST', body: new FormData(formGenerar) });
    if (!respuesta.ok) {
      if (pestañaDrive) pestañaDrive.close();
      document.open();
      document.write(await respuesta.text());
      document.close();
      return;
    }
    const contenido = await respuesta.blob();
    const enlace = document.createElement('a');
    enlace.href = URL.createObjectURL(contenido);
    enlace.download = (respuesta.headers.get('content-disposition') || 'borrador.docx').match(/filename\*?=(?:UTF-8'')?([^;]+)/i)?.[1] || 'borrador.docx';
    enlace.click();
    URL.revokeObjectURL(enlace.href);
    const urlDrive = respuesta.headers.get('x-google-drive-url');
    if (urlDrive && pestañaDrive) {
      pestañaDrive.location.href = urlDrive;
    } else if (pestañaDrive) {
      pestañaDrive.close();
      alert('El DOCX fue descargado, pero no se pudo abrir la copia de Google Drive. Revisa la configuración de Google.');
    }
  } catch (error) {
    if (pestañaDrive) pestañaDrive.close();
    alert('No fue posible generar el borrador. Inténtalo nuevamente.');
  } finally {
    boton.disabled = false;
    boton.textContent = 'GENERAR BORRADOR DE CONTRATO';
  }
});
</script></body></html>""")


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
    contenido = PAGE_TEMPLATE.render({
        "registro_id": registro_id,
        "datos": datos_finales,
        "fecha": _fecha(datos_finales.get("fecha", "")) if datos_finales else fecha_hoy(),
        "plantillas": [plantilla.name for plantilla in _plantillas_disponibles()],
        "estado_generado": datos_finales.get("estado") == "Generado",
        "error": error or error_registro,
        "mensaje": mensaje,
        "enviado": enviado,
    })
    return HTMLResponse(contenido, status_code=status_code)


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

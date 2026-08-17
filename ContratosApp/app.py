"""Aplicación FastAPI para generación de borradores y envío a firma."""

from datetime import date, datetime
import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from jinja2 import Environment, select_autoescape

from config import (APP_BASE_URL, DRIVE_REVIEW_FOLDER_ID, MAX_DOCX_SIZE_BYTES, MAX_PDF_SIZE_BYTES,
                    N8N_WEBHOOK_SECRET, N8N_ZAPSIGN_WEBHOOK_URL, ONLYOFFICE_DOCUMENT_SERVER_URL,
                    ONLYOFFICE_JWT_HEADER, ONLYOFFICE_JWT_SECRET, ONLYOFFICE_URL_SIGNING_SECRET)
from drive_service import (ErrorDrive, crear_servicio_drive, descargar_google_doc_como_docx,
                           obtener_credenciales, obtener_documento_por_registro, obtener_url_documento,
                           reemplazar_google_doc_desde_docx, subir_docx_como_google_docs)
from generador import generar_contrato
from modelos import DatosContrato
from n8n_service import ErrorN8N, enviar_pdf_a_firma
from onlyoffice_service import (ErrorOnlyOffice, clave_documento, crear_jwt, crear_token_url,
                                descargar_docx_editado, editor_configurado, jwt_valido,
                                url_api_javascript, validar_token_url)
from sheets_service import ErrorSheets, actualizar_estado_contrato, crear_servicio_sheets, obtener_contrato_pendiente
from utils import email_valido, fecha_hoy, parsear_datos_pegados


BASE_DIR = Path(__file__).resolve().parent
DIRECTORIO_PLANTILLAS = BASE_DIR / "plantillas"
app = FastAPI(title="Generación de borradores de contrato")
LOGGER = logging.getLogger(__name__)


PAGE_TEMPLATE = Environment(autoescape=select_autoescape(default=True)).from_string("""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Generación de borradores de contrato</title><style>
:root{font-family:Inter,system-ui,sans-serif;color:#18212f;background:#f7f9fc;--brand:#003b7a;--brand-dark:#00285b;--brand-soft:#e7eff7;--brand-border:#b6cce0}.container{max-width:900px;margin:0 auto;padding:48px 20px}h1{font-size:2.2rem;margin:0 0 28px}h2{font-size:1.1rem;margin-top:0}.card,details{background:#fff;border:1px solid #dce3ed;border-radius:12px;padding:22px;margin:20px 0}summary{font-weight:700;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}label{display:grid;gap:7px;font-weight:600;margin:14px 0}input,select,textarea{border:1px solid #cbd5e1;border-radius:8px;padding:10px;font:inherit;background:#fff}textarea{resize:vertical;min-height:160px}button,.drive-button{width:100%;box-sizing:border-box;display:block;text-align:center;text-decoration:none;border:0;border-radius:8px;background:var(--brand);color:#fff;font-weight:700;padding:13px;cursor:pointer;margin-top:10px}.secondary{background:#fff;color:var(--brand-dark);border:1px solid var(--brand-border)}.hint{color:#64748b;font-size:.9rem}.notice{padding:12px 14px;border-radius:8px;margin:14px 0}.success{background:#dcfce7;color:#166534}.error{background:#fee2e2;color:#991b1b}.info{background:var(--brand-soft);color:var(--brand-dark)}.modal-backdrop{position:fixed;inset:0;z-index:10;display:grid;place-items:center;padding:20px;background:rgb(15 23 42 / .55)}.modal-backdrop[hidden]{display:none}.modal{width:min(100%,430px);background:#fff;border-radius:18px;padding:32px;text-align:center;box-shadow:0 24px 60px rgb(15 23 42 / .3)}.modal-icon{width:58px;height:58px;margin:0 auto 18px;border-radius:50%;display:grid;place-items:center;background:#dcfce7;color:#15803d;font-size:2rem;font-weight:800}.modal h2{font-size:1.4rem;margin:0 0 10px}.modal p{margin:0;color:#475569;line-height:1.5}.modal button{margin:24px 0 0}.loading-modal{z-index:20}.loading-modal .modal{text-align:left}.loading-heading{display:flex;align-items:center;gap:12px;margin-bottom:20px}.loading-spinner{width:32px;height:32px;border:4px solid var(--brand-soft);border-top-color:var(--brand);border-radius:50%;animation:spin .8s linear infinite}.loading-heading h2{margin:0}.loading-steps{display:grid;gap:12px;margin:0;padding:0;list-style:none}.loading-step{display:flex;align-items:center;gap:12px;padding:11px;border-radius:10px;color:#64748b;background:#f8fafc;transition:.25s ease}.loading-step .emoji{font-size:1.25rem;filter:grayscale(1);transition:.25s ease}.loading-step.active{background:#f0f5fa;color:var(--brand-dark);font-weight:700}.loading-step.active .emoji,.loading-step.done .emoji{filter:none}.loading-step.done{background:#f0fdf4;color:#15803d}.loading-step.done::after{content:'✓';margin-left:auto;font-weight:800}.loading-step.active::after{content:'...';margin-left:auto}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:640px){.grid{grid-template-columns:1fr}.container{padding:28px 14px}}
</style></head><body><main class="container"><h1>Generación de borradores de contrato</h1>
{% if mensaje and not mostrar_modal_exito %}<div class="notice success">✓ {{ mensaje }}</div>{% endif %}{% if error %}<div class="notice error">{{ error }}</div>{% endif %}{% if registro_id %}<div class="notice info">Datos cargados desde Google Sheets.</div>{% endif %}
<details class="paste-data"><summary>Pegar datos desde Excel (opcional)</summary><form action="/datos/pegar" method="post"><input type="hidden" name="registro_id" value="{{ registro_id or '' }}"><p class="hint">Pega las filas copiadas desde Excel. Identificamos automáticamente cada campo.</p><label>Datos copiados<textarea name="datos_pegados" rows="9" placeholder="Nombres: María Ejemplo&#10;Apellidos: Pérez Soto&#10;DNI: DOC-12345678&#10;Celular: +56 9 1111 2222&#10;Email personal: maria.ejemplo@correo.test&#10;Ciudad: Santiago&#10;País: Chile&#10;Monto: 350&#10;Banco: Banco Demo&#10;Productos: Cuenta corriente"></textarea></label><button type="submit" class="secondary">CARGAR DATOS EN EL FORMULARIO</button></form></details>
<form id="generate-contract-form" action="/contrato/generar" method="post" enctype="multipart/form-data"><input type="hidden" name="registro_id" value="{{ registro_id or '' }}"><details {% if not registro_id %}open{% endif %}><summary>¿Quieres verificar los datos?</summary><p class="hint">Puedes revisar o corregir la información antes de crear el borrador.</p><div class="grid"><label>Nombres *<input name="nombres" required value="{{ datos.nombres }}"></label><label>Apellidos *<input name="apellidos" required value="{{ datos.apellidos }}"></label><label>DNI / Documento *<input name="dni" required value="{{ datos.dni }}"></label><label>Celular<input name="celular" value="{{ datos.celular }}"></label><label>Email *<input name="email" type="email" required value="{{ datos.email }}"></label><label>Ciudad<input name="ciudad" value="{{ datos.ciudad }}"></label><label>País<input name="pais" value="{{ datos.pais }}"></label><label>Monto<input name="monto" value="{{ datos.monto }}"></label><label>Banco *<input name="banco" required value="{{ datos.banco }}"></label><label>Productos<input name="productos" value="{{ datos.productos }}"></label></div><label>Fecha *<input name="fecha" type="date" required value="{{ fecha.isoformat() }}"></label></details><section class="card"><h2>Plantilla del contrato</h2><label>Plantilla guardada<select name="plantilla_guardada"><option value="">Seleccione una plantilla</option>{% for plantilla in plantillas %}<option value="{{ plantilla }}">{{ plantilla }}</option>{% endfor %}</select></label><label>Subir plantilla personalizada<input name="plantilla_personalizada" type="file" accept=".docx"></label><p class="hint">La plantilla subida tiene prioridad sobre la plantilla guardada.</p><button type="submit">GENERAR BORRADOR DE CONTRATO</button></section></form>
{% if drive_url %}<section class="card"><h2>Borrador listo para revisión</h2><p>El contrato fue guardado como documento editable en Google Drive.</p>{% if editor_configurado %}<p class="hint">Elige <strong>una</strong> de las siguientes formas para editar el contrato.</p>{% endif %}<section class="card"><h2>1. Editar en Google Drive</h2><p>Realiza los cambios en Drive, descarga el documento como PDF y vuelve a este formulario para subirlo y enviarlo a firma.</p><a class="drive-button" href="{{ drive_url }}" target="_blank" rel="noopener">EDITAR EN GOOGLE DRIVE</a></section>{% if editor_configurado %}<section class="card"><h2>2. Editar en el editor de documento</h2><p>Guarda los cambios y presiona <strong>Volver al formulario</strong>. El PDF se descargará automáticamente y podrás subirlo enseguida para enviarlo a firma.</p><a class="drive-button secondary" href="/contrato/editor/{{ registro_id }}">EDITAR EN EL EDITOR DE DOCUMENTO</a></section>{% else %}<p class="hint">Editor de documentos no configurado. Puedes continuar editando desde Google Drive.</p>{% endif %}</section>{% endif %}
{% if estado_generado or enviado %}<section class="card"><h2>Documento final para firma</h2>{% if enviado %}<p class="hint">El documento fue enviado correctamente a firma.</p>{% else %}<form action="/contrato/enviar" method="post" enctype="multipart/form-data"><input type="hidden" name="registro_id" value="{{ registro_id }}"><p><strong>Firmante:</strong> {{ datos.nombres }} {{ datos.apellidos }}</p><p><strong>Correo:</strong> {{ datos.email }}</p><label>Subir documento PDF final<input name="pdf_final" type="file" accept=".pdf" required></label><p class="hint">El PDF definitivo se envía sólo después de confirmar esta acción.</p><button type="submit">APROBAR Y ENVIAR A FIRMA</button></form>{% endif %}</section>{% endif %}
</main>{% if mostrar_modal_exito %}<div class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-exito-titulo"><section class="modal"><div class="modal-icon" aria-hidden="true">✓</div><h2 id="modal-exito-titulo">{{ titulo_modal_exito }}</h2><p>{{ mensaje }}</p><button type="button" onclick="this.closest('.modal-backdrop').remove()">CONTINUAR</button></section></div>{% endif %}<div id="loading-modal" class="modal-backdrop loading-modal" role="status" aria-live="polite" hidden><section class="modal"><div class="loading-heading"><div class="loading-spinner" aria-hidden="true"></div><div><h2>Estamos creando tu borrador</h2><p>Esto puede tardar unos segundos.</p></div></div><ol class="loading-steps"><li class="loading-step"><span class="emoji">🔎</span> Revisando los datos del contrato</li><li class="loading-step"><span class="emoji">📄</span> Preparando el documento</li><li class="loading-step"><span class="emoji">✍️</span> Agregando los datos a la plantilla</li><li class="loading-step"><span class="emoji">☁️</span> Guardando el borrador</li></ol></section></div><script>const scrollKey='contratos-scroll-position';window.addEventListener('DOMContentLoaded',()=>{try{const savedPosition=sessionStorage.getItem(scrollKey);if(savedPosition!==null){sessionStorage.removeItem(scrollKey);window.requestAnimationFrame(()=>window.scrollTo(0,Number(savedPosition)))}}catch(error){}});document.querySelectorAll('form').forEach(form=>form.addEventListener('submit',()=>{try{sessionStorage.setItem(scrollKey,String(window.scrollY))}catch(error){}}));const generationForm=document.getElementById('generate-contract-form');if(generationForm)generationForm.addEventListener('submit',function(){const loadingModal=document.getElementById('loading-modal');const steps=[...loadingModal.querySelectorAll('.loading-step')];loadingModal.hidden=false;this.querySelector('button[type="submit"]').disabled=true;let current=0;const update=()=>{steps.forEach((step,index)=>step.classList.toggle('done',index<current));steps.forEach((step,index)=>step.classList.toggle('active',index===current));if(current<steps.length-1){current+=1;window.setTimeout(update,900)}};update()});</script></body></html>""")


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
            error: str | None = None, mensaje: str | None = None, drive_url: str | None = None,
            enviado: bool = False, status_code: int = 200):
    registro, error_registro = _obtener_registro(registro_id) if datos is None else (None, None)
    datos_finales = datos or registro or _datos_vacios()
    documento_drive = None
    if registro_id and datos_finales.get("estado") == "Generado":
        try:
            documento_drive = obtener_documento_por_registro(crear_servicio_drive(), registro_id)
            if documento_drive and not drive_url:
                drive_url = obtener_url_documento(documento_drive)
        except ErrorDrive:
            documento_drive = None
    contenido = PAGE_TEMPLATE.render({
        "registro_id": registro_id,
        "datos": datos_finales,
        "fecha": _fecha(datos_finales.get("fecha", "")) if datos_finales else fecha_hoy(),
        "plantillas": [plantilla.name for plantilla in _plantillas_disponibles()],
        "estado_generado": datos_finales.get("estado") == "Generado",
        "error": error or error_registro,
        "mensaje": mensaje,
        "drive_url": drive_url,
        "editor_configurado": editor_configurado(ONLYOFFICE_DOCUMENT_SERVER_URL, ONLYOFFICE_URL_SIGNING_SECRET, APP_BASE_URL),
        "enviado": enviado,
        "mostrar_modal_exito": bool(mensaje and not error and (drive_url or enviado)),
        "titulo_modal_exito": "Documento enviado a firma" if enviado else "Borrador generado con éxito",
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
    error_drive = None
    try:
        documento_drive = subir_docx_como_google_docs(
            crear_servicio_drive(), resultado.contenido, resultado.nombre_archivo,
            DRIVE_REVIEW_FOLDER_ID, registro_id=registro_id or None,
        )
        drive_url = documento_drive.web_view_link
    except ErrorDrive as error:
        error_drive = str(error)
    datos_resultado = dict(datos_formulario)
    if registro_id:
        datos_resultado["estado"] = "Generado"
    return _render(
        request, registro_id=registro_id or None, datos=datos_resultado,
        mensaje="Borrador generado y guardado en Google Drive." if drive_url else "Borrador generado.",
        error=error_drive, drive_url=drive_url or None,
    )


def _editor_habilitado() -> bool:
    return editor_configurado(ONLYOFFICE_DOCUMENT_SERVER_URL, ONLYOFFICE_URL_SIGNING_SECRET, APP_BASE_URL)


def _contrato_generado(registro_id: str) -> dict:
    registro, error = _obtener_registro(registro_id)
    if error or registro is None:
        raise HTTPException(404, "No se encontró el contrato solicitado.")
    if registro.get("estado") != "Generado":
        raise HTTPException(409, "El contrato aún no está generado.")
    return registro


@app.get("/contrato/editor/{registro_id}", response_class=HTMLResponse)
async def abrir_editor(registro_id: str):
    if not _editor_habilitado():
        return HTMLResponse("<h1>Editor no configurado</h1><p>Puedes continuar editando el documento desde Google Drive.</p>", status_code=503)
    _contrato_generado(registro_id)
    try:
        documento = obtener_documento_por_registro(crear_servicio_drive(), registro_id)
    except ErrorDrive:
        documento = None
    if documento is None:
        raise HTTPException(404, "No se encontró el borrador asociado a este registro.")
    token_documento = crear_token_url(registro_id, ONLYOFFICE_URL_SIGNING_SECRET, proposito="documento")
    token_callback = crear_token_url(registro_id, ONLYOFFICE_URL_SIGNING_SECRET, proposito="callback", ttl_segundos=24 * 3600)
    configuracion = {
        "documentType": "word",
        "width": "100%",
        "height": "100%",
        "document": {
            "fileType": "docx", "key": clave_documento(registro_id, documento["id"], documento.get("modifiedTime", "")),
            "title": documento.get("name", "Contrato") + ".docx",
            "url": f"{APP_BASE_URL}/api/onlyoffice/document/{registro_id}?token={token_documento}",
        },
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": f"{APP_BASE_URL}/api/onlyoffice/callback/{registro_id}?token={token_callback}",
            # Esta aplicación tiene un único operador. Un ID fijo evita que
            # ONLYOFFICE contabilice cada contrato abierto como otro usuario.
            "user": {"id": "operador-principal", "name": "Operador principal"},
            # El boton Guardar de ONLYOFFICE dispara el callback status=6.
            # Ahi se guarda el DOCX y se crea el PDF listo para firma.
            "customization": {"forcesave": True},
        },
    }
    if ONLYOFFICE_JWT_SECRET:
        configuracion["token"] = crear_jwt(configuracion, ONLYOFFICE_JWT_SECRET)
    config_json = json.dumps(configuracion).replace("<", "\\u003c")
    pagina = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Editar contrato</title><style>html,body{{height:100%;margin:0}}body{{font-family:Inter,system-ui,sans-serif;background:#f7f9fc;color:#18212f}}header{{background:#fff;border-bottom:1px solid #dce3ed}}.editor-header{{max-width:1180px;margin:0 auto;padding:18px 28px 20px}}.header-top{{display:flex;align-items:center;justify-content:space-between;gap:16px}}.back-link{{display:inline-flex;align-items:center;gap:8px;color:#1d4ed8;text-decoration:none;font-weight:700;padding:9px 12px;border-radius:8px}}.back-link svg{{width:18px;height:18px;stroke:currentColor;stroke-width:2.25;fill:none;stroke-linecap:round;stroke-linejoin:round}}.back-link:hover{{background:#eff6ff}}.status{{display:inline-flex;align-items:center;gap:7px;background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;border-radius:999px;padding:7px 11px;font-size:.84rem;font-weight:700}}.status::before{{content:"";width:7px;height:7px;border-radius:50%;background:#10b981}}.editor-guide{{margin-top:16px}}h1{{font-size:1.45rem;margin:0 0 6px;letter-spacing:-.02em}}.editor-guide p{{margin:0;color:#64748b;line-height:1.5}}.steps{{display:flex;gap:10px;margin:14px 0 0;padding:0;list-style:none;color:#475569;font-size:.9rem}}.steps li{{display:flex;align-items:center;gap:7px}}.step-number{{display:grid;place-items:center;width:20px;height:20px;border-radius:50%;background:#dbeafe;color:#1d4ed8;font-size:.75rem;font-weight:800}}#editor{{height:calc(100vh - 178px);min-height:650px}}@media(max-width:700px){{.editor-header{{padding:16px}}.steps{{flex-direction:column;gap:6px}}#editor{{height:calc(100vh - 278px);min-height:500px}}}}</style></head><body><header><div class="editor-header"><div class="header-top"><a id="back-to-contract" class="back-link" href="/?registro={registro_id}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path><path d="M9 12h11"></path></svg>Volver al formulario</a><span class="status">Borrador en edición</span></div><div class="editor-guide"><h1>Revisa y edita el documento</h1><p>Cuando termines, guarda los cambios en el editor y presiona <strong>Volver al formulario</strong>. El PDF se descargará automáticamente.</p><ol class="steps"><li><span class="step-number">1</span> Edita el contenido</li><li><span class="step-number">2</span> Guarda los cambios</li><li><span class="step-number">3</span> Vuelve al formulario</li></ol></div></div></header><div id="editor">Cargando editor...</div><script src="{url_api_javascript(ONLYOFFICE_DOCUMENT_SERVER_URL)}"></script><script>const config = {config_json}; config.events = {{ onError: function(event) {{ console.error("ONLYOFFICE error", event); document.getElementById("editor").textContent = "No fue posible mostrar el documento en ONLYOFFICE (código " + (event.data && event.data.errorCode || "desconocido") + "). Puedes continuar desde Google Drive."; }} }}; if (window.DocsAPI) {{ new DocsAPI.DocEditor("editor", config); }} else {{ document.getElementById("editor").textContent = "No fue posible cargar el editor. Puedes continuar desde Google Drive."; }}</script></body></html>'''
    # Mantiene el visor de ONLYOFFICE alineado con la paleta institucional.
    pagina = (
        pagina.replace("#1d4ed8", "#00285b")
        .replace("#dbeafe", "#e7eff7")
        .replace("#eff6ff", "#f0f5fa")
    )
    pagina = pagina.replace(
        'if (window.DocsAPI) { new DocsAPI.DocEditor("editor", config); }',
        'var returnAfterDownload = false; '
        'function descargarPdf(url) { var iframe = document.createElement("iframe"); iframe.hidden = true; iframe.src = url; document.body.appendChild(iframe); window.setTimeout(function() { iframe.remove(); }, 60000); } '
        'config.events.onDownloadAs = function(event) { if (!(event.data && event.data.url)) return; '
        'descargarPdf(event.data.url); '
        f'if (returnAfterDownload) window.setTimeout(function() {{ window.location.href = "/?registro={registro_id}"; }}, 250); }}; '
        'if (window.DocsAPI) { window.docEditor = new DocsAPI.DocEditor("editor", config); }',
    )
    pagina = pagina.replace(
        '</script></body>',
        f'''</script><script>document.getElementById("back-to-contract").onclick = function(event) {{
            event.preventDefault(); returnAfterDownload = true;
            window.docEditor.downloadAs("pdf");
            window.setTimeout(function() {{ if (returnAfterDownload) window.location.href = "/?registro={registro_id}"; }}, 3500);
        }};</script></body>''',
    )
    return HTMLResponse(pagina)


@app.get("/api/onlyoffice/document/{registro_id}")
async def documento_onlyoffice(registro_id: str, token: str = ""):
    if not _editor_habilitado() or not validar_token_url(token, registro_id, ONLYOFFICE_URL_SIGNING_SECRET, proposito="documento"):
        raise HTTPException(403, "Acceso no autorizado.")
    _contrato_generado(registro_id)
    try:
        documento = obtener_documento_por_registro(crear_servicio_drive(), registro_id)
        if documento is None:
            raise HTTPException(404, "No se encontró el borrador.")
        contenido = descargar_google_doc_como_docx(crear_servicio_drive(), documento["id"])
    except ErrorDrive as error:
        raise HTTPException(502, "No se pudo obtener el documento para editar.") from error
    return Response(
        contenido, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="contrato.docx"'},
    )


@app.post("/api/onlyoffice/callback/{registro_id}")
async def callback_onlyoffice(registro_id: str, request: Request, token: str = ""):
    if not _editor_habilitado() or not validar_token_url(token, registro_id, ONLYOFFICE_URL_SIGNING_SECRET, proposito="callback"):
        raise HTTPException(403, "Acceso no autorizado.")
    registro, error_registro = _obtener_registro(registro_id)
    if error_registro or registro is None:
        raise HTTPException(404, "No se encontrÃ³ el contrato solicitado.")
    # ONLYOFFICE puede repetir callbacks. Si ya fue enviado, confirmamos sin
    # volver a crear otra solicitud de firma.
    if registro.get("estado") != "Generado":
        return JSONResponse({"error": 0})
    try:
        evento = await request.json()
    except ValueError:
        raise HTTPException(400, "Callback inválido.")
    jwt_callback = evento.get("token", "") or request.headers.get(ONLYOFFICE_JWT_HEADER, "")
    if jwt_callback.lower().startswith("bearer "):
        jwt_callback = jwt_callback[7:]
    if ONLYOFFICE_JWT_SECRET and not jwt_valido(jwt_callback, ONLYOFFICE_JWT_SECRET):
        raise HTTPException(403, "Callback no autorizado.")
    LOGGER.info(
        "ONLYOFFICE callback: registro_id=%s status=%s tiene_url=%s",
        registro_id, evento.get("status"), bool(evento.get("url")),
    )
    if evento.get("status") not in (2, 6) or not evento.get("url"):
        return JSONResponse({"error": 0})
    try:
        contenido = descargar_docx_editado(evento["url"], ONLYOFFICE_DOCUMENT_SERVER_URL, MAX_DOCX_SIZE_BYTES)
        documento = obtener_documento_por_registro(crear_servicio_drive(), registro_id)
        if documento is None:
            raise ErrorDrive("Documento no encontrado.")
        reemplazar_google_doc_desde_docx(crear_servicio_drive(), documento["id"], contenido)
        LOGGER.info("Contrato actualizado desde ONLYOFFICE: registro_id=%s", registro_id)
    except (ErrorOnlyOffice, ErrorDrive) as error:
        LOGGER.warning("No se pudo guardar la edicion: registro_id=%s tipo=%s", registro_id, type(error).__name__)
        return JSONResponse({"error": 1}, status_code=502)
    return JSONResponse({"error": 0})


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
    try:
        actualizar_estado_contrato(crear_servicio_sheets(obtener_credenciales()), registro_id, "Enviado")
    except (ErrorDrive, ErrorSheets) as error_estado:
        return _render(request, registro_id=registro_id, error=str(error_estado), status_code=502)
    return _render(request, registro_id=registro_id, mensaje=resultado.mensaje, enviado=True)

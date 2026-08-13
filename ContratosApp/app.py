"""Interfaz local de Streamlit para la generación de contratos."""

from datetime import datetime
from pathlib import Path

import streamlit as st

from generador import generar_contrato
from modelos import DatosContrato
from utils import email_valido, fecha_hoy, parsear_datos_pegados
from config import DRIVE_REVIEW_FOLDER_ID, MAX_PDF_SIZE_BYTES, N8N_WEBHOOK_SECRET, N8N_ZAPSIGN_WEBHOOK_URL
from drive_service import ErrorDrive, crear_servicio_drive, obtener_credenciales, subir_docx_como_google_docs
from n8n_service import ErrorN8N, enviar_pdf_a_firma, validar_pdf
from sheets_service import ErrorSheets, actualizar_estado_contrato, crear_servicio_sheets, obtener_contrato_pendiente


BASE_DIR = Path(__file__).resolve().parent
DIRECTORIO_PLANTILLAS = BASE_DIR / "plantillas"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _plantillas_disponibles() -> list[Path]:
    return sorted(DIRECTORIO_PLANTILLAS.glob("*.docx"))


def _fecha_desde_sheets(valor: str):
    """Interpreta formatos habituales de Sheets; conserva la fecha actual si falla."""
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except (TypeError, ValueError):
            continue
    return None


def _cargar_registro_desde_sheets(registro_id: str) -> str | None:
    """Carga un registro sólo una vez por UUID, antes de crear los widgets."""
    if st.session_state.get("_registro_cargado") == registro_id:
        return None
    try:
        servicio = crear_servicio_sheets(obtener_credenciales())
        registro = obtener_contrato_pendiente(servicio, registro_id)
    except (ErrorDrive, ErrorSheets) as error:
        return str(error)
    if registro is None:
        st.session_state["_registro_cargado"] = registro_id
        return "No se encontró el registro solicitado en Google Sheets."
    for clave in ("nombres", "apellidos", "dni", "celular", "email", "ciudad", "pais", "monto", "banco", "productos"):
        st.session_state[clave] = registro[clave]
    if fecha := _fecha_desde_sheets(registro["fecha"]):
        st.session_state["fecha"] = fecha
    st.session_state["_registro_cargado"] = registro_id
    st.session_state["_registro_estado"] = registro["estado"]
    st.session_state["_registro_id"] = registro_id
    st.session_state.pop("resultado_contrato", None)
    st.session_state.pop("resultado_drive", None)
    return "Datos cargados automáticamente desde Google Sheets."


def _marcar_registro_generado() -> None:
    """Actualiza Sheets sólo después de que el DOCX se haya creado con éxito."""
    registro_id = st.session_state.get("_registro_id")
    if not registro_id or st.session_state.get("_registro_estado") == "Generado":
        return
    try:
        servicio = crear_servicio_sheets(obtener_credenciales())
        if actualizar_estado_contrato(servicio, registro_id, "Generado"):
            st.session_state["_registro_estado"] = "Generado"
        else:
            st.warning("El contrato se generó, pero no se encontró el registro para actualizar su estado.")
    except (ErrorDrive, ErrorSheets):
        st.warning("El contrato se generó, pero no fue posible actualizar su estado en Google Sheets.")


def _limpiar_firma_al_cambiar_registro(registro_id: str | None) -> None:
    """Evita asociar el PDF de una persona a otro UUID."""
    if st.session_state.get("_firma_registro_id") == registro_id:
        return
    for clave in ("_firma_pdf_nombre", "_firma_pdf_bytes", "_registro_enviado"):
        st.session_state.pop(clave, None)
    st.session_state["_firma_registro_id"] = registro_id


def _seccion_firma(nombres: str, apellidos: str, email: str) -> None:
    """Presenta el paso manual de PDF y el único botón que puede llamar a n8n."""
    st.divider()
    st.subheader("Documento final para firma")
    registro_id = st.session_state.get("_registro_id")
    if not registro_id:
        st.caption("Para enviar automáticamente a firma, abre el contrato desde Google Sheets.")
        return

    archivo_pdf = st.file_uploader("Subir documento PDF final", type=["pdf"], key=f"pdf_final_{registro_id}")
    if archivo_pdf is not None:
        pdf_bytes = archivo_pdf.getvalue()
        try:
            validar_pdf(archivo_pdf.name, pdf_bytes, MAX_PDF_SIZE_BYTES)
            st.session_state["_firma_pdf_nombre"] = archivo_pdf.name
            st.session_state["_firma_pdf_bytes"] = pdf_bytes
        except ErrorN8N as error:
            st.session_state.pop("_firma_pdf_nombre", None)
            st.session_state.pop("_firma_pdf_bytes", None)
            st.error(str(error))

    nombre = f"{nombres.strip()} {apellidos.strip()}".strip()
    pdf_nombre = st.session_state.get("_firma_pdf_nombre")
    pdf_bytes = st.session_state.get("_firma_pdf_bytes")
    if pdf_nombre:
        st.write(f"**Firmante:** {nombre}")
        st.write(f"**Correo:** {email.strip()}")
        st.write(f"**Documento:** {pdf_nombre}")

    if st.session_state.get("_registro_enviado") == registro_id:
        st.success("✅ Enviado a firma")
        return
    habilitado = bool(pdf_bytes and nombre and email_valido(email))
    if st.button("APROBAR Y ENVIAR A FIRMA", type="primary", use_container_width=True, disabled=not habilitado):
        try:
            resultado = enviar_pdf_a_firma(
                N8N_ZAPSIGN_WEBHOOK_URL, registro_id, nombre, email, pdf_nombre, pdf_bytes,
                webhook_secret=N8N_WEBHOOK_SECRET or None, max_size_bytes=MAX_PDF_SIZE_BYTES,
            )
        except ErrorN8N as error:
            st.error(str(error))
        else:
            st.session_state["_registro_enviado"] = registro_id
            st.success("✅ Contrato enviado correctamente a firma.")


def _subir_resultado_a_drive(resultado, permitir_duplicado: bool = False) -> None:
    """Intenta la extensión Drive sin afectar la descarga local del DOCX."""
    try:
        servicio = crear_servicio_drive()
        st.session_state["resultado_drive"] = subir_docx_como_google_docs(
            servicio, resultado.contenido, resultado.nombre_archivo,
            DRIVE_REVIEW_FOLDER_ID, permitir_duplicado=permitir_duplicado,
        )
        st.session_state.pop("error_drive", None)
    except ErrorDrive as error:
        st.session_state["error_drive"] = str(error)
        st.session_state.pop("resultado_drive", None)


def _mostrar_resultado(resultado) -> None:
    """Muestra Drive como acción principal y conserva la descarga DOCX de respaldo."""
    st.success(" Contrato generado correctamente")
    st.write(f"**Archivo:** {resultado.nombre_archivo}")
    resultado_drive = st.session_state.get("resultado_drive")
    if resultado_drive:
        if resultado_drive.duplicado:
            st.warning("Ya existe un contrato con este nombre en Google Drive.")
            st.link_button("ABRIR CONTRATO EXISTENTE", resultado_drive.web_view_link, use_container_width=True)
            if st.button("CREAR UNA NUEVA VERSIÓN", use_container_width=True):
                _subir_resultado_a_drive(resultado, permitir_duplicado=True)
                st.rerun()
        else:
            st.success(" Contrato guardado en Google Drive")
            st.link_button("ABRIR CONTRATO EN DRIVE", resultado_drive.web_view_link, type="primary", use_container_width=True)
    elif error_drive := st.session_state.get("error_drive"):
        st.warning(f"⚠️ {error_drive} Puedes descargar el DOCX y reintentar después.")

    st.download_button(
        "DESCARGAR DOCX", data=resultado.contenido,
        file_name=resultado.nombre_archivo, mime=MIME_DOCX,
        use_container_width=True,
    )
    if resultado.placeholders_no_encontrados:
        st.info("Algunos campos no aparecen en esta plantilla: " + ", ".join(resultado.placeholders_no_encontrados))


def main() -> None:
    st.set_page_config(page_title="Gestión de Contratos", page_icon="📄", layout="centered")
    st.title("Gestión de Contratos")
    st.subheader("Generación de contrato")
    st.caption("Complete los datos, genere el Word editable y revíselo antes de enviarlo a firma.")

    registro_id = st.query_params.get("registro")
    _limpiar_firma_al_cambiar_registro(registro_id)
    if registro_id:
        mensaje_carga = _cargar_registro_desde_sheets(registro_id)
        if mensaje_carga:
            if mensaje_carga.startswith("Datos cargados"):
                st.caption(f" {mensaje_carga}")
            else:
                st.warning(mensaje_carga)

    with st.expander("Pegar datos desde Excel", expanded=True):
        st.caption("Pegue las filas copiadas desde Excel. Ejemplo: Nombres: María Ejemplo")
        texto_pegado = st.text_area(
            "Datos copiados", key="datos_excel", height=190,
            placeholder="Nombres: María\nApellidos: Ejemplo López\nDNI: DOC-12345678\nCelular de Contacto: +56 9 1111 2222\nEmail personal: maria.ejemplo@correo.test\nCiudad: Santiago\nPaís: Chile\nMonto: 350\nBanco: Banco Demo\nProductos: Cuenta de prueba",
            label_visibility="collapsed",
        )
        if st.button("CARGAR DATOS EN EL FORMULARIO", use_container_width=True):
            campos, no_reconocidas = parsear_datos_pegados(texto_pegado)
            if not campos:
                st.warning("No se reconocieron campos. Verifica que cada fila tenga el formato Campo: valor.")
            else:
                for clave, valor in campos.items():
                    st.session_state[clave] = valor
                st.session_state["lineas_no_reconocidas"] = no_reconocidas
                st.rerun()
        if no_reconocidas := st.session_state.pop("lineas_no_reconocidas", []):
            st.info("No se cargaron estas líneas: " + " | ".join(no_reconocidas))

    plantillas = _plantillas_disponibles()
    with st.form("formulario_contrato"):
        columna_1, columna_2 = st.columns(2)
        with columna_1:
            nombres = st.text_input("Nombres *", key="nombres")
            dni = st.text_input("DNI / Documento *", key="dni")
            email = st.text_input("Email *", key="email")
            ciudad = st.text_input("Ciudad", key="ciudad")
            monto = st.text_input("Monto", key="monto")
        with columna_2:
            apellidos = st.text_input("Apellidos *", key="apellidos")
            celular = st.text_input("Celular", key="celular")
            pais = st.text_input("País", key="pais")
            banco = st.text_input("Banco *", key="banco")
            productos = st.text_input("Productos", key="productos")

        fecha = st.date_input("Fecha *", value=st.session_state.get("fecha", fecha_hoy()), format="DD/MM/YYYY", key="fecha")
        seleccion = st.selectbox(
            "Plantilla guardada",
            options=[None, *plantillas],
            format_func=lambda item: "Seleccione una plantilla" if item is None else item.name,
        )
        subida = st.file_uploader("Subir plantilla personalizada", type=["docx"])
        st.caption("La plantilla subida tiene prioridad sobre la plantilla guardada.")
        generar = st.form_submit_button("GENERAR CONTRATO", type="primary", use_container_width=True)

    if not generar and "resultado_contrato" not in st.session_state:
        st.divider()
        st.subheader("Próximamente")
        st.button("Aprobar y enviar a firma", disabled=True, use_container_width=True)
        return

    if generar:
        obligatorios = [nombres.strip(), apellidos.strip(), dni.strip(), email.strip(), banco.strip()]
        if not all(obligatorios) or (subida is None and seleccion is None):
            st.warning("⚠️ Debes completar los campos obligatorios y seleccionar o subir una plantilla.")
            return
        if not email_valido(email):
            st.warning("⚠️ Ingresa un correo electrónico válido.")
            return

        datos = DatosContrato(
            nombres=nombres.strip(), apellidos=apellidos.strip(), dni=dni.strip(),
            celular_contacto=celular.strip(), email_personal=email.strip(), ciudad=ciudad.strip(),
            pais=pais.strip(), monto=monto.strip(), banco=banco.strip(), productos=productos.strip(), fecha=fecha,
        )
        try:
            plantilla = subida.getvalue() if subida is not None else seleccion
            resultado = generar_contrato(plantilla, datos)
        except Exception:
            st.error("No fue posible generar el contrato. Verifica que la plantilla Word sea válida e inténtalo nuevamente.")
            return
        st.session_state["resultado_contrato"] = resultado
        st.session_state.pop("resultado_drive", None)
        st.session_state.pop("error_drive", None)
        _marcar_registro_generado()
        _subir_resultado_a_drive(resultado)

    _mostrar_resultado(st.session_state["resultado_contrato"])
    _seccion_firma(nombres, apellidos, email)


if __name__ == "__main__":
    main()

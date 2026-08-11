"""Interfaz local de Streamlit para la generación de contratos."""

from pathlib import Path

import streamlit as st

from generador import generar_contrato
from modelos import DatosContrato
from utils import email_valido, fecha_hoy


BASE_DIR = Path(__file__).resolve().parent
DIRECTORIO_PLANTILLAS = BASE_DIR / "plantillas"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _plantillas_disponibles() -> list[Path]:
    return sorted(DIRECTORIO_PLANTILLAS.glob("*.docx"))


def main() -> None:
    st.set_page_config(page_title="Gestión de Contratos", page_icon="📄", layout="centered")
    st.title("Gestión de Contratos")
    st.subheader("Generación de contrato")
    st.caption("Complete los datos, genere el Word editable y revíselo antes de enviarlo a firma.")

    plantillas = _plantillas_disponibles()
    with st.form("formulario_contrato"):
        columna_1, columna_2 = st.columns(2)
        with columna_1:
            nombres = st.text_input("Nombres *")
            dni = st.text_input("DNI / Documento *")
            email = st.text_input("Email *")
            ciudad = st.text_input("Ciudad")
            monto = st.text_input("Monto")
        with columna_2:
            apellidos = st.text_input("Apellidos *")
            celular = st.text_input("Celular")
            pais = st.text_input("País")
            banco = st.text_input("Banco *")
            productos = st.text_input("Productos")

        fecha = st.date_input("Fecha *", value=fecha_hoy(), format="DD/MM/YYYY")
        seleccion = st.selectbox(
            "Plantilla guardada",
            options=[None, *plantillas],
            format_func=lambda item: "Seleccione una plantilla" if item is None else item.name,
        )
        subida = st.file_uploader("Subir plantilla personalizada", type=["docx"])
        st.caption("La plantilla subida tiene prioridad sobre la plantilla guardada.")
        generar = st.form_submit_button("GENERAR CONTRATO", type="primary", use_container_width=True)

    if not generar:
        st.divider()
        st.subheader("Próximamente")
        st.button("Aprobar y enviar a firma", disabled=True, use_container_width=True)
        return

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

    st.success("✅ Contrato generado correctamente")
    st.write(f"**Archivo:** {resultado.nombre_archivo}")
    st.download_button(
        "DESCARGAR CONTRATO", data=resultado.contenido,
        file_name=resultado.nombre_archivo, mime=MIME_DOCX,
        type="primary", use_container_width=True,
    )
    if resultado.placeholders_no_encontrados:
        st.info("Algunos campos no aparecen en esta plantilla: " + ", ".join(resultado.placeholders_no_encontrados))


if __name__ == "__main__":
    main()

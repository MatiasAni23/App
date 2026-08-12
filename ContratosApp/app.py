"""Interfaz local de Streamlit para la generación de contratos."""

from pathlib import Path

import streamlit as st

from generador import generar_contrato
from modelos import DatosContrato
from utils import email_valido, fecha_hoy, parsear_datos_pegados


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

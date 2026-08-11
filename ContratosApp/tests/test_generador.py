from datetime import date
from io import BytesIO
import unittest

from docx import Document

from generador import formatear_fecha, generar_contrato, generar_nombre_archivo
from modelos import DatosContrato
from utils import sanitizar_nombre_archivo


def datos_prueba() -> DatosContrato:
    return DatosContrato(
        nombres="Ana", apellidos="Pérez", dni="123", celular_contacto="", email_personal="ana@example.com",
        ciudad="Santiago", pais="Chile", monto="350", banco="Banco/Estado", productos="Cuenta", fecha=date(2027, 1, 2),
    )


class GeneradorTests(unittest.TestCase):
    def test_fecha_dinamica(self):
        self.assertEqual(formatear_fecha(date(2027, 1, 2)), "02 de enero de 2027")
        self.assertTrue(generar_nombre_archivo(datos_prueba()).startswith("02012027_"))

    def test_sanitizar_nombre(self):
        self.assertEqual(sanitizar_nombre_archivo('A<B>:C"/D\\E|F?G*'), "ABCDEFG")

    def test_nombre_archivo(self):
        nombre = generar_nombre_archivo(datos_prueba())
        self.assertEqual(nombre, "02012027_Ana Pérez_BancoEstado_Contrato Apertura de Cuentas_acuerdo 2026.docx")

    def test_reemplaza_placeholder_dividido_en_runs_y_tabla(self):
        documento = Document()
        parrafo = documento.add_paragraph()
        parrafo.add_run("Cliente: <<Nom")
        parrafo.add_run("bres>>")
        celda = documento.add_table(rows=1, cols=1).cell(0, 0)
        celda.text = "Banco: <<Banco>>"
        plantilla = BytesIO()
        documento.save(plantilla)

        resultado = generar_contrato(plantilla.getvalue(), datos_prueba())
        generado = Document(BytesIO(resultado.contenido))
        self.assertEqual(generado.paragraphs[0].text, "Cliente: Ana")
        self.assertEqual(generado.tables[0].cell(0, 0).text, "Banco: Banco/Estado")


if __name__ == "__main__":
    unittest.main()

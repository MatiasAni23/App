import unittest
from unittest.mock import MagicMock

from sheets_service import actualizar_estado_contrato, obtener_contrato_pendiente


class SheetsServiceTests(unittest.TestCase):
    def setUp(self):
        self.servicio = MagicMock()

    def test_registro_encontrado_incluye_monto_y_todas_las_columnas(self):
        self.servicio.spreadsheets().values().get().execute.return_value = {"values": [[
            "ID", "Fecha", "Nombres", "Apellidos", "DNI", "Celular", "Email", "Ciudad", "País", "Monto", "Banco", "Productos", "Estado",
        ], [
            "abc", "12/08/2026", "María", "Ejemplo", "123", "999", "maria@test.cl", "Santiago", "Chile", "100,50", "Banco Demo", "Cuenta", "Pendiente",
        ]]}
        registro = obtener_contrato_pendiente(self.servicio, "abc", "spreadsheet-1")
        self.assertEqual(registro["nombres"], "María")
        self.assertEqual(registro["monto"], "100,50")
        self.assertEqual(registro["productos"], "Cuenta")

    def test_registro_inexistente_devuelve_none(self):
        self.servicio.spreadsheets().values().get().execute.return_value = {"values": [["otro-id"]]}
        self.assertIsNone(obtener_contrato_pendiente(self.servicio, "abc", "spreadsheet-1"))

    def test_fila_incompleta_no_produce_error(self):
        self.servicio.spreadsheets().values().get().execute.return_value = {"values": [["abc", "", "María"]]}
        registro = obtener_contrato_pendiente(self.servicio, "abc", "spreadsheet-1")
        self.assertEqual(registro["nombres"], "María")
        self.assertEqual(registro["monto"], "")
        self.assertEqual(registro["estado"], "")

    def test_actualiza_solo_columna_m(self):
        self.servicio.spreadsheets().values().get().execute.return_value = {"values": [["ID"], ["abc"]]}
        self.assertTrue(actualizar_estado_contrato(self.servicio, "abc", "Generado", "spreadsheet-1"))
        argumentos = self.servicio.spreadsheets().values().update.call_args.kwargs
        self.assertEqual(argumentos["range"], "Contratos_Pendientes!M2")
        self.assertEqual(argumentos["body"], {"values": [["Generado"]]})

    def test_actualizar_id_inexistente_devuelve_false(self):
        self.servicio.spreadsheets().values().get().execute.return_value = {"values": [["ID"], ["otro"]]}
        self.assertFalse(actualizar_estado_contrato(self.servicio, "abc", "Generado", "spreadsheet-1"))
        self.servicio.spreadsheets().values().update.assert_not_called()


if __name__ == "__main__":
    unittest.main()

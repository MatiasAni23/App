from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app


class AppSheetsTests(unittest.TestCase):
    def test_mismo_registro_no_sobrescribe_edicion_en_rerun(self):
        streamlit_falso = SimpleNamespace(session_state={})
        registro = {
            "id": "abc", "fecha": "12/08/2026", "nombres": "María", "apellidos": "Ejemplo",
            "dni": "123", "celular": "999", "email": "maria@test.cl", "ciudad": "Santiago",
            "pais": "Chile", "monto": "100,50", "banco": "Banco Demo", "productos": "Cuenta", "estado": "Pendiente",
        }
        with patch.object(app, "st", streamlit_falso), \
             patch.object(app, "obtener_credenciales"), \
             patch.object(app, "crear_servicio_sheets"), \
             patch.object(app, "obtener_contrato_pendiente", return_value=registro) as obtener:
            self.assertEqual(app._cargar_registro_desde_sheets("abc"), "Datos cargados automáticamente desde Google Sheets.")
            streamlit_falso.session_state["monto"] = "200"  # edición manual
            self.assertIsNone(app._cargar_registro_desde_sheets("abc"))
        self.assertEqual(streamlit_falso.session_state["monto"], "200")
        obtener.assert_called_once()


if __name__ == "__main__":
    unittest.main()

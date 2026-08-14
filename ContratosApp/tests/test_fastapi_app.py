import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class FastAPIAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)

    @patch("app._obtener_registro", return_value=(None, None))
    def test_inicio_manual_responde(self, _obtener):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Generación de borradores de contrato", respuesta.text)

    @patch("app._obtener_registro")
    def test_registro_inexistente_muestra_error_controlado(self, obtener):
        obtener.return_value = (None, "No se encontró el registro solicitado en Google Sheets.")
        respuesta = self.client.get("/?registro=uuid-inexistente")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("No se encontró el registro solicitado", respuesta.text)

    @patch("app._obtener_registro")
    def test_registro_valido_carga_datos(self, obtener):
        obtener.return_value = ({"id": "uuid", "nombres": "María", "apellidos": "Ejemplo", "dni": "1", "celular": "", "email": "maria@example.com", "ciudad": "", "pais": "", "monto": "100", "banco": "Banco", "productos": "Cuenta", "fecha": "2026-08-14", "estado": "Pendiente"}, None)
        respuesta = self.client.get("/?registro=uuid")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('value="María"', respuesta.text)

    def test_datos_pegados_se_cargan_en_el_formulario(self):
        respuesta = self.client.post(
            "/datos/pegar",
            data={"datos_pegados": "Nombres: Ana\nApellidos: Demo\nDNI: 123\nBanco: Banco Prueba\nEmail: ana@ejemplo.test"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('value="Ana"', respuesta.text)
        self.assertIn('value="Banco Prueba"', respuesta.text)


if __name__ == "__main__":
    unittest.main()

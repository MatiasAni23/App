import unittest
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

import app
from security import firma_acceso


REGISTRO_A = "123e4567-e89b-12d3-a456-426614174000"
REGISTRO_B = "123e4567-e89b-12d3-a456-426614174001"
SECRETO = "test-secret"


def registro_prueba(registro_id=REGISTRO_A):
    return {"id": registro_id, "nombres": "María", "apellidos": "Ejemplo", "dni": "1", "celular": "", "email": "maria@example.com", "ciudad": "", "pais": "", "monto": "100", "banco": "Banco", "productos": "Cuenta", "fecha": "2026-08-14", "estado": "Pendiente"}


class FastAPIAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app, base_url="https://testserver")

    @patch("app._obtener_registro", return_value=(None, None))
    def test_inicio_manual_responde(self, _obtener):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("Acceso no autorizado", respuesta.text)
        self.assertNotIn("Generación de borradores", respuesta.text)

    @patch("app._obtener_registro")
    def test_enlace_firmado_crea_sesion_y_redirige_sin_token(self, obtener):
        expiracion = int(time.time()) + 1800
        obtener.return_value = (registro_prueba(), None)
        with patch.object(app, "APP_ACCESS_SECRET", SECRETO):
            respuesta = self.client.get(
                f"/access?registro={REGISTRO_A}&exp={expiracion}&token={firma_acceso(REGISTRO_A, expiracion, SECRETO)}",
                follow_redirects=False,
            )
        self.assertEqual(respuesta.status_code, 303)
        self.assertEqual(respuesta.headers["location"], f"/?registro={REGISTRO_A}")
        self.assertNotIn("token=", respuesta.headers["location"])
        self.assertIn("contrato_session", respuesta.headers["set-cookie"])

    @patch("app._obtener_registro")
    def test_enlace_modificado_se_rechaza(self, obtener):
        expiracion = int(time.time()) + 1800
        obtener.return_value = (registro_prueba(), None)
        with patch.object(app, "APP_ACCESS_SECRET", SECRETO):
            respuesta = self.client.get(
                f"/access?registro={REGISTRO_A}&exp={expiracion + 1}&token={firma_acceso(REGISTRO_A, expiracion, SECRETO)}",
            )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json(), {"detail": "Acceso no autorizado."})

    @patch("app._obtener_registro")
    def test_sesion_no_puede_cambiar_de_registro(self, obtener):
        expiracion = int(time.time()) + 1800
        obtener.return_value = (registro_prueba(REGISTRO_A), None)
        with patch.object(app, "APP_ACCESS_SECRET", SECRETO):
            self.client.get(
                f"/access?registro={REGISTRO_A}&exp={expiracion}&token={firma_acceso(REGISTRO_A, expiracion, SECRETO)}",
                follow_redirects=False,
            )
            respuesta = self.client.get(f"/?registro={REGISTRO_B}")
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("Acceso no autorizado", respuesta.text)

    @patch("app._obtener_registro")
    def test_registro_inexistente_muestra_acceso_denegado(self, obtener):
        obtener.return_value = (None, "No se encontró el registro solicitado en Google Sheets.")
        expiracion = int(time.time()) + 1800
        with patch.object(app, "APP_ACCESS_SECRET", SECRETO):
            respuesta = self.client.get(
                f"/access?registro={REGISTRO_A}&exp={expiracion}&token={firma_acceso(REGISTRO_A, expiracion, SECRETO)}",
            )
        self.assertEqual(respuesta.status_code, 403)

    @patch("app._obtener_registro")
    def test_registro_valido_carga_datos(self, obtener):
        obtener.return_value = (registro_prueba(), None)
        expiracion = int(time.time()) + 1800
        with patch.object(app, "APP_ACCESS_SECRET", SECRETO):
            self.client.get(f"/access?registro={REGISTRO_A}&exp={expiracion}&token={firma_acceso(REGISTRO_A, expiracion, SECRETO)}", follow_redirects=False)
            respuesta = self.client.get(f"/?registro={REGISTRO_A}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('value="María"', respuesta.text)

    @patch("app._obtener_registro", return_value=(registro_prueba(), None))
    def test_datos_pegados_se_cargan_en_el_formulario(self, _obtener):
        expiracion = int(time.time()) + 1800
        with patch.object(app, "APP_ACCESS_SECRET", SECRETO):
            self.client.get(f"/access?registro={REGISTRO_A}&exp={expiracion}&token={firma_acceso(REGISTRO_A, expiracion, SECRETO)}", follow_redirects=False)
            respuesta = self.client.post("/datos/pegar", data={"registro_id": REGISTRO_A, "datos_pegados": "Nombres: Ana\nApellidos: Demo\nDNI: 123\nBanco: Banco Prueba\nEmail: ana@ejemplo.test"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('value="Ana"', respuesta.text)
        self.assertIn('value="Banco Prueba"', respuesta.text)


if __name__ == "__main__":
    unittest.main()

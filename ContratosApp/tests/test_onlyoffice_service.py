import unittest
from unittest.mock import patch

from onlyoffice_service import clave_documento, crear_token_url, validar_token_url


class OnlyOfficeServiceTests(unittest.TestCase):
    @patch("onlyoffice_service.time.time", return_value=1000)
    def test_token_solo_autoriza_el_registro_y_proposito_correctos(self, _tiempo):
        token = crear_token_url("registro-a", "secreto", proposito="documento", ttl_segundos=60)
        self.assertTrue(validar_token_url(token, "registro-a", "secreto", proposito="documento"))
        self.assertFalse(validar_token_url(token, "registro-b", "secreto", proposito="documento"))
        self.assertFalse(validar_token_url(token, "registro-a", "secreto", proposito="callback"))

    @patch("onlyoffice_service.time.time", return_value=1001)
    def test_token_expirado_es_rechazado(self, _tiempo):
        token = crear_token_url("registro-a", "secreto", proposito="documento", ttl_segundos=-1)
        self.assertFalse(validar_token_url(token, "registro-a", "secreto", proposito="documento"))

    def test_clave_cambia_al_cambiar_version(self):
        self.assertNotEqual(clave_documento("a", "file", "v1"), clave_documento("a", "file", "v2"))


if __name__ == "__main__":
    unittest.main()

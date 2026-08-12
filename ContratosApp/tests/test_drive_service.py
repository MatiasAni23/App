from io import BytesIO
import unittest
from unittest.mock import MagicMock

from drive_service import (
    CarpetaNoEncontrada,
    SinPermisoCarpeta,
    buscar_documento_duplicado,
    subir_docx_como_google_docs,
    verificar_carpeta,
)


class DriveServiceTests(unittest.TestCase):
    def setUp(self):
        self.servicio = MagicMock()
        self.servicio.files().get().execute.return_value = {
            "id": "folder-1", "name": "Contratos Pendientes",
            "mimeType": "application/vnd.google-apps.folder",
            "capabilities": {"canAddChildren": True},
        }

    def test_carpeta_no_es_carpeta(self):
        self.servicio.files().get().execute.return_value["mimeType"] = "application/vnd.google-apps.document"
        with self.assertRaises(CarpetaNoEncontrada):
            verificar_carpeta(self.servicio, "folder-1")

    def test_carpeta_sin_permiso_de_escritura(self):
        self.servicio.files().get().execute.return_value["capabilities"] = {"canAddChildren": False}
        with self.assertRaises(SinPermisoCarpeta):
            verificar_carpeta(self.servicio, "folder-1")

    def test_duplicado_devuelve_documento_existente_sin_crear_otro(self):
        self.servicio.files().list().execute.return_value = {"files": [{
            "id": "existente", "name": "Contrato", "webViewLink": "https://drive.example/existente",
        }]}
        resultado = subir_docx_como_google_docs(self.servicio, b"docx", "Contrato.docx", "folder-1")
        self.assertTrue(resultado.duplicado)
        self.assertEqual(resultado.id, "existente")
        self.servicio.files().create.assert_not_called()

    def test_subida_construye_metadata_google_docs(self):
        self.servicio.files().list().execute.return_value = {"files": []}
        self.servicio.files().create().execute.return_value = {
            "id": "nuevo", "name": "Contrato", "webViewLink": "https://drive.example/nuevo", "parents": ["folder-1"],
        }
        resultado = subir_docx_como_google_docs(self.servicio, b"docx", "Contrato.docx", "folder-1")
        self.assertFalse(resultado.duplicado)
        argumentos = self.servicio.files().create.call_args.kwargs
        self.assertEqual(argumentos["body"], {
            "name": "Contrato", "mimeType": "application/vnd.google-apps.document", "parents": ["folder-1"],
        })
        self.assertTrue(argumentos["supportsAllDrives"])


if __name__ == "__main__":
    unittest.main()

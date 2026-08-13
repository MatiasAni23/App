import base64
import unittest
from unittest.mock import MagicMock, patch

from n8n_service import ErrorN8N, enviar_pdf_a_firma, validar_pdf


class N8NServiceTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"%PDF-1.7\ncontenido-prueba"

    def test_pdf_valido(self):
        validar_pdf("contrato.pdf", self.pdf, 1024)

    def test_rechaza_extension_falsa_y_pdf_vacio(self):
        with self.assertRaises(ErrorN8N):
            validar_pdf("contrato.pdf", b"no es pdf", 1024)
        with self.assertRaises(ErrorN8N):
            validar_pdf("contrato.docx", self.pdf, 1024)
        with self.assertRaises(ErrorN8N):
            validar_pdf("contrato.pdf", b"", 1024)

    @patch("n8n_service.requests.post")
    def test_payload_minimo_y_base64_sin_data_uri(self, post):
        respuesta = MagicMock()
        respuesta.json.return_value = {"ok": True, "estado": "Enviado"}
        post.return_value = respuesta
        resultado = enviar_pdf_a_firma(
            "https://n8n.example/webhook", "uuid", "María Ejemplo", "maria@example.com",
            "final.pdf", self.pdf, max_size_bytes=1024,
        )
        self.assertTrue(resultado.ok)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(set(payload), {"registro_id", "nombre", "email", "nombre_archivo", "pdf_base64"})
        self.assertEqual(payload["pdf_base64"], base64.b64encode(self.pdf).decode("utf-8"))
        self.assertFalse(payload["pdf_base64"].startswith("data:"))

    def test_rechaza_campos_necesarios(self):
        with self.assertRaises(ErrorN8N):
            enviar_pdf_a_firma("no-es-url", "id", "María", "maria@example.com", "a.pdf", self.pdf, max_size_bytes=1024)
        with self.assertRaises(ErrorN8N):
            enviar_pdf_a_firma("url", "", "María", "maria@example.com", "a.pdf", self.pdf, max_size_bytes=1024)
        with self.assertRaises(ErrorN8N):
            enviar_pdf_a_firma("url", "id", "", "maria@example.com", "a.pdf", self.pdf, max_size_bytes=1024)
        with self.assertRaises(ErrorN8N):
            enviar_pdf_a_firma("url", "id", "María", "invalido", "a.pdf", self.pdf, max_size_bytes=1024)


if __name__ == "__main__":
    unittest.main()

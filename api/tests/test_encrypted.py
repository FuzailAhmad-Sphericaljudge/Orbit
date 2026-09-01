import unittest

from cryptography.fernet import Fernet

from app.config import get_settings
from app.encrypted import EncryptedText, PREFIX


class EncryptedTextTests(unittest.TestCase):
    def test_round_trip_uses_authenticated_ciphertext(self):
        settings = get_settings()
        original = settings.data_encryption_key
        try:
            settings.data_encryption_key = Fernet.generate_key().decode("ascii")
            column = EncryptedText()
            stored = column.process_bind_param("customer-impact", None)
            self.assertTrue(stored.startswith(PREFIX))
            self.assertNotIn("customer-impact", stored)
            self.assertEqual(column.process_result_value(stored, None), "customer-impact")
        finally:
            settings.data_encryption_key = original

    def test_development_without_key_remains_compatible(self):
        settings = get_settings()
        original = settings.data_encryption_key
        try:
            settings.data_encryption_key = ""
            column = EncryptedText()
            self.assertEqual(column.process_bind_param("local-value", None), "local-value")
        finally:
            settings.data_encryption_key = original


if __name__ == "__main__":
    unittest.main()

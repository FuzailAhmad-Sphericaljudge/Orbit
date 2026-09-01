from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from .config import get_settings


PREFIX = "enc:v1:"


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def cipher(self) -> Fernet | None:
        key = get_settings().data_encryption_key
        return Fernet(key.encode("ascii")) if key else None

    def process_bind_param(self, value, dialect):
        if value is None or (isinstance(value, str) and value.startswith(PREFIX)):
            return value
        cipher = self.cipher()
        if cipher is None:
            return value
        return PREFIX + cipher.encrypt(str(value).encode("utf-8")).decode("ascii")

    def process_result_value(self, value, dialect):
        if value is None or not isinstance(value, str) or not value.startswith(PREFIX):
            return value
        cipher = self.cipher()
        if cipher is None:
            raise RuntimeError("Encrypted data cannot be read without DATA_ENCRYPTION_KEY")
        try:
            return cipher.decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Encrypted field authentication failed") from exc

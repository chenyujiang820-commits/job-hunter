"""Encryption helpers for user-owned model credentials."""

from cryptography.fernet import Fernet, InvalidToken


class CredentialConfigurationError(ValueError):
    pass


class CredentialCipher:
    def __init__(self, secret: str):
        if not secret:
            raise CredentialConfigurationError("model credential encryption key is not configured")
        try:
            self._fernet = Fernet(secret.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise CredentialConfigurationError("model credential encryption key is invalid") from exc

    @classmethod
    def from_secret(cls, secret: str) -> "CredentialCipher | None":
        return cls(secret) if secret else None

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
            raise CredentialConfigurationError("stored model credential cannot be decrypted") from exc

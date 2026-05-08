"""
services/credential_manager.py — Credential Encryption
========================================================
Uses Fernet symmetric encryption (AES-128-CBC) to protect
portal passwords stored in the database.

MENTOR NOTE:
  Why Fernet? Because we need to DECRYPT credentials later
  (to log into portals). bcrypt is one-way — can't decrypt.
  Fernet is reversible AND secure, perfect for this use case.

Usage:
    from backend.services.credential_manager import CredentialManager

    manager = CredentialManager()
    encrypted = manager.encrypt("my_password_123")
    original  = manager.decrypt(encrypted)
"""

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from backend.config import settings


class CredentialManager:
    """
    Handles encryption and decryption of sensitive credentials.
    The encryption key comes from MASTER_ENCRYPTION_KEY in .env.
    """

    def __init__(self):
        key = settings.master_encryption_key.encode()
        self._fernet = Fernet(key)

    def encrypt(self, plain_text: str) -> str:
        """
        Encrypts a plain-text string (e.g., password).

        Args:
            plain_text: The raw string to encrypt.

        Returns:
            Base64-encoded encrypted string (safe to store in DB).
        """
        if not plain_text:
            raise ValueError("Cannot encrypt empty string.")

        encrypted_bytes = self._fernet.encrypt(plain_text.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")  # Return as string for DB storage

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypts a previously encrypted string.

        Args:
            encrypted_text: The encrypted base64 string from the DB.

        Returns:
            The original plain-text string.

        Raises:
            ValueError: If decryption fails (wrong key or corrupted data).
        """
        if not encrypted_text:
            raise ValueError("Cannot decrypt empty string.")

        try:
            decrypted_bytes = self._fernet.decrypt(encrypted_text.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except InvalidToken:
            logger.error("Decryption failed — invalid token or wrong key.")
            raise ValueError("Failed to decrypt credential. Key mismatch or corrupted data.")

    def rotate_key(self, old_key: str, new_key: str, encrypted_text: str) -> str:
        """
        Re-encrypts data with a new key (for key rotation).
        Use when rotating the MASTER_ENCRYPTION_KEY.

        Args:
            old_key: The old Fernet key.
            new_key: The new Fernet key.
            encrypted_text: Data encrypted with the old key.

        Returns:
            Data encrypted with the new key.
        """
        old_fernet = Fernet(old_key.encode())
        new_fernet = Fernet(new_key.encode())
        plain_text = old_fernet.decrypt(encrypted_text.encode()).decode()
        return new_fernet.encrypt(plain_text.encode()).decode()


# ─── Singleton instance ────────────────────────────────────────────────────────
# Use this throughout the app — don't create new instances
credential_manager = CredentialManager()


# ─── Utility function to generate a new key ───────────────────────────────────
def generate_new_key() -> str:
    """
    Generates a new Fernet key.
    Run once, save to .env as MASTER_ENCRYPTION_KEY.

    Usage:
        python -c "from backend.services.credential_manager import generate_new_key; print(generate_new_key())"
    """
    return Fernet.generate_key().decode()

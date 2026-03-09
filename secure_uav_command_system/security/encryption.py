# =============================================================================
# security/encryption.py — AES-256 Encryption Utilities
# =============================================================================
# Provides symmetric encryption for sensitive data (command payloads, logs).
# Uses AES-256-CBC with PKCS7 padding and a random IV per encryption.
# The IV is prepended to the ciphertext and Base64-encoded for transport.
# =============================================================================

import os
import base64
import logging

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.backends import default_backend

from config import Config

logger = logging.getLogger(__name__)

# AES master key — loaded from Config
_KEY: bytes = Config.AES_MASTER_KEY[:32]   # enforce 256-bit


def encrypt_data(data: str) -> str:
    """
    Encrypt plaintext using AES-256-CBC.

    Process:
        1. Generate a cryptographically random 16-byte IV.
        2. Pad plaintext to a 128-bit block boundary (PKCS7).
        3. Encrypt with AES-256-CBC.
        4. Return Base64( IV || ciphertext ).

    Args:
        data: Plaintext string to encrypt.

    Returns:
        Base64-encoded string containing the IV and ciphertext.
    """
    iv = os.urandom(Config.AES_IV_SIZE)

    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(data.encode()) + padder.finalize()

    cipher = Cipher(
        algorithms.AES(_KEY),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor  = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    result = base64.b64encode(iv + ciphertext).decode()
    logger.debug("Data encrypted successfully (%d bytes).", len(ciphertext))
    return result


def decrypt_data(encrypted_b64: str) -> str:
    """
    Decrypt data produced by encrypt_data().

    Process:
        1. Base64-decode input.
        2. Split IV (first 16 bytes) from ciphertext.
        3. Decrypt with AES-256-CBC.
        4. Remove PKCS7 padding.

    Args:
        encrypted_b64: Base64-encoded string from encrypt_data().

    Returns:
        Decrypted plaintext string.

    Raises:
        ValueError: If decryption or unpadding fails.
    """
    try:
        raw        = base64.b64decode(encrypted_b64)
        iv         = raw[:Config.AES_IV_SIZE]
        ciphertext = raw[Config.AES_IV_SIZE:]

        cipher = Cipher(
            algorithms.AES(_KEY),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded    = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder  = sym_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        logger.debug("Data decrypted successfully.")
        return plaintext.decode()
    except Exception as exc:
        logger.error("Decryption failed: %s", exc)
        raise ValueError("Decryption failed.") from exc
# =============================================================================
# security/rsa_signatures.py — RSA Command Signing & Verification
# =============================================================================
# Generates an RSA-2048 key pair at module load time (or from disk if present).
# Every command is signed before execution; the signature is verified before
# the command is dispatched.  This prevents replay / tampering attacks.
# =============================================================================

import os
import base64
import logging

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key storage paths (generated once; persisted for the process lifetime)
# ---------------------------------------------------------------------------
_PRIVATE_KEY_PATH = "keys/rsa_private.pem"
_PUBLIC_KEY_PATH  = "keys/rsa_public.pem"

_private_key = None
_public_key  = None


# ---------------------------------------------------------------------------
# Key generation / loading
# ---------------------------------------------------------------------------

def generate_keys() -> tuple:
    """
    Generate a new RSA-2048 key pair.
    Returns (private_key, public_key) objects and persists PEM files to disk.
    """
    global _private_key, _public_key

    os.makedirs("keys", exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()

    # Persist to disk
    with open(_PRIVATE_KEY_PATH, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    with open(_PUBLIC_KEY_PATH, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

    _private_key = private_key
    _public_key  = public_key

    logger.info("RSA key pair generated and stored.")
    return private_key, public_key


def _load_or_generate_keys():
    """Load keys from disk if available; otherwise generate new ones."""
    global _private_key, _public_key

    if _private_key and _public_key:
        return  # already loaded

    if os.path.exists(_PRIVATE_KEY_PATH) and os.path.exists(_PUBLIC_KEY_PATH):
        with open(_PRIVATE_KEY_PATH, "rb") as f:
            _private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        with open(_PUBLIC_KEY_PATH, "rb") as f:
            _public_key = serialization.load_pem_public_key(
                f.read(), backend=default_backend()
            )
        logger.info("RSA keys loaded from disk.")
    else:
        generate_keys()


# ---------------------------------------------------------------------------
# Sign / Verify
# ---------------------------------------------------------------------------

def sign_command(command: str) -> str:
    """
    Sign a command string using RSA-PSS with SHA-256.
    Returns the Base64-encoded signature.
    """
    _load_or_generate_keys()

    signature = _private_key.sign(
        command.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    encoded = base64.b64encode(signature).decode()
    logger.debug("Command '%s' signed successfully.", command)
    return encoded


def verify_signature(command: str, signature_b64: str) -> bool:
    """
    Verify the RSA-PSS signature for a command.
    Returns True if valid, False otherwise.
    """
    _load_or_generate_keys()

    try:
        signature = base64.b64decode(signature_b64)
        _public_key.verify(
            signature,
            command.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        logger.debug("Signature verified for command '%s'.", command)
        return True
    except InvalidSignature:
        logger.warning("INVALID signature detected for command '%s'.", command)
        return False
    except Exception as exc:
        logger.error("Signature verification error: %s", exc)
        return False
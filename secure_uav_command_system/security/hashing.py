# =============================================================================
# security/hashing.py — bcrypt Password Hashing
# =============================================================================
# Wraps bcrypt for safe, adaptive password storage.
# Work factor (rounds) is configurable; default is 12.
# =============================================================================

import logging
import bcrypt

logger = logging.getLogger(__name__)

_BCRYPT_ROUNDS = 12   # increase for higher security at the cost of latency


def hash_password(password: str) -> str:
    """
    Hash a plaintext password with bcrypt.

    Args:
        password: Plaintext password string.

    Returns:
        bcrypt hash as a UTF-8 string (includes algorithm, rounds, and salt).
    """
    salt   = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode(), salt)
    logger.debug("Password hashed successfully.")
    return hashed.decode()


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    Args:
        password: Plaintext password to check.
        hashed:   Stored bcrypt hash string.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        result = bcrypt.checkpw(password.encode(), hashed.encode())
        if result:
            logger.debug("Password verification succeeded.")
        else:
            logger.warning("Password verification failed.")
        return result
    except Exception as exc:
        logger.error("Error during password verification: %s", exc)
        return False
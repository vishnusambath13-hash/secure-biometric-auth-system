# =============================================================================
# auth/login_auth.py — Authentication (Password + Face)
# =============================================================================

import logging

from database.db_manager import get_db_connection
from security.hashing import verify_password
from auth.biometric_auth import verify_operator_face, operator_face_registered

logger = logging.getLogger(__name__)


def authenticate_user(username: str, password: str) -> bool:
    """
    Authenticate an operator using password + facial verification.

    Workflow:
        1. Validate username/password.
        2. Verify registered face via webcam.
        3. Grant access to dashboard.

    Returns:
        True  — authentication successful
        False — authentication failed
    """

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT password_hash FROM users WHERE username = %s AND active = 1",
            (username,)
        )

        row = cursor.fetchone()

        if not row:
            logger.warning("AUTH FAILED — unknown user '%s'", username)
            return False

        # ── PASSWORD VERIFICATION ───────────────────────────────────────────
        if not verify_password(password, row["password_hash"]):

            logger.warning("AUTH FAILED — incorrect password for '%s'", username)
            return False

        logger.info("Password verified for user '%s'", username)

        # ── FACE VERIFICATION ───────────────────────────────────────────────
        if not operator_face_registered():

            logger.error(
                "AUTH FAILED — no registered face found. Run enroll_face.py first."
            )

            return False

        logger.info("Starting facial verification for '%s'", username)

        face_ok = verify_operator_face()

        if not face_ok:

            logger.warning(
                "AUTH FAILED — facial verification mismatch for '%s'",
                username
            )

            return False

        logger.info(
            "AUTH SUCCESS — password + face verified for '%s'",
            username
        )

        return True

    except Exception as exc:

        logger.error("Authentication error: %s", exc)
        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
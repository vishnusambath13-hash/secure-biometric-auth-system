# =============================================================================
# config.py — Application Configuration
# Secure Biometric Authentication and Command Authorization System
# =============================================================================
# Central configuration file for all environment settings.
# Biometric configuration stubs are included for future integration.
# =============================================================================

import os

class Config:
    # -------------------------------------------------------------------------
    # Flask
    # -------------------------------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_supersecretkey")
    DEBUG = os.environ.get("FLASK_DEBUG", "False") == "True"

    # -------------------------------------------------------------------------
    # Database — MySQL
    # -------------------------------------------------------------------------
    DB_HOST = "localhost"
    DB_PORT = 3306
    DB_USER = "root"
    DB_PASSWORD = "TheDarkKnight@2005"
    DB_NAME = "secure_uav"

    # -------------------------------------------------------------------------
    # Cryptography
    # -------------------------------------------------------------------------
    RSA_KEY_SIZE   = 2048          # bits
    AES_KEY_SIZE   = 32            # bytes → AES-256
    AES_IV_SIZE    = 16            # bytes

    # AES master key — store securely (env var / secrets manager in production)
    AES_MASTER_KEY = os.environ.get(
        "AES_MASTER_KEY",
        "01234567890123456789012345678901"   # 32-byte placeholder
    ).encode()

    # -------------------------------------------------------------------------
    # Session
    # -------------------------------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # -------------------------------------------------------------------------
    # Biometrics — FUTURE INTEGRATION
    # -------------------------------------------------------------------------
    # Uncomment and configure when biometric modules are ready.
    #
    # BIOMETRIC_FACE_THRESHOLD    = 0.6     # DeepFace distance threshold
    # BIOMETRIC_VOICE_MODEL       = "path/to/voice_model"
    # BIOMETRIC_GESTURE_ENABLED   = False
    # BIOMETRIC_CAMERA_INDEX      = 0       # OpenCV camera index
    # BIOMETRIC_MEDIAPIPE_CONF    = 0.7     # MediaPipe confidence
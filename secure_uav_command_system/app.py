# =============================================================================
# app.py — Flask Application Entry Point
# Secure Biometric Authentication and Command Authorization System
# =============================================================================
# Routes:
#   GET  /                      → Login page
#   POST /login                 → Authenticate and start session (MFA)
#   GET  /dashboard             → Command console (requires session)
#   POST /execute_command       → Secure keyboard/button command execution
#   POST /gesture-command       → Gesture command (via microservice on :6000)
#   POST /api/gesture-command   → External gesture microservice API endpoint
#   POST /logout                → Destroy session
#
# Security pipeline (all command routes):
#   Input → normalise → whitelist → RSA sign → RSA verify → execute → log
# =============================================================================

import logging
from functools import wraps
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, jsonify
)
import requests as http_client   # used by gesture_command_route to call microservice

from config import Config
from auth.login_auth import authenticate_user
from security.rsa_signatures import sign_command, verify_signature
from commands.command_handler import execute_command, COMMAND_MAP
from commands.command_logger import log_command
from auth.voice_auth import verify_operator_voice
# detect_gesture_command() removed — gesture detection now handled by
# the dedicated microservice at GESTURE_SERVICE_URL (see below).

# ---------------------------------------------------------------------------
# Logging setup — writes to console and uav_system.log
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("uav_system.log"),
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config.from_object(Config)

# ---------------------------------------------------------------------------
# Initialise DB schema (non-fatal if DB is not available during dev)
# ---------------------------------------------------------------------------
try:
    from database.db_manager import init_db
    init_db()
except Exception as _exc:
    logger.warning("DB init skipped (not available in this environment): %s", _exc)


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def _check_password_only(username: str, password: str) -> bool:
    """
    Lightweight Factor-1-only check used by the login route to distinguish
    a wrong password (generic 401 message) from a face failure (HTTP 403).

    Does NOT open the webcam.  Mirrors the DB query in authenticate_user()
    but calls verify_password() directly without proceeding to biometrics.

    Returns:
        True  — username exists and password matches the stored bcrypt hash.
        False — user not found, inactive, wrong password, or DB error.
    """
    from database.db_manager import get_db_connection
    from security.hashing import verify_password as _verify

    conn = cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT password_hash FROM users WHERE username = %s AND active = 1",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        return _verify(password, row["password_hash"])
    except Exception as exc:
        logger.error("_check_password_only error: %s", exc)
        return False
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ---------------------------------------------------------------------------
# Shared security pipeline
# ---------------------------------------------------------------------------

def _run_secure_pipeline(command_name: str, operator: str, source: str):

    # ── VOICE AUTHORIZATION BEFORE COMMAND EXECUTION ──────────────────────
    # ── VOICE AUTHORIZATION (ONLY FOR BUTTON COMMANDS) ─────────────────────

    if source == "keyboard":

        logger.info("[SECURITY] Voice authorization required for command execution.")

        if not verify_operator_voice():

            logger.warning(
                "[SECURITY] Voice authorization failed for operator '%s'.",
                operator
            )

            return {
                "status": "denied",
                "result": "Voice authorization failed."
            }, 403

        logger.info("[SECURITY] Voice authorization passed.")

    # ── 1. COMMAND WHITELIST ───────────────────────────────────────────────
    if command_name not in COMMAND_MAP:

        logger.warning(
            "[%s] Unknown command '%s' from '%s'",
            source.upper(),
            command_name,
            operator
        )

        return {"status": "error", "result": "Unknown command."}, 400

    # ── 2. RSA SIGN ────────────────────────────────────────────────────────
    try:

        signature = sign_command(command_name)

    except Exception as exc:

        logger.error("[%s] Signing failed: %s", source.upper(), exc)

        return {
            "status": "error",
            "result": "Cryptographic signing failed."
        }, 500

    # ── 3. RSA VERIFY ──────────────────────────────────────────────────────
    if not verify_signature(command_name, signature):

        logger.error(
            "[%s] Signature verification FAILED for '%s'",
            source.upper(),
            command_name
        )

        return {
            "status": "error",
            "result": "Signature verification failed."
        }, 403

    # ── 4. EXECUTE COMMAND ─────────────────────────────────────────────────
    try:

        result = execute_command(command_name)

    except Exception as exc:

        logger.error("[%s] Command execution error: %s", source.upper(), exc)

        return {
            "status": "error",
            "result": "Command execution failed."
        }, 500

    # ── 5. LOG COMMAND ─────────────────────────────────────────────────────
    try:

        log_command(
            command_name=command_name,
            operator=operator,
            result=result,
            signature=signature
        )

    except Exception as exc:

        logger.warning(
            "[%s] Command executed but logging failed: %s",
            source.upper(),
            exc
        )

    return {
        "status": "success",
        "command": command_name,
        "result": result,
        "operator": operator,
        "source": source,
        "signature": signature[:16] + "…"
    }, 200


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Redirect root to login page."""
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    """
    GET  → Render login form.
    POST → Two-factor authentication:
               Factor 1 — bcrypt password check.
               Factor 2 — DeepFace facial verification (webcam).
           On full MFA success: create session, redirect to /dashboard.
           On face verification failure: HTTP 403 with specific error message.
    """
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return render_template("login.html", error="Credentials required.")

    # ── Pre-check: password only (Factor 1), before opening the webcam ───────
    # authenticate_user() now runs BOTH factors internally.
    # To surface a distinct HTTP 403 for face failure (vs wrong password) we
    # call a lightweight password-only check first, then delegate the full MFA.
    from auth.biometric_auth import operator_face_registered
    from security.hashing import verify_password
    from database.db_manager import get_db_connection

    password_valid = _check_password_only(username, password)

    if not password_valid:
        logger.warning("Failed login attempt (bad password) for user '%s'.", username)
        return render_template(
            "login.html",
            error="ACCESS DENIED — Invalid credentials."
        )

    # Password passed — now run the full MFA pipeline (face verification)
    mfa_ok = authenticate_user(username, password)

    if mfa_ok:
        session["username"] = username
        session.permanent    = False
        logger.info("MFA complete — session created for user '%s'.", username)
        return redirect(url_for("dashboard"))

    # Distinguish face failure from password failure for the operator
    logger.warning("Face verification failed for user '%s'.", username)
    return render_template(
        "login.html",
        error="Face verification failed — access denied."
    ), 403


@app.route("/dashboard")
@login_required
def dashboard():
    """Render the main command console (requires active session)."""
    return render_template("dashboard.html", username=session["username"])


@app.route("/execute_command", methods=["POST"])
@login_required
def execute_command_route():
    """
    Keyboard / button command execution endpoint.

    Expects JSON body: { "command": "<command_name>" }

    Delegates to _run_secure_pipeline() which runs:
        whitelist → RSA sign → RSA verify → execute → log

    Returns JSON: { "status": "success"|"error", "result": "...", ... }
    """
    data         = request.get_json(force=True, silent=True) or {}
    command_name = data.get("command", "").strip().lower()

    body, status = _run_secure_pipeline(
        command_name=command_name,
        operator=session["username"],
        source="keyboard",
    )
    return jsonify(body), status


# ---------------------------------------------------------------------------
# Gesture-based command execution
# ---------------------------------------------------------------------------

# Normalisation table: gesture detection returns UPPER_SNAKE_CASE,
# COMMAND_MAP keys use lower_snake_case.
_GESTURE_TO_COMMAND: dict[str, str] = {
    "START_RECON":   "start_recon",
    "DEPLOY_DRONE":  "deploy_drone",
    "RETURN_BASE":   "return_base",
    "SYSTEM_STATUS": "system_status",
    "ABORT_MISSION": "abort_mission",
}

# URL of the standalone gesture detection microservice (gesture_server.py)
GESTURE_SERVICE_URL = "http://127.0.0.1:6000/detect"
# Timeout in seconds to wait for the microservice to return a gesture.
# The microservice blocks until the operator confirms a gesture (~2 s hold),
# so this must be generous enough to cover the full detection window.
GESTURE_SERVICE_TIMEOUT = 60


@app.route("/gesture-command", methods=["POST"])
@login_required
def gesture_command_route():
    """
    Gesture-based command execution endpoint (microservice-backed).

    Workflow:
        1. POST to the gesture microservice at GESTURE_SERVICE_URL.
           The microservice opens the webcam, waits for a stable hand
           gesture (~2 s hold), then returns JSON: { "gesture": "..." }
           or { "gesture": null } if the operator cancelled.
        2. Handle unreachable service, timeout, and malformed responses
           with specific error messages and log entries.
        3. Handle null gesture (cancellation) with a clean 200 response.
        4. Normalise the UPPER_SNAKE gesture string to the lowercase key
           expected by COMMAND_MAP and the RSA pipeline.
        5. Pass through _run_secure_pipeline():
               whitelist → RSA sign → RSA verify → execute → log
        6. Enrich the success response with the original gesture label.

    Gesture → Command mapping:
        START_RECON   →  start_recon
        DEPLOY_DRONE  →  deploy_drone
        RETURN_BASE   →  return_base
        SYSTEM_STATUS →  system_status
        ABORT_MISSION →  abort_mission

    Returns JSON:
        200  { "status": "executed",  "command": "start_recon",
               "gesture": "START_RECON", "result": "...", ... }
        200  { "status": "cancelled", "result": "No gesture detected." }
        400  { "status": "error",     "result": "Unrecognised gesture: '...'." }
        502  { "status": "error",     "result": "Gesture service unreachable." }
        504  { "status": "error",     "result": "Gesture service timed out." }
        500  { "status": "error",     "result": "Unexpected error ..." }
    """
    operator = session["username"]

    logger.info(
        "[GESTURE] Operator '%s' requested gesture detection via microservice.",
        operator,
    )

    # ── 1. Call gesture detection microservice ───────────────────────────────
    try:
        svc_response = http_client.post(
            GESTURE_SERVICE_URL,
            timeout=GESTURE_SERVICE_TIMEOUT,
        )
        svc_response.raise_for_status()
        payload = svc_response.json()

    except http_client.exceptions.ConnectionError:
        logger.error(
            "[GESTURE] Microservice unreachable at '%s'. "
            "Ensure gesture_server.py is running.",
            GESTURE_SERVICE_URL,
        )
        return jsonify({
            "status": "error",
            "result": (
                "Gesture service unreachable. "
                "Start gesture_server.py and try again."
            ),
        }), 502

    except http_client.exceptions.Timeout:
        logger.error(
            "[GESTURE] Microservice at '%s' did not respond within %ds.",
            GESTURE_SERVICE_URL, GESTURE_SERVICE_TIMEOUT,
        )
        return jsonify({
            "status": "error",
            "result": "Gesture service timed out waiting for a gesture.",
        }), 504

    except http_client.exceptions.HTTPError as exc:
        logger.error(
            "[GESTURE] Microservice returned HTTP error: %s", exc,
        )
        return jsonify({
            "status": "error",
            "result": f"Gesture service error: {exc}",
        }), 502

    except Exception as exc:
        logger.error("[GESTURE] Unexpected error contacting microservice: %s", exc)
        return jsonify({
            "status": "error",
            "result": "Unexpected error communicating with gesture service.",
        }), 500

    # ── 2. Extract gesture string from microservice payload ──────────────────
    gesture_raw = payload.get("gesture")   # None when operator pressed Q

    # ── 3. Handle cancellation (operator pressed Q in the camera window) ─────
    if gesture_raw is None:
        logger.info(
            "[GESTURE] Detection cancelled by operator '%s' (microservice returned null).",
            operator,
        )
        return jsonify({
            "status": "cancelled",
            "result": "No gesture detected — detection was cancelled.",
        }), 200

    logger.info(
        "[GESTURE] Microservice returned gesture '%s' for operator '%s'.",
        gesture_raw, operator,
    )

    # ── 4. Normalise gesture string to COMMAND_MAP key ───────────────────────
    command_name = _GESTURE_TO_COMMAND.get(gesture_raw.upper())

    if not command_name:
        logger.warning(
            "[GESTURE] Unrecognised gesture '%s' from microservice "
            "(operator: '%s'). Valid gestures: %s.",
            gesture_raw, operator, ", ".join(_GESTURE_TO_COMMAND.keys()),
        )
        return jsonify({
            "status": "error",
            "result": (
                f"Unrecognised gesture: '{gesture_raw}'. "
                f"Valid values: {', '.join(_GESTURE_TO_COMMAND.keys())}."
            ),
        }), 400

    # ── 5. RSA sign → verify → execute → log (shared pipeline) ──────────────
    body, status = _run_secure_pipeline(
        command_name=command_name,
        operator=operator,
        source="gesture",
    )

    # ── 6. Enrich the success response with the original gesture label ────────
    if body.get("status") == "success":
        body["gesture"] = gesture_raw
        body["status"]  = "executed"

    return jsonify(body), status


# ---------------------------------------------------------------------------
# External gesture microservice API endpoint
# ---------------------------------------------------------------------------

@app.route("/api/gesture-command", methods=["POST"])
@login_required
def api_gesture_command_route():
    """
    POST /api/gesture-command — External gesture microservice endpoint.

    Accepts a pre-recognised gesture string from an external gesture detection
    service (e.g. a dedicated MediaPipe microservice, a hardware glove, or
    any other gesture input system).  Does NOT open the webcam or call
    detect_gesture_command() — gesture recognition is the caller's concern.

    Request body (JSON):
        { "gesture": "START_RECON" }

    Workflow:
        1. Enforce operator session via @login_required.
        2. Extract and validate the 'gesture' field from the JSON payload.
        3. Normalise the UPPER_SNAKE gesture string to the lowercase
           COMMAND_MAP key using the shared _GESTURE_TO_COMMAND table.
        4. Pass into _run_secure_pipeline() with source="gesture_service":
               whitelist → RSA sign → RSA verify → execute → log
        5. Enrich the response body with the original gesture label.
        6. Return JSON.

    Gesture → Command mapping:
        START_RECON   →  start_recon
        DEPLOY_DRONE  →  deploy_drone
        RETURN_BASE   →  return_base
        SYSTEM_STATUS →  system_status
        ABORT_MISSION →  abort_mission

    Responses:
        200  { "status": "executed", "command": "start_recon",
               "gesture": "START_RECON", "result": "...",
               "operator": "...", "source": "gesture_service",
               "signature": "…" }
        400  { "status": "error", "result": "Missing 'gesture' field." }
        400  { "status": "error", "result": "Unrecognised gesture: '...'." }
        401  → Redirect to /login  (session missing — @login_required)
        400/403/500  propagated from _run_secure_pipeline()
    """
    operator = session["username"]

    # ── 1. Parse JSON payload ────────────────────────────────────────────────
    payload = request.get_json(force=True, silent=True) or {}

    gesture_raw = payload.get("gesture", "").strip()

    if not gesture_raw:
        logger.warning(
            "[GESTURE_SERVICE] Missing 'gesture' field in request from operator '%s'.",
            operator,
        )
        return jsonify({
            "status": "error",
            "result": "Missing 'gesture' field in request body.",
        }), 400

    logger.info(
        "[GESTURE_SERVICE] External gesture received from operator '%s': '%s'.",
        operator,
        gesture_raw,
    )

    # ── 2. Normalise gesture string → COMMAND_MAP key ────────────────────────
    command_name = _GESTURE_TO_COMMAND.get(gesture_raw.upper())

    if not command_name:
        logger.warning(
            "[GESTURE_SERVICE] Unrecognised gesture '%s' from operator '%s'. "
            "Valid gestures: %s.",
            gesture_raw,
            operator,
            ", ".join(_GESTURE_TO_COMMAND.keys()),
        )
        return jsonify({
            "status": "error",
            "result": (
                f"Unrecognised gesture: '{gesture_raw}'. "
                f"Valid values: {', '.join(_GESTURE_TO_COMMAND.keys())}."
            ),
        }), 400

    logger.info(
        "[GESTURE_SERVICE] Gesture '%s' mapped to command '%s' for operator '%s'.",
        gesture_raw,
        command_name,
        operator,
    )

    # ── 3. Secure pipeline: whitelist → RSA sign → verify → execute → log ────
    body, status = _run_secure_pipeline(
        command_name=command_name,
        operator=operator,
        source="gesture_service",   # distinct source label in audit log
    )

    # ── 4. Enrich success response with the original gesture label ────────────
    if body.get("status") == "success":
        body["gesture"] = gesture_raw
        body["status"]  = "executed"

        logger.info(
            "[GESTURE_SERVICE] Command '%s' executed successfully for operator '%s' "
            "(gesture: '%s').",
            command_name,
            operator,
            gesture_raw,
        )

    return jsonify(body), status


@app.route("/logout", methods=["POST"])
def logout():
    """Invalidate the current session."""
    username = session.pop("username", "unknown")
    logger.info("Session terminated for user '%s'.", username)
    return redirect(url_for("login_page"))


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
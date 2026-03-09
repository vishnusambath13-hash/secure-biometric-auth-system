# =============================================================================
# biometrics/camera_capture.py — Webcam Face Capture
# Secure Biometric Authentication and Command Authorization System
# =============================================================================
# Captures a single frame from the operator's webcam for biometric
# verification.  Designed to be called from Flask routes before a session
# is granted or before high-priority commands are authorized.
#
# Integration point in auth/login_auth.py:
#   from biometrics.camera_capture import capture_face_image
#   frame = capture_face_image()
#   if frame is None:
#       return False   # operator cancelled
#   # pass frame to DeepFace / face-recognition pipeline
#
# Dependencies:
#   pip install opencv-python
# =============================================================================

import logging
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key codes
# ---------------------------------------------------------------------------
_KEY_SPACE = 32   # capture
_KEY_ESC   = 27   # cancel

# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------
_WINDOW_TITLE  = "Operator Face Scan"
_OVERLAY_COLOR = (0, 245, 180)    # cyan-green — matches HUD palette (BGR)
_WARN_COLOR    = (0, 60, 255)     # red (BGR)
_FONT          = cv2.FONT_HERSHEY_SIMPLEX


def capture_face_image() -> np.ndarray | None:

    face_detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = _open_camera()

    if cap is None:
        return None

    captured_frame = None

    try:

        logger.info("Face capture window opened — awaiting operator input.")

        while True:

            ret, frame = cap.read()

            if not ret:
                break

            frame = cv2.flip(frame,1)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = face_detector.detectMultiScale(gray,1.3,5)

            h,w = frame.shape[:2]

            box_w = int(w * 0.35)
            box_h = int(h * 0.45)

            x1 = w//2 - box_w//2
            y1 = h//2 - box_h//2
            x2 = w//2 + box_w//2
            y2 = h//2 + box_h//2

            cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,180),2)

            cv2.putText(
                frame,
                "ALIGN FACE INSIDE FRAME",
                (10,30),
                _FONT,
                0.6,
                (0,255,180),
                2
            )

            for (fx,fy,fw,fh) in faces:

                cx = fx + fw//2
                cy = fy + fh//2

                cv2.rectangle(frame,(fx,fy),(fx+fw,fy+fh),(255,0,0),2)

                if x1 < cx < x2 and y1 < cy < y2:

                    cv2.putText(
                        frame,
                        "FACE LOCKED - PRESS SPACE",
                        (10,60),
                        _FONT,
                        0.6,
                        (0,255,0),
                        2
                    )

            cv2.imshow(_WINDOW_TITLE,frame)

            key = cv2.waitKey(1) & 0xFF

            if key == _KEY_SPACE:

                captured_frame = frame.copy()
                logger.info("Face frame captured.")
                break

            if key == _KEY_ESC:

                logger.warning("Face capture cancelled.")
                break

    finally:

        _release(cap)

    return captured_frame


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _open_camera() -> cv2.VideoCapture | None:
    """
    Open VideoCapture(0) and validate that it is readable.

    Returns:
        cv2.VideoCapture on success, None on failure.
    """
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error(
            "Could not open webcam (index 0). "
            "Check that a camera is connected and not in use by another process."
        )
        return None

    # Prefer a small, fast resolution for low-latency preview
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    logger.debug("Webcam opened successfully.")
    return cap


def _draw_overlay(frame: np.ndarray) -> None:
    """
    Draw a minimal HUD-style annotation on the live preview frame.
    Mutates *frame* in place.
    """
    h, w = frame.shape[:2]

    # ── Targeting reticle (centre) ──────────────────────────────────────────
    cx, cy  = w // 2, h // 2
    arm_len = 30
    gap     = 10
    thickness = 2

    # Horizontal arms
    cv2.line(frame, (cx - arm_len - gap, cy), (cx - gap, cy), _OVERLAY_COLOR, thickness)
    cv2.line(frame, (cx + gap, cy), (cx + arm_len + gap, cy), _OVERLAY_COLOR, thickness)
    # Vertical arms
    cv2.line(frame, (cx, cy - arm_len - gap), (cx, cy - gap), _OVERLAY_COLOR, thickness)
    cv2.line(frame, (cx, cy + gap), (cx, cy + arm_len + gap), _OVERLAY_COLOR, thickness)

    # ── Corner bracket marks ────────────────────────────────────────────────
    margin  = 16
    bracket = 20

    corners = [
        # top-left
        [(margin, margin + bracket), (margin, margin), (margin + bracket, margin)],
        # top-right
        [(w - margin - bracket, margin), (w - margin, margin), (w - margin, margin + bracket)],
        # bottom-left
        [(margin, h - margin - bracket), (margin, h - margin), (margin + bracket, h - margin)],
        # bottom-right
        [(w - margin - bracket, h - margin), (w - margin, h - margin), (w - margin, h - margin - bracket)],
    ]
    for pts in corners:
        for i in range(len(pts) - 1):
            cv2.line(frame, pts[i], pts[i + 1], _OVERLAY_COLOR, thickness)

    # ── Instruction text ────────────────────────────────────────────────────
    _put_text(frame, "BIOMETRIC SCAN ACTIVE",    (10, 22),      scale=0.45, color=_OVERLAY_COLOR)
    _put_text(frame, "SPACE: CAPTURE  |  ESC: CANCEL", (10, h - 12), scale=0.38, color=_OVERLAY_COLOR)


def _put_text(
    frame:  np.ndarray,
    text:   str,
    origin: tuple[int, int],
    scale:  float = 0.45,
    color:  tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
) -> None:
    """Helper — draw text with a dark drop-shadow for legibility."""
    ox, oy = origin
    # Shadow
    cv2.putText(frame, text, (ox + 1, oy + 1), _FONT, scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
    # Foreground
    cv2.putText(frame, text, (ox, oy), _FONT, scale, color, thickness, cv2.LINE_AA)


def _release(cap: cv2.VideoCapture) -> None:
    """Safely release the camera and destroy the preview window."""
    try:
        cap.release()
    except Exception as exc:
        logger.warning("Error releasing camera: %s", exc)

    try:
        cv2.destroyWindow(_WINDOW_TITLE)
        cv2.waitKey(1)   # pump the event loop so the window actually closes
    except Exception as exc:
        logger.warning("Error destroying window: %s", exc)

    logger.debug("Camera released and window destroyed.")
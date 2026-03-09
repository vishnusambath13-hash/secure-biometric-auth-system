# =============================================================================
# gesture/gesture_detection.py — MediaPipe Hand Gesture → UAV Command
# Secure Biometric Authentication and Command Authorization System
# =============================================================================
# Maps hand gestures to UAV command strings using MediaPipe Hands.
# Intended as an optional tertiary input factor that can supplement or
# replace keyboard-driven command dispatch from the HUD console.
#
# Integration point in app.py (or a dedicated Flask route):
#
#   from gesture.gesture_detection import detect_gesture_command
#
#   @app.route("/gesture_command", methods=["POST"])
#   @login_required
#   def gesture_command_route():
#       command = detect_gesture_command()   # blocking — run in a thread
#       if command:
#           # feed into the same RSA-sign → verify → execute pipeline
#           signature = sign_command(command)
#           ...
#
# Gesture → Command map:
#   1 finger raised    →  START_RECON
#   2 fingers raised   →  DEPLOY_DRONE
#   3 fingers raised   →  RETURN_BASE
#   Open palm (5)      →  SYSTEM_STATUS
#   Closed fist (0)    →  ABORT_MISSION
#   Q key              →  quit (returns None)
#
# Dependencies:
#   pip install opencv-python mediapipe numpy
# =============================================================================

import logging
import numpy as np
import cv2
import mediapipe as mp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MediaPipe setup
# ---------------------------------------------------------------------------
_mp_hands    = mp.solutions.hands
_mp_drawing  = mp.solutions.drawing_utils
_mp_styles   = mp.solutions.drawing_styles

# ---------------------------------------------------------------------------
# Gesture → command mapping
# ---------------------------------------------------------------------------
_GESTURE_MAP: dict[int | str, str] = {
    0: "ABORT_MISSION",    # closed fist
    1: "START_RECON",
    2: "DEPLOY_DRONE",
    3: "RETURN_BASE",
    5: "SYSTEM_STATUS",    # open palm
}

# ---------------------------------------------------------------------------
# Display constants (BGR — HUD palette)
# ---------------------------------------------------------------------------
_COL_CYAN   = (255, 220,   0)   # BGR ≈ cyan
_COL_GREEN  = ( 60, 220,   0)
_COL_RED    = (  0,  40, 220)
_COL_AMBER  = (  0, 160, 255)
_COL_WHITE  = (220, 220, 220)
_COL_SHADOW = (  0,   0,   0)

_FONT         = cv2.FONT_HERSHEY_SIMPLEX
_WINDOW_TITLE = "UAV Gesture Command"

# How many consecutive frames a gesture must be stable before it is accepted.
_CONFIRM_FRAMES = 12


# =============================================================================
# Public API
# =============================================================================

def detect_gesture_command() -> str | None:
    """
    Open the webcam, track a single hand with MediaPipe, and return the
    UAV command string mapped to the first confidently-held gesture.

    Controls:
        Hold a gesture steady for ~12 frames → command accepted.
        Q key → quit without returning a command.

    Returns:
        str  — one of START_RECON, DEPLOY_DRONE, RETURN_BASE,
                       SYSTEM_STATUS, ABORT_MISSION.
        None — operator pressed Q or camera could not be opened.
    """
    cap = _open_camera()
    if cap is None:
        return None

    detected_command: str | None = None

    # Stability counter — gesture must persist for _CONFIRM_FRAMES frames
    stable_gesture:   str | None = None
    stable_count:     int        = 0

    with _mp_hands.Hands(
        static_image_mode       = False,
        max_num_hands           = 1,
        min_detection_confidence= 0.75,
        min_tracking_confidence = 0.65,
    ) as hands:

        logger.info("Gesture detection active — awaiting operator gesture.")

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.error("Camera feed lost during gesture detection.")
                break

            # Mirror for natural feel; convert BGR→RGB for MediaPipe
            frame_mirror = cv2.flip(frame, 1)
            rgb          = cv2.cvtColor(frame_mirror, cv2.COLOR_BGR2RGB)

            # Mark as not writeable to pass by reference (performance)
            rgb.flags.writeable = False
            results = hands.process(rgb)
            rgb.flags.writeable = True

            # Back to BGR for drawing
            display = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            current_command: str | None = None

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                handedness     = (
                    results.multi_handedness[0].classification[0].label
                    if results.multi_handedness else "Right"
                )

                # Draw MediaPipe skeleton
                _mp_drawing.draw_landmarks(
                    display,
                    hand_landmarks,
                    _mp_hands.HAND_CONNECTIONS,
                    _mp_styles.get_default_hand_landmarks_style(),
                    _mp_styles.get_default_hand_connections_style(),
                )

                # Count raised fingers
                finger_count  = _count_fingers(hand_landmarks, handedness)
                current_command = _GESTURE_MAP.get(finger_count)

                # Draw finger-count badge
                _draw_finger_badge(display, finger_count)

            # ── Stability check ──────────────────────────────────────────────
            if current_command and current_command == stable_gesture:
                stable_count += 1
            else:
                stable_gesture = current_command
                stable_count   = 1

            if stable_count >= _CONFIRM_FRAMES and stable_gesture:
                detected_command = stable_gesture
                logger.info(
                    "Gesture confirmed after %d frames: %s",
                    stable_count, detected_command,
                )
                break

            # ── HUD overlay ──────────────────────────────────────────────────
            _draw_hud(display, current_command, stable_gesture, stable_count)

            cv2.imshow(_WINDOW_TITLE, display)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                logger.warning("Gesture detection cancelled by operator (Q).")
                break

    _release(cap)
    return detected_command


# =============================================================================
# Finger counting
# =============================================================================

# Landmark indices for fingertips and their corresponding PIP joints
# Order: [thumb, index, middle, ring, pinky]
_FINGERTIP_IDS = [4,  8,  12, 16, 20]
_FINGER_PIP_IDS= [3,  6,  10, 14, 18]


def _count_fingers(landmarks, handedness: str) -> int:
    """
    Count the number of extended (raised) fingers.

    Thumb: compared horizontally (x-axis) because it moves laterally.
           Accounts for left vs right hand mirroring.
    Other fingers: compared vertically (y-axis); tip above PIP = extended.

    Args:
        landmarks:   MediaPipe NormalizedLandmarkList for one hand.
        handedness:  "Left" or "Right" as reported by MediaPipe
                     (on the *mirrored* frame this maps naturally).

    Returns:
        int in range 0–5.
    """
    lm = landmarks.landmark
    count = 0

    # ── Thumb (horizontal comparison) ───────────────────────────────────────
    tip_x = lm[_FINGERTIP_IDS[0]].x
    pip_x = lm[_FINGER_PIP_IDS[0]].x

    if handedness == "Right":
        if tip_x < pip_x:   # tip further left than knuckle → extended
            count += 1
    else:
        if tip_x > pip_x:   # mirror logic for left hand
            count += 1

    # ── Four fingers (vertical comparison) ──────────────────────────────────
    for i in range(1, 5):
        tip_y = lm[_FINGERTIP_IDS[i]].y
        pip_y = lm[_FINGER_PIP_IDS[i]].y
        if tip_y < pip_y:   # lower y = higher on screen = raised
            count += 1

    return count


# =============================================================================
# Drawing helpers
# =============================================================================

def _draw_hud(
    frame:          np.ndarray,
    current_cmd:    str | None,
    stable_cmd:     str | None,
    stable_count:   int,
) -> None:
    """Draw the full HUD overlay: title, gesture map legend, progress bar."""
    h, w = frame.shape[:2]

    # ── Title bar ────────────────────────────────────────────────────────────
    cv2.rectangle(frame, (0, 0), (w, 36), (10, 18, 26), -1)
    _put_text(frame, "UAV GESTURE COMMAND INTERFACE",
              (10, 24), scale=0.52, color=_COL_CYAN, thickness=1)
    _put_text(frame, "Q: QUIT",
              (w - 80, 24), scale=0.38, color=_COL_AMBER, thickness=1)

    # ── Corner brackets ───────────────────────────────────────────────────────
    _draw_brackets(frame, margin=8, size=18, color=_COL_CYAN)

    # ── Legend panel (bottom-left) ───────────────────────────────────────────
    legend = [
        ("1 finger",    "START_RECON"),
        ("2 fingers",   "DEPLOY_DRONE"),
        ("3 fingers",   "RETURN_BASE"),
        ("Open palm",   "SYSTEM_STATUS"),
        ("Fist",        "ABORT_MISSION"),
    ]
    panel_x, panel_y = 8, h - (len(legend) * 22 + 16)
    cv2.rectangle(frame,
                  (panel_x - 4, panel_y - 6),
                  (210, h - 6),
                  (8, 14, 22, 180), -1)

    for i, (gesture_label, cmd_label) in enumerate(legend):
        y        = panel_y + i * 22
        is_active = (cmd_label == current_cmd)
        col       = _COL_GREEN if is_active else _COL_WHITE
        prefix    = "▸ " if is_active else "  "
        _put_text(frame, f"{prefix}{gesture_label:<12} {cmd_label}",
                  (panel_x, y), scale=0.36, color=col, thickness=1)

    # ── Detected command display ─────────────────────────────────────────────
    if current_cmd:
        cmd_col = _COL_RED if current_cmd == "ABORT_MISSION" else _COL_GREEN
        _put_text(frame, current_cmd,
                  (w // 2 - 120, h - 52), scale=0.72, color=cmd_col, thickness=2)

    # ── Stability progress bar ───────────────────────────────────────────────
    if stable_cmd and stable_count > 1:
        bar_w    = w - 20
        bar_h    = 6
        bar_y    = h - 14
        progress = min(stable_count / _CONFIRM_FRAMES, 1.0)
        filled   = int(bar_w * progress)

        cv2.rectangle(frame, (10, bar_y), (10 + bar_w, bar_y + bar_h),
                      (30, 30, 30), -1)
        bar_col = _COL_RED if stable_cmd == "ABORT_MISSION" else _COL_CYAN
        cv2.rectangle(frame, (10, bar_y), (10 + filled, bar_y + bar_h),
                      bar_col, -1)
        _put_text(frame, "CONFIRMING …",
                  (10, bar_y - 6), scale=0.35, color=_COL_AMBER, thickness=1)


def _draw_finger_badge(frame: np.ndarray, count: int) -> None:
    """Draw a large finger-count number in the top-right corner."""
    h, w = frame.shape[:2]
    label = str(count)
    (tw, th), _ = cv2.getTextSize(label, _FONT, 2.2, 3)
    x = w - tw - 20
    y = 80
    # Shadow
    cv2.putText(frame, label, (x + 2, y + 2), _FONT, 2.2, _COL_SHADOW, 5, cv2.LINE_AA)
    # Foreground
    col = _COL_RED if count == 0 else _COL_GREEN
    cv2.putText(frame, label, (x, y), _FONT, 2.2, col, 3, cv2.LINE_AA)


def _draw_brackets(
    frame:  np.ndarray,
    margin: int,
    size:   int,
    color:  tuple[int, int, int],
    t:      int = 2,
) -> None:
    """Draw four corner bracket marks on the frame."""
    h, w = frame.shape[:2]
    m, s = margin, size
    corners = [
        # top-left
        [(m, m + s), (m, m), (m + s, m)],
        # top-right
        [(w - m - s, m), (w - m, m), (w - m, m + s)],
        # bottom-left
        [(m, h - m - s), (m, h - m), (m + s, h - m)],
        # bottom-right
        [(w - m - s, h - m), (w - m, h - m), (w - m, h - m - s)],
    ]
    for pts in corners:
        for i in range(len(pts) - 1):
            cv2.line(frame, pts[i], pts[i + 1], color, t, cv2.LINE_AA)


def _put_text(
    frame:     np.ndarray,
    text:      str,
    origin:    tuple[int, int],
    scale:     float = 0.45,
    color:     tuple[int, int, int] = _COL_WHITE,
    thickness: int = 1,
) -> None:
    """Draw text with a dark drop-shadow for legibility over any background."""
    ox, oy = origin
    cv2.putText(frame, text, (ox + 1, oy + 1),
                _FONT, scale, _COL_SHADOW, thickness + 1, cv2.LINE_AA)
    cv2.putText(frame, text, (ox, oy),
                _FONT, scale, color,      thickness,     cv2.LINE_AA)


# =============================================================================
# Camera helpers
# =============================================================================

def _open_camera() -> cv2.VideoCapture | None:
    """Open VideoCapture(0) and validate it is readable."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error(
            "Could not open webcam (index 0). "
            "Ensure a camera is connected and not in use."
        )
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 560)
    logger.debug("Webcam opened for gesture detection.")
    return cap


def _release(cap: cv2.VideoCapture) -> None:
    """Safely release the camera and destroy the gesture window."""
    try:
        cap.release()
    except Exception as exc:
        logger.warning("Error releasing camera: %s", exc)
    try:
        cv2.destroyWindow(_WINDOW_TITLE)
        cv2.waitKey(1)
    except Exception as exc:
        logger.warning("Error destroying gesture window: %s", exc)
    logger.debug("Gesture detection camera released.")
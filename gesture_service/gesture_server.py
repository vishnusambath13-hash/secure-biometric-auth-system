# =============================================================================
# gesture_server.py — Gesture Detection Flask Microservice
# Secure UAV Command Authorization System
# =============================================================================
# Exposes a single REST endpoint that the main UAV Flask application calls
# when it needs a gesture-based command from the operator.
#
# Architecture:
#   Main UAV server  ──POST /detect──►  This service (port 6000)
#                    ◄──{ "gesture": "START_RECON" }──
#
# Endpoints:
#   POST /detect   Opens webcam, runs MediaPipe hand tracking, waits for a
#                  stable gesture (~2 s hold), closes webcam, returns JSON.
#   GET  /health   Liveness probe.
#
# Usage:
#   python gesture_server.py
#   # Server starts on http://127.0.0.1:6000
#
# Requirements:
#   pip install flask mediapipe opencv-python
# =============================================================================

import time
import threading

import cv2
import mediapipe as mp
from flask import Flask, jsonify

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SERVICE_PORT   = 6000
CAMERA_INDEX   = 0
FRAME_W        = 800
FRAME_H        = 560
STABLE_SECONDS = 2.0   # gesture must be held this long to be accepted
WINDOW_TITLE   = "UAV Gesture Detection"

# Prevent concurrent /detect calls from opening two webcams simultaneously
_detection_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Gesture → command mapping
# 4 fingers and open palm both map to SYSTEM_STATUS as specified
# ---------------------------------------------------------------------------
FINGER_TO_GESTURE = {
    0: "ABORT_MISSION",   # closed fist
    1: "START_RECON",
    2: "DEPLOY_DRONE",
    3: "RETURN_BASE",
    4: "SYSTEM_STATUS",   # 4 fingers
    5: "SYSTEM_STATUS",   # open palm
}

# ---------------------------------------------------------------------------
# HUD colour palette (BGR)
# ---------------------------------------------------------------------------
C_CYAN   = (255, 220,   0)
C_GREEN  = ( 40, 220,   0)
C_RED    = (  0,  40, 220)
C_AMBER  = (  0, 160, 255)
C_WHITE  = (220, 220, 220)
C_SHADOW = (  0,   0,   0)
FONT     = cv2.FONT_HERSHEY_SIMPLEX

# MediaPipe references
mp_hands   = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Landmark indices: fingertips and their PIP (proximal interphalangeal) joints
TIP_IDS = [4,  8, 12, 16, 20]
PIP_IDS = [3,  6, 10, 14, 18]


# =============================================================================
# Finger counting
# =============================================================================

def count_fingers(landmarks, handedness: str) -> int:
    """
    Count extended fingers using tip-vs-PIP landmark comparison.

    Thumb  : compared on the x-axis (lateral movement); direction flips for
             left vs right hand to handle the mirrored feed correctly.
    Fingers 1-4 : compared on the y-axis — tip above its PIP joint
                  (lower y in image coords) means the finger is extended.

    Returns an integer 0-5.
    """
    lm    = landmarks.landmark
    count = 0

    # Thumb — lateral axis
    if handedness == "Right":
        if lm[TIP_IDS[0]].x < lm[PIP_IDS[0]].x:
            count += 1
    else:
        if lm[TIP_IDS[0]].x > lm[PIP_IDS[0]].x:
            count += 1

    # Fingers 1-4 — vertical axis
    for i in range(1, 5):
        if lm[TIP_IDS[i]].y < lm[PIP_IDS[i]].y:
            count += 1

    return count


# =============================================================================
# HUD overlay
# =============================================================================

def _put_text(frame, text, origin, scale=0.45, color=C_WHITE, thickness=1):
    """Render text with a dark drop-shadow for legibility over any background."""
    ox, oy = origin
    cv2.putText(frame, text, (ox+1, oy+1), FONT, scale,
                C_SHADOW, thickness + 1, cv2.LINE_AA)
    cv2.putText(frame, text, (ox, oy),     FONT, scale,
                color,    thickness,      cv2.LINE_AA)


def _draw_overlay(frame, finger_count: int,
                  gesture: str | None, stable_pct: float) -> None:
    """
    Draw the tactical HUD overlay on the live camera frame.
    Shows: title bar, gesture legend, finger count badge,
           detected gesture label, stability confirmation bar.
    """
    h, w = frame.shape[:2]

    # Title bar
    cv2.rectangle(frame, (0, 0), (w, 36), (10, 18, 26), -1)
    _put_text(frame, "UAV GESTURE DETECTION — /detect ACTIVE",
              (10, 24), scale=0.48, color=C_CYAN)
    _put_text(frame, "Q: CANCEL", (w - 88, 24), scale=0.38, color=C_AMBER)

    # Corner bracket marks
    m, s = 8, 18
    for pts in [
        [(m, m+s), (m, m), (m+s, m)],
        [(w-m-s, m), (w-m, m), (w-m, m+s)],
        [(m, h-m-s), (m, h-m), (m+s, h-m)],
        [(w-m-s, h-m), (w-m, h-m), (w-m, h-m-s)],
    ]:
        for i in range(len(pts) - 1):
            cv2.line(frame, pts[i], pts[i+1], C_CYAN, 2, cv2.LINE_AA)

    # Gesture legend panel (bottom-left)
    legend = [
        ("1 finger",  "START_RECON"),
        ("2 fingers", "DEPLOY_DRONE"),
        ("3 fingers", "RETURN_BASE"),
        ("4 fingers", "SYSTEM_STATUS"),
        ("Open palm", "SYSTEM_STATUS"),
        ("Fist",      "ABORT_MISSION"),
    ]
    py = h - len(legend) * 20 - 22
    cv2.rectangle(frame, (4, py - 6), (220, h - 20), (8, 14, 22), -1)
    for i, (label, cmd) in enumerate(legend):
        active = (cmd == gesture)
        col    = C_GREEN if active else C_WHITE
        pfx    = ">" if active else " "
        _put_text(frame, f"{pfx} {label:<12}  {cmd}",
                  (10, py + i * 20), scale=0.34, color=col)

    # Large finger count badge (top-right)
    if finger_count >= 0:
        fc_col = C_RED if finger_count == 0 else C_GREEN
        _put_text(frame, str(finger_count), (w - 54, 90),
                  scale=2.2, color=fc_col, thickness=3)

    # Detected gesture label (centre-bottom)
    if gesture:
        g_col = C_RED if gesture == "ABORT_MISSION" else C_GREEN
        _put_text(frame, gesture, (w // 2 - 130, h - 44),
                  scale=0.68, color=g_col, thickness=2)

    # Stability confirmation progress bar
    if stable_pct > 0:
        bar_w   = w - 20
        filled  = int(bar_w * min(stable_pct, 1.0))
        bar_col = C_RED if gesture == "ABORT_MISSION" else C_CYAN
        cv2.rectangle(frame, (10, h - 14), (10 + bar_w, h - 8),
                      (30, 30, 30), -1)
        cv2.rectangle(frame, (10, h - 14), (10 + filled, h - 8),
                      bar_col, -1)
        _put_text(frame, "HOLD STEADY — CONFIRMING ...",
                  (10, h - 18), scale=0.35, color=C_AMBER)


# =============================================================================
# Core detection session (runs on the main thread — required by OpenCV/GUI)
# =============================================================================

def _run_detection_session() -> str | None:
    """
    Open the webcam and block until a confirmed gesture or cancellation.

    Returns:
        str   — gesture string (e.g. "START_RECON") when confirmed.
        None  — operator pressed Q, camera lost, or camera failed to open.
    """
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[DETECT] ERROR: Cannot open webcam.")
        return None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    print("[DETECT] Webcam open. Waiting for operator gesture ...")

    stable_gesture = None   # gesture currently being tracked
    stable_start   = None   # monotonic timestamp when tracking started
    result         = None   # final confirmed gesture (or None)

    with mp_hands.Hands(
        max_num_hands            = 1,
        min_detection_confidence = 0.75,
        min_tracking_confidence  = 0.65,
    ) as hands:

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[DETECT] Camera feed lost.")
                break

            now     = time.monotonic()
            display = cv2.flip(frame, 1)                       # mirror feed
            rgb     = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)
            rgb.flags.writeable = True
            display = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            current_gesture = None
            current_fingers = -1
            stable_pct      = 0.0

            if results.multi_hand_landmarks:
                lm_list    = results.multi_hand_landmarks[0]
                handedness = (
                    results.multi_handedness[0].classification[0].label
                    if results.multi_handedness else "Right"
                )

                # Draw MediaPipe skeleton on the display frame
                mp_drawing.draw_landmarks(
                    display, lm_list, mp_hands.HAND_CONNECTIONS
                )

                current_fingers = count_fingers(lm_list, handedness)
                current_gesture = FINGER_TO_GESTURE.get(current_fingers)

            # ── Stability gate ─────────────────────────────────────────────
            if current_gesture and current_gesture == stable_gesture:
                elapsed    = now - (stable_start or now)
                stable_pct = elapsed / STABLE_SECONDS

                if elapsed >= STABLE_SECONDS:
                    # Gesture confirmed
                    result = current_gesture
                    print(f"[DETECT] Confirmed: '{result}'")
                    break
            else:
                # New gesture or hand left frame — reset stability counter
                stable_gesture = current_gesture
                stable_start   = now if current_gesture else None

            # ── Render and check Q key ─────────────────────────────────────
            _draw_overlay(display, current_fingers, current_gesture, stable_pct)
            cv2.imshow(WINDOW_TITLE, display)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[DETECT] Cancelled by operator (Q).")
                break

    # Always release camera and destroy the preview window
    cap.release()
    cv2.destroyWindow(WINDOW_TITLE)
    cv2.waitKey(1)   # pump the event loop so the window actually closes
    return result


# =============================================================================
# Flask endpoints
# =============================================================================

@app.route("/detect", methods=["POST"])
def detect():
    """
    POST /detect — Trigger a single gesture detection session.

    Workflow:
        1. Acquire the detection lock (returns 503 if already in progress).
        2. Open the webcam and run MediaPipe tracking in the main thread.
        3. Block until operator holds a stable gesture for ~2 seconds,
           or presses Q to cancel.
        4. Close the webcam and return the result.

    Response:
        200  { "gesture": "START_RECON" }  — gesture detected and confirmed
        200  { "gesture": null }           — operator cancelled (Q pressed)
        503  { "error": "..." }            — another detection is running
    """
    # Reject concurrent requests — only one webcam session at a time
    if not _detection_lock.acquire(blocking=False):
        return jsonify({"error": "Detection already in progress."}), 503

    try:
        gesture = _run_detection_session()
        print(f"[API  ] /detect returning: gesture={gesture!r}")
        return jsonify({"gesture": gesture})
    finally:
        _detection_lock.release()


@app.route("/health", methods=["GET"])
def health():
    """GET /health — Liveness probe for the gesture microservice."""
    return jsonify({
        "status":  "ok",
        "service": "gesture-detection",
        "port":    SERVICE_PORT,
    })


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  UAV GESTURE DETECTION MICROSERVICE")
    print(f"  Listening on  http://127.0.0.1:{SERVICE_PORT}")
    print("  POST /detect  -> open webcam, detect gesture, return JSON")
    print("  GET  /health  -> liveness probe")
    print("=" * 60)

    # threaded=False  : cv2.imshow must run on the main thread (OS GUI rule).
    # use_reloader=False : prevents the process from forking, which breaks
    #                      OpenCV's GUI on macOS/Linux.
    app.run(
        host         = "127.0.0.1",
        port         = SERVICE_PORT,
        threaded     = False,
        use_reloader = False,
        debug        = False,
    )
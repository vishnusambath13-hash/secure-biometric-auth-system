# =============================================================================
# enroll_face.py — Operator Face Enrollment
# Secure Biometric Authentication and Command Authorization System
# =============================================================================
# One-time setup script that registers the authorized operator's face.
# Run this ONCE before enabling biometric authentication:
#
#   python enroll_face.py
#
# The captured image is saved to:
#   biometrics/operator_face.jpg
#
# This file is subsequently read by auth/biometric_auth.py during every
# login attempt to verify the operator's identity via DeepFace.
#
# Controls (shown live in the camera window):
#   SPACE → capture and save
#   ESC   → cancel without saving
# =============================================================================

import os
import sys
import cv2

# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------
_BIOMETRICS_DIR   = "biometrics"
_OUTPUT_PATH      = os.path.join(_BIOMETRICS_DIR, "operator_face.jpg")

# JPEG quality — 95 gives DeepFace enough detail without large file size
_JPEG_QUALITY     = 95


def main() -> None:
    """
    Run the face enrollment workflow:
        1. Import and call capture_face_image() from biometrics.camera_capture.
        2. On successful capture, ensure the output directory exists.
        3. Write the frame to biometrics/operator_face.jpg.
        4. Print a confirmation or cancellation message and exit cleanly.
    """
    print("=" * 58)
    print("  UAV COMMAND SYSTEM — OPERATOR FACE ENROLLMENT")
    print("=" * 58)
    print()
    print("[ENROLL] Face enrollment started.")
    print("[ENROLL] Press SPACE to capture your face.")
    print("[ENROLL] Press ESC  to cancel.")
    print()

    # ── 1. Import capture module ─────────────────────────────────────────────
    # Imported here (not at top-level) so a missing OpenCV/cv2 installation
    # produces a clear, contextual error rather than a bare ImportError on load.
    try:
        from biometrics.camera_capture import capture_face_image
    except ImportError as exc:
        print(f"[ENROLL] ERROR: Could not import camera_capture — {exc}")
        print("[ENROLL] Ensure opencv-python is installed:  pip install opencv-python")
        sys.exit(1)

    # ── 2. Open camera and capture frame ─────────────────────────────────────
    frame = capture_face_image()

    # ── 3. Handle cancellation ───────────────────────────────────────────────
    if frame is None:
        print()
        print("[ENROLL] Enrollment cancelled.")
        print("[ENROLL] No face image was saved. Run the script again to enroll.")
        sys.exit(0)

    # ── 4. Ensure output directory exists ────────────────────────────────────
    try:
        os.makedirs(_BIOMETRICS_DIR, exist_ok=True)
    except OSError as exc:
        print(f"[ENROLL] ERROR: Could not create directory '{_BIOMETRICS_DIR}' — {exc}")
        sys.exit(1)

    # ── 5. Overwrite warning if a face is already registered ─────────────────
    if os.path.isfile(_OUTPUT_PATH):
        print(f"[ENROLL] WARNING: An existing face image was found at '{_OUTPUT_PATH}'.")
        print("[ENROLL]          It will be overwritten with the new capture.")

    # ── 6. Save the captured frame ───────────────────────────────────────────
    try:
        success = cv2.imwrite(
            _OUTPUT_PATH,
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY],
        )
    except Exception as exc:
        print(f"[ENROLL] ERROR: Exception while saving image — {exc}")
        sys.exit(1)

    if not success:
        print(f"[ENROLL] ERROR: cv2.imwrite() failed for path '{_OUTPUT_PATH}'.")
        print("[ENROLL]        Check write permissions for the biometrics/ directory.")
        sys.exit(1)

    # ── 7. Confirm enrollment ────────────────────────────────────────────────
    file_kb = os.path.getsize(_OUTPUT_PATH) / 1024
    h, w    = frame.shape[:2]

    print()
    print("[ENROLL] ✔ Face successfully registered.")
    print(f"[ENROLL]   Saved  : {_OUTPUT_PATH}")
    print(f"[ENROLL]   Size   : {w}×{h} px  ({file_kb:.1f} KB)")
    print()
    print("[ENROLL] Biometric authentication is now active.")
    print("[ENROLL] The system will verify this face at every login.")
    print()


# =============================================================================
# Entry point
# =============================================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Ctrl-C during the camera window
        print()
        print("[ENROLL] Interrupted by operator. Enrollment cancelled.")
        sys.exit(0)
    except Exception as exc:
        # Catch-all — enrollment must never crash the terminal session
        print(f"[ENROLL] Unexpected error: {exc}")
        sys.exit(1)
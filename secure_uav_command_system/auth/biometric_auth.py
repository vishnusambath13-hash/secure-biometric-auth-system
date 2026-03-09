# =============================================================================
# auth/biometric_auth.py — DeepFace Facial Verification
# =============================================================================

import os
import logging
import cv2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BIOMETRICS_DIR = "biometrics"
_REGISTERED_FACE = os.path.join(_BIOMETRICS_DIR, "operator_face.jpg")

# ---------------------------------------------------------------------------
# DeepFace configuration
# ---------------------------------------------------------------------------

_MODEL_NAME = "Facenet512"
_DISTANCE_METRIC = "cosine"
_ENFORCE_DETECTION = False

# Face verification threshold
_MATCH_THRESHOLD = 0.65


# =============================================================================
# Public API
# =============================================================================

def operator_face_registered() -> bool:

    registered = os.path.isfile(_REGISTERED_FACE)

    if registered:
        logger.debug("Registered operator face found at '%s'.", _REGISTERED_FACE)

    else:
        logger.warning(
            "No registered operator face at '%s'. "
            "Run enroll_face.py before enabling biometric authentication.",
            _REGISTERED_FACE,
        )

    return registered


def verify_operator_face() -> bool:

    import time
    from deepface import DeepFace

    if not operator_face_registered():
        logger.error("No registered operator face.")
        return False

    face_detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error("Webcam could not be opened.")
        return False

    verified_frames = 0
    REQUIRED_MATCHES = 5
    TIMEOUT = 12

    start_time = time.time()

    logger.info("Biometric scanner started.")

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        frame = cv2.flip(frame, 1)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_detector.detectMultiScale(gray, 1.3, 5)

        h, w = frame.shape[:2]

        # Alignment box
        box_w = int(w * 0.35)
        box_h = int(h * 0.45)

        x1 = w // 2 - box_w // 2
        y1 = h // 2 - box_h // 2
        x2 = w // 2 + box_w // 2
        y2 = h // 2 + box_h // 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 180), 2)

        cv2.putText(
            frame,
            "ALIGN FACE IN FRAME",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 180),
            2,
        )

        for (fx, fy, fw, fh) in faces:

            cx = fx + fw // 2
            cy = fy + fh // 2

            cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (255, 0, 0), 2)

            if x1 < cx < x2 and y1 < cy < y2:

                cv2.putText(
                    frame,
                    "FACE LOCKED - SCANNING",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

                try:

                    result = DeepFace.verify(
                        img1_path=_REGISTERED_FACE,
                        img2_path=frame,
                        model_name=_MODEL_NAME,
                        distance_metric=_DISTANCE_METRIC,
                        enforce_detection=_ENFORCE_DETECTION,
                    )

                    distance = result.get("distance", 1.0)

                    # Color-coded score
                    score_color = (0, 255, 0) if distance < _MATCH_THRESHOLD else (0, 0, 255)

                    cv2.putText(
                        frame,
                        f"MATCH SCORE: {distance:.2f}",
                        (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        score_color,
                        2,
                    )

                    # Pass condition
                    if distance < _MATCH_THRESHOLD:
                        verified_frames += 1

                except Exception as e:
                    logger.warning(f"DeepFace verification error: {e}")

        # Success condition
        if verified_frames >= REQUIRED_MATCHES:

            logger.info("Face verification successful.")

            cap.release()
            cv2.destroyAllWindows()

            return True

        # Timeout condition
        if time.time() - start_time > TIMEOUT:

            logger.warning("Face verification timeout.")
            break

        cv2.imshow("Biometric Face Scanner", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    return False
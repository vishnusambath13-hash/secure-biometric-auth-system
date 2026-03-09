# =============================================================================
# auth/voice_auth.py — Dynamic Challenge-Phrase Voice Verification
# Secure Biometric Authentication and Command Authorization System
# =============================================================================

import random
import logging
import speech_recognition as sr

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Challenge phrase pool
# ---------------------------------------------------------------------------
CHALLENGE_PHRASES: list[str] = [
    "secure command confirmed",
    "mission authorization granted",
    "operator access verified",
    "control system unlocked",
]

# ---------------------------------------------------------------------------
# Recognizer tuning
# ---------------------------------------------------------------------------
_ENERGY_THRESHOLD    = 250
_PAUSE_THRESHOLD     = 0.7
_PHRASE_TIME_LIMIT   = 6
_AMBIENT_ADJUST_SECS = 1.0
_LANGUAGE            = "en-US"


# =============================================================================
# Public API
# =============================================================================

def verify_operator_voice() -> bool:

    print("\n[VOICE AUTH] Voice verification started.")

    # ── 1. Random challenge phrase ──────────────────────────────────────────
    expected_phrase = random.choice(CHALLENGE_PHRASES)

    print(
        f'[VOICE AUTH] Speak the following phrase:\n'
        f'             >> {expected_phrase.upper()} <<\n'
    )

    logger.info("Voice challenge issued: '%s'.", expected_phrase)

    # ── 2. Recognizer setup ──────────────────────────────────────────────────
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = _ENERGY_THRESHOLD
    recognizer.pause_threshold = _PAUSE_THRESHOLD
    recognizer.dynamic_energy_threshold = True

    # ── 3. Microphone check ──────────────────────────────────────────────────
    try:
        mic = sr.Microphone()
    except OSError as exc:
        logger.error("Microphone unavailable: %s", exc)
        print(f"[VOICE AUTH] ERROR: Microphone not found — {exc}")
        return False

    # ── 4. Ambient calibration ───────────────────────────────────────────────
    print("[VOICE AUTH] Calibrating microphone …")

    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(
                source,
                duration=_AMBIENT_ADJUST_SECS
            )

    except Exception as exc:
        logger.error("Microphone calibration failed: %s", exc)
        print(f"[VOICE AUTH] Calibration error: {exc}")
        return False

    # ── 5. Capture speech ────────────────────────────────────────────────────
    audio = _capture_audio(mic, recognizer)

    if audio is None:
        return False

    # ── 6. Speech recognition ───────────────────────────────────────────────
    transcription = _transcribe(audio, recognizer)

    if transcription is None:
        return False

    # ── 7. Phrase comparison ─────────────────────────────────────────────────
    return _compare_phrases(transcription, expected_phrase)


# =============================================================================
# Private helpers
# =============================================================================

def _capture_audio(
    mic: sr.Microphone,
    recognizer: sr.Recognizer,
):

    try:

        with mic as source:

            print("[VOICE AUTH] Listening … speak now")

            audio = recognizer.listen(
                source,
                phrase_time_limit=_PHRASE_TIME_LIMIT
            )

        logger.debug("Audio captured successfully.")
        return audio

    except OSError as exc:

        logger.error("Microphone read error: %s", exc)
        print(f"[VOICE AUTH] Microphone error: {exc}")
        return None

    except Exception as exc:

        logger.error("Unexpected error during audio capture: %s", exc)
        print(f"[VOICE AUTH] Unexpected capture error: {exc}")
        return None


def _transcribe(
    audio: "sr.AudioData",
    recognizer: sr.Recognizer
):

    try:

        text = recognizer.recognize_google(audio, language=_LANGUAGE)

        logger.info("Speech recognised: '%s'.", text)
        print(f'[VOICE AUTH] Recognised: "{text}"')

        return text

    except sr.UnknownValueError:

        logger.warning("Speech recognition could not interpret the audio.")
        print("[VOICE AUTH] Could not understand the audio — speak clearly.")

        return None

    except sr.RequestError as exc:

        logger.error("Speech recognition service unavailable: %s", exc)

        print(f"[VOICE AUTH] Recognition service unavailable: {exc}")

        return None

    except Exception as exc:

        logger.error("Unexpected transcription error: %s", exc)

        return None


def _compare_phrases(
    transcription: str,
    expected: str
) -> bool:

    spoken = " ".join(transcription.lower().split())
    expected = " ".join(expected.lower().split())

    if spoken == expected:

        logger.info("VOICE AUTH SUCCESS — phrase matched: '%s'.", expected)

        print("[VOICE AUTH] ✔ Phrase accepted. Voice verification passed.")

        return True

    logger.warning(
        "VOICE AUTH FAILED — expected: '%s' | received: '%s'.",
        expected,
        spoken,
    )

    print(
        f"[VOICE AUTH] ✘ Phrase mismatch.\n"
        f"  Expected : \"{expected}\"\n"
        f"  Received : \"{spoken}\""
    )

    return False
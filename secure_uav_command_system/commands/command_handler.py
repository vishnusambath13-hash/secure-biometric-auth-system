# =============================================================================
# commands/command_handler.py — UAV Command Dispatcher
# =============================================================================
# Maps validated command identifiers to simulated drone operations.
# Each function returns a human-readable status string that is returned to the
# frontend and stored in the command log.
# =============================================================================

import logging
import random

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simulated telemetry helpers
# ---------------------------------------------------------------------------

def _random_coords() -> str:
    lat = round(random.uniform(30.0, 60.0), 4)
    lon = round(random.uniform(-120.0, 40.0), 4)
    return f"{lat}°N, {abs(lon)}°{'W' if lon < 0 else 'E'}"


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def start_recon() -> str:
    """Initiate reconnaissance mission."""
    coords = _random_coords()
    logger.info("Command executed: start_recon @ %s", coords)
    return f"[RECON INITIATED] Drone entering recon pattern at {coords}. Sensors active."


def deploy_drone() -> str:
    """Launch and deploy the primary UAV asset."""
    logger.info("Command executed: deploy_drone")
    return "[DRONE DEPLOYED] UAV launched. Auto-navigation engaged. Awaiting waypoint confirmation."


def return_base() -> str:
    """Command the drone to return to base."""
    logger.info("Command executed: return_base")
    return "[RTB ORDERED] Return-to-base sequence initiated. ETA: 4 minutes."


def abort_mission() -> str:
    """Emergency mission abort — highest priority command."""
    logger.warning("Command executed: ABORT MISSION")
    return "[⚠ MISSION ABORTED] All operations halted. Drone entering safe hover mode."


def system_status() -> str:
    """Return a synthetic system health report."""
    battery  = random.randint(72, 99)
    signal   = random.randint(85, 100)
    altitude = random.randint(50, 300)
    logger.info("Command executed: system_status")
    return (
        f"[SYSTEM STATUS] "
        f"Battery: {battery}% | "
        f"Signal: {signal}% | "
        f"Altitude: {altitude}m | "
        f"Encryption: AES-256 ACTIVE | "
        f"Auth: RSA-2048 ACTIVE"
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "start_recon":   start_recon,
    "deploy_drone":  deploy_drone,
    "return_base":   return_base,
    "abort_mission": abort_mission,
    "system_status": system_status,
}


def execute_command(command_name: str) -> str:
    """
    Dispatch a validated command by name.

    Args:
        command_name: One of the keys in COMMAND_MAP.

    Returns:
        Status string from the command function.

    Raises:
        ValueError: If command_name is not recognised.
    """
    handler = COMMAND_MAP.get(command_name)
    if not handler:
        raise ValueError(f"Unknown command: '{command_name}'")
    return handler()
# =============================================================================
# commands/command_logger.py — Persistent Command Audit Log
# =============================================================================
# Writes every executed command to the MySQL command_logs table and also
# to the Python logging facility for syslog / file-based SIEM integration.
# =============================================================================

import logging
from datetime import datetime, timezone
from database.db_manager import get_db_connection

logger = logging.getLogger(__name__)


def log_command(
    command_name: str,
    operator:     str,
    result:       str,
    signature:    str = ""
) -> None:
    """
    Persist a command execution record.

    Args:
        command_name: The command that was executed.
        operator:     Username of the authenticated operator.
        result:       Status string returned by the command handler.
        signature:    Base64 RSA signature of the command (optional, stored for audit).
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Write to Python logging (file / syslog handler configured in app.py)
    logger.info(
        "CMD_LOG | ts=%s | op=%s | cmd=%s | result=%s",
        timestamp, operator, command_name, result
    )

    # Persist to database
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO command_logs
                (command_name, operator, result, signature, executed_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (command_name, operator, result, signature, timestamp)
        )
        conn.commit()
        logger.debug("Command log persisted to database (cmd=%s).", command_name)

    except Exception as exc:
        logger.error("Failed to persist command log: %s", exc)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
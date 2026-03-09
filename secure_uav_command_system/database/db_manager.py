# =============================================================================
# database/db_manager.py — MySQL Connection & Schema Bootstrap
# =============================================================================
# Provides a thin wrapper around mysql-connector-python.
# On first run, call init_db() to create the required tables.
# =============================================================================

import logging
import mysql.connector
from mysql.connector import Error
from config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_db_connection():
    """
    Open and return a new MySQL connection.

    Returns:
        mysql.connector.connection.MySQLConnection

    Raises:
        Exception: Propagates mysql.connector errors to the caller.
    """
    try:
        conn = mysql.connector.connect(
            host     = Config.DB_HOST,
            port     = Config.DB_PORT,
            user     = Config.DB_USER,
            password = Config.DB_PASSWORD,
            database = Config.DB_NAME,
        )
        return conn
    except Error as exc:
        logger.error("Database connection failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Users table for credential storage
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role          VARCHAR(32)  NOT NULL DEFAULT 'operator',
    active        TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Audit log for every executed command
CREATE TABLE IF NOT EXISTS command_logs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    command_name VARCHAR(64)   NOT NULL,
    operator     VARCHAR(64)   NOT NULL,
    result       TEXT          NOT NULL,
    signature    TEXT,
    executed_at  VARCHAR(64)   NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def init_db() -> None:
    """
    Create database tables if they do not already exist.
    Call once at application startup (app.py).
    """
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        for statement in _SCHEMA_SQL.strip().split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

        conn.commit()
        logger.info("Database schema initialised.")
    except Exception as exc:
        logger.error("Schema initialisation failed: %s", exc)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def insert_command_log(
    command_name: str,
    operator:     str,
    result:       str,
    signature:    str,
    executed_at:  str
) -> None:
    """
    Insert a single command log row.
    Prefer using command_logger.log_command() which calls this internally.
    """
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
            (command_name, operator, result, signature, executed_at)
        )
        conn.commit()
    except Exception as exc:
        logger.error("insert_command_log failed: %s", exc)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
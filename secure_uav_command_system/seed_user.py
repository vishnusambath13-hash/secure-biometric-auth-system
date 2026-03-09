"""
seed_user.py — Create the initial operator account
===================================================
Run ONCE after init_db() has created the schema:

    python seed_user.py

This inserts a default operator user with a bcrypt-hashed password.
Change the credentials before running in any real environment.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database.db_manager import get_db_connection, init_db
from security.hashing import hash_password

# ---------------------------------------------------------------------------
# Default credentials — CHANGE BEFORE DEPLOYMENT
# ---------------------------------------------------------------------------
DEFAULT_USERNAME = "operator"
DEFAULT_PASSWORD = "SecurePass123!"   # ← change this

def seed():
    print("[seed] Initialising database schema ...")
    init_db()

    hashed = hash_password(DEFAULT_PASSWORD)

    conn   = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role, active)
            VALUES (%s, %s, 'operator', 1)
            ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)
            """,
            (DEFAULT_USERNAME, hashed)
        )
        conn.commit()
        print(f"[seed] User '{DEFAULT_USERNAME}' created/updated.")
    except Exception as exc:
        print(f"[seed] ERROR: {exc}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    seed()
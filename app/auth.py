import sqlite3
from pathlib import Path
from typing import Optional

# bcrypt is optional at import time; functions below will use it if available
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except Exception:
    bcrypt = None  # type: ignore
    BCRYPT_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "users.db"


def init_db() -> None:
    """Initialize the users database and ensure a default user exists."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Ensure default user 'toru' exists. The plain password is 'jejeje' for now;
    # if bcrypt is available we store a bcrypt hash, otherwise store plaintext.
    cur.execute("SELECT id FROM users WHERE username = ?", ("toru",))
    if not cur.fetchone():
        default_pw = "jejeje"
        if BCRYPT_AVAILABLE and bcrypt is not None:
            pw_hash = bcrypt.hashpw(default_pw.encode("utf-8"), bcrypt.gensalt())
            pw_store = pw_hash.decode("utf-8")
        else:
            pw_store = default_pw
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)", ("toru", pw_store)
        )
        conn.commit()

    conn.close()


def check_credentials(username: str, password: str) -> bool:
    """Return True if username/password is valid according to users.db."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    stored = row[0]
    if BCRYPT_AVAILABLE and bcrypt is not None:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    # fallback: plaintext comparison
    return password == stored


# Initialize DB on import
init_db()

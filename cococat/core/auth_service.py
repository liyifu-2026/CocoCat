"""AuthService — login and initialization logic extracted from HTTP layer."""

import bcrypt
import os

from cococat.auth import create_access_token, verify_password, verify_user_password
from cococat.core.paths import memory_dir, session_dir
from cococat.db import Database


class AuthService:
    """Authentication operations: login, initialization, status."""

    def __init__(self, db: Database, config_store=None):
        self._db = db
        self._config_store = config_store

    def has_users(self) -> bool:
        row = self._db.fetch_one("SELECT COUNT(*) AS n FROM users")
        return (row["n"] if row else 0) > 0

    def authenticate(self, username: str, password: str) -> tuple[str | None, str | None]:
        """Authenticate a user. Returns (token, error_detail) — one is always None."""
        if self.has_users():
            if not verify_user_password(username, password, self._db):
                return None, "Incorrect username or password"
            token = create_access_token({"sub": username})
        else:
            if not verify_password(password):
                return None, "Incorrect password"
            token = create_access_token({"sub": "admin"})
        return token, None

    def initialize(self, username: str, password: str) -> tuple[str | None, str | None]:
        """Create initial admin user. Only works when no users exist. Returns (token, error_detail)."""
        if self.has_users():
            return None, "Users already exist"

        if not username or len(password) < 4 or not password.strip():
            return None, "Username required, password >= 4 chars"

        self._create_user_in_db(username, password)
        self._ensure_user_dirs(username)

        token = create_access_token({"sub": username})
        return token, None

    def create_user(self, username: str, password: str) -> tuple[str | None, str | None]:
        """Create a user. Returns (username, error_detail) — one is always None."""
        if not username or len(password) < 4 or not password.strip():
            return None, "Username required, password >= 4 chars"

        if self._db.fetch_one("SELECT id FROM users WHERE id = ?", (username,)):
            return None, "User already exists"

        self._create_user_in_db(username, password)
        self._ensure_user_dirs(username)

        return username, None

    def delete_user(self, username: str) -> bool:
        """Delete a user. Returns False if not found."""
        if not self._db.fetch_one("SELECT id FROM users WHERE id = ?", (username,)):
            return False
        self._db.execute("DELETE FROM users WHERE id = ?", (username,))
        self._db.commit()
        import shutil
        for d in [f"config/users/{username}", f"agents/{username}"]:
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
        return True

    def reset_password(self, username: str, password: str) -> tuple[bool, str | None]:
        """Reset user password. Returns (success, error_detail)."""
        if not self._db.fetch_one("SELECT id FROM users WHERE id = ?", (username,)):
            return False, "User not found"
        if len(password) < 4:
            return False, "Password must be >= 4 chars"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        self._db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, username))
        self._db.commit()
        return True, None

    def list_users(self) -> list[dict]:
        """List all users with display_name and created_at."""
        rows = self._db.fetch_all(
            "SELECT id, display_name, created_at FROM users ORDER BY created_at"
        )
        return [{"id": r["id"], "display_name": r["display_name"] or "", "created_at": r["created_at"]} for r in rows]

    # ── helpers ──────────────────────────────────────────────

    def _create_user_in_db(self, username: str, password: str) -> None:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        self._db.execute_insert(
            "INSERT INTO users (id, password_hash, display_name) VALUES (?, ?, ?)",
            (username, password_hash, username),
        )
        self._db.commit()

    @staticmethod
    def _ensure_user_dirs(username: str) -> None:
        os.makedirs(f"config/users/{username}", exist_ok=True)
        os.makedirs(memory_dir("default", username), exist_ok=True)
        os.makedirs(os.path.join(memory_dir("default", username), "compiled"), exist_ok=True)
        os.makedirs(os.path.join(memory_dir("default", username), "summaries"), exist_ok=True)
        os.makedirs(session_dir("default", username), exist_ok=True)

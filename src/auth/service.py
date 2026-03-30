"""Local authentication service for the Streamlit application."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.logger import get_logger

LOGGER = get_logger(__name__)


class AuthValidationError(ValueError):
    """Raised when sign-up or sign-in input is invalid."""


@dataclass
class AuthUser:
    """Authenticated user profile stored in the local auth database."""

    user_id: int
    email: str
    full_name: str
    created_at: str
    last_login_at: Optional[str] = None


class AuthService:
    """Provide local account registration and sign-in with hashed passwords.

    Passwords are stored using PBKDF2-HMAC-SHA256 with a per-user random salt.
    """

    EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", flags=re.I)
    HASH_ITERATIONS = 240_000

    def __init__(self, db_path: str | Path, min_password_length: int = 8) -> None:
        self.db_path = Path(db_path)
        self.min_password_length = min_password_length
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def register_user(self, email: str, password: str, full_name: str) -> AuthUser:
        """Create a new local account and return the resulting user profile."""

        normalized_email = self._normalize_email(email)
        clean_name = " ".join(full_name.split()).strip()
        if not clean_name:
            raise AuthValidationError("Please provide your name.")
        self._validate_password(password)

        salt = os.urandom(16)
        password_hash = self._hash_password(password, salt)
        now = self._now()

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (email, full_name, password_salt, password_hash, created_at, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (normalized_email, clean_name, salt.hex(), password_hash, now, now),
                )
                user_id = int(cursor.lastrowid)
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise AuthValidationError("An account with that email already exists.") from error

        LOGGER.info("Registered new Streamlit user: %s", normalized_email)
        return AuthUser(user_id=user_id, email=normalized_email, full_name=clean_name, created_at=now, last_login_at=now)

    def authenticate(self, email: str, password: str) -> Optional[AuthUser]:
        """Verify credentials and return the authenticated user, if valid."""

        normalized_email = self._normalize_email(email)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, full_name, password_salt, password_hash, created_at, last_login_at
                FROM users
                WHERE email = ?
                """,
                (normalized_email,),
            ).fetchone()

            if row is None:
                return None

            expected_hash = self._hash_password(password, bytes.fromhex(row["password_salt"]))
            if not hmac.compare_digest(expected_hash, row["password_hash"]):
                return None

            now = self._now()
            connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"]))
            connection.commit()

        LOGGER.info("Authenticated Streamlit user: %s", normalized_email)
        return AuthUser(
            user_id=int(row["id"]),
            email=str(row["email"]),
            full_name=str(row["full_name"]),
            created_at=str(row["created_at"]),
            last_login_at=now,
        )

    def get_user_by_email(self, email: str) -> Optional[AuthUser]:
        """Fetch a user profile by email if it exists."""

        normalized_email = self._normalize_email(email)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, email, full_name, created_at, last_login_at FROM users WHERE email = ?",
                (normalized_email,),
            ).fetchone()
        if row is None:
            return None
        return AuthUser(
            user_id=int(row["id"]),
            email=str(row["email"]),
            full_name=str(row["full_name"]),
            created_at=str(row["created_at"]),
            last_login_at=str(row["last_login_at"]) if row["last_login_at"] else None,
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _normalize_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if not normalized:
            raise AuthValidationError("Please provide your email address.")
        if not self.EMAIL_PATTERN.match(normalized):
            raise AuthValidationError("Please enter a valid email address.")
        return normalized

    def _validate_password(self, password: str) -> None:
        if len(password) < self.min_password_length:
            raise AuthValidationError(f"Password must be at least {self.min_password_length} characters long.")
        if password.lower() == password or password.upper() == password:
            LOGGER.info("Password accepted without mixed case; user can still proceed.")

    def _hash_password(self, password: str, salt: bytes) -> str:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.HASH_ITERATIONS)
        return digest.hex()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

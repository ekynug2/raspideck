"""Authentication utilities for RaspiDeck Server."""

from __future__ import annotations

import hmac
import time
from collections import defaultdict

import bcrypt
from flask import request, session

# Rate limiting: max 5 attempts per IP per 15 minutes
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 900  # 15 minutes


def _get_client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"


def is_rate_limited() -> bool:
    """Check if current IP exceeded login attempt limit."""
    ip = _get_client_ip()
    now = time.time()
    # Prune old attempts
    _LOGIN_ATTEMPTS[ip] = [t for t in _LOGIN_ATTEMPTS[ip] if now - t < _WINDOW_SECONDS]
    return len(_LOGIN_ATTEMPTS[ip]) >= _MAX_ATTEMPTS


def record_attempt() -> None:
    """Record a failed login attempt for rate limiting."""
    ip = _get_client_ip()
    _LOGIN_ATTEMPTS[ip].append(time.time())


def hash_password(plain: str) -> str:
    """Hash password with bcrypt. Use for initial setup / password change."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, stored: str) -> bool:
    """Verify plaintext against stored hash.

    Supports both bcrypt hashes and legacy plaintext (constant-time compare).
    Legacy plaintext match triggers a warning — caller should re-hash.
    """
    if stored.startswith(("$2b$", "$2a$")):
        return bcrypt.checkpw(plain.encode(), stored.encode())
    # ponytail: legacy plaintext fallback — remove after migration
    return hmac.compare_digest(plain, stored)


def require_auth() -> bool:
    """Verify if the current session is authenticated as admin."""
    return bool(session.get("authenticated"))

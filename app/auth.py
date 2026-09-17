"""Bearer-token auth. Deliberately minimal.

The brief requires admin-issued access, not public sign-up. This is a gate to
keep the public and competitors out of a partner tool, not a system protecting
financial records. No registration, no password reset, no email verification.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.config import settings


@dataclass(frozen=True)
class Principal:
    """Who is calling, and what they are allowed to see."""

    token: str
    is_internal: bool

    @property
    def tail(self) -> str:
        """Last four characters, for logging without writing the secret down."""
        return self.token[-4:] if len(self.token) >= 4 else "????"


def require_token(request: Request) -> Principal:
    """Identify the caller, or raise 401. Constant-time comparison."""
    if not settings.auth_required:
        # No tokens configured: development only. Treated as internal so the
        # full dashboard is usable locally, and logged loudly at startup.
        return Principal(token="development", is_internal=True)

    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""

    for known in settings.internal_tokens:
        if secrets.compare_digest(presented, known):
            return Principal(token=known, is_internal=True)
    for known in settings.access_tokens:
        if secrets.compare_digest(presented, known):
            return Principal(token=known, is_internal=False)

    raise HTTPException(status_code=401, detail="Not authorised")

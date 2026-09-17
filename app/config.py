"""Configuration, all from environment variables. No secrets in code."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split(var: str) -> set[str]:
    raw = os.environ.get(var, "")
    return {t.strip() for t in raw.split(",") if t.strip()}


def _tokens() -> set[str]:
    """Partner tokens. Access to the twelve public outputs only."""
    return _split("ACCESS_TOKENS")


def _internal_tokens() -> set[str]:
    """Adaptavate tokens. Additionally receive the internal-only figures."""
    return _split("INTERNAL_TOKENS")


@dataclass(frozen=True)
class Settings:
    # Adaptavate's workbook. Mounted at run time, never baked into an image.
    workbook_path: str = os.environ.get("WORKBOOK_PATH", "model/Adaptavate-BBE-TEST-model.xlsx")
    # "formulas" (fast) or "libreoffice" (compatible). See docs/03.
    backend: str = os.environ.get("CALC_BACKEND", "formulas")
    # Admin-issued partner tokens. No public sign-up, per the brief.
    access_tokens: set[str] = field(default_factory=_tokens)
    internal_tokens: set[str] = field(default_factory=_internal_tokens)
    # Serve the front end from this process. False if hosting it separately.
    serve_web: bool = os.environ.get("SERVE_WEB", "true").lower() != "false"
    environment: str = os.environ.get("ENVIRONMENT", "development")

    @property
    def auth_required(self) -> bool:
        return bool(self.access_tokens or self.internal_tokens)

    @property
    def all_tokens(self) -> set[str]:
        return self.access_tokens | self.internal_tokens


settings = Settings()

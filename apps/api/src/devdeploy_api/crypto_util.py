"""Local-at-rest encryption for project secrets (Fernet, key derived from settings)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from devdeploy_api.config import Settings, get_settings


def _fernet(settings: Settings | None = None) -> Fernet:
    settings = settings or get_settings()
    raw = (settings.secrets_encryption_key or settings.session_secret).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str, settings: Settings | None = None) -> str:
    return _fernet(settings).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str, settings: Settings | None = None) -> str:
    try:
        return _fernet(settings).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt secret with current key") from exc

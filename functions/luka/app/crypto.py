from __future__ import annotations

import base64
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

log = logging.getLogger("luka.crypto")


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().app_encryption_key
    if key:
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError):
            log.warning("APP_ENCRYPTION_KEY non valida: uso una chiave effimera.")
    else:
        log.warning(
            "APP_ENCRYPTION_KEY assente: genero una chiave effimera "
            "(i token cifrati non sopravvivono al riavvio)."
        )
    return Fernet(Fernet.generate_key())


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def new_key() -> str:
    return Fernet.generate_key().decode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

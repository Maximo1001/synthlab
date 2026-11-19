"""TOTP RFC 6238 (SHA-1, 30 s, 6 dígitos) sin dependencias externas."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    num = struct.unpack(">I", digest[off : off + 4])[0] & 0x7FFFFFFF
    return str(num % 10**DIGITS).zfill(DIGITS)


def verify(secret: str, code: str, last_step: int | None, *, at: float | None = None) -> int | None:
    """Devuelve el contador aceptado (para impedir reutilizar el mismo código) o None.
    Tolera ±1 ventana de desfase de reloj."""
    code = (code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    current = int((at if at is not None else time.time()) // STEP)
    for step in (current - 1, current, current + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(_code(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "SYNTHLAB") -> str:
    return (
        f"otpauth://totp/{quote(issuer)}:{quote(account)}"
        f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP}"
    )


def current_code(secret: str, at: float | None = None) -> str:
    """Utilidad para tests."""
    return _code(secret, int((at if at is not None else time.time()) // STEP))

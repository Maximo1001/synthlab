"""Hash de contraseñas (Argon2id, parámetros OWASP) y política de contraseñas (NIST 800-63B)."""

from __future__ import annotations

import hashlib
import urllib.request

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# OWASP Password Storage Cheat Sheet: Argon2id, m=19 MiB, t=2, p=1 como mínimo.
_ph = PasswordHasher(time_cost=3, memory_cost=19 * 1024, parallelism=1)

# Hash de una contraseña aleatoria: se verifica cuando el usuario no existe para que el
# tiempo de respuesta no revele qué correos están registrados.
DUMMY_HASH = _ph.hash("synthlab-dummy-password-for-timing-equalization")

MIN_LEN = 12
MAX_LEN = 128

# Extracto de las contraseñas más filtradas + variantes obvias del dominio.
COMMON = {
    "123456789012",
    "password1234",
    "qwertyuiop12",
    "contraseña123",
    "contrasena123",
    "123456123456",
    "111111111111",
    "000000000000",
    "abcdefghijkl",
    "iloveyou1234",
    "passwordpassword",
    "qwerty123456",
    "1q2w3e4r5t6y",
    "administrator",
    "welcome12345",
    "synthlab1234",
    "synthlab2026",
    "synthlab2025",
    "musica123456",
    "letmein12345",
}


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _ph.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True


def _pwned(password: str) -> bool:
    """k-anonimato contra Have I Been Pwned: sólo se envían 5 hex del SHA-1."""
    sha1 = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    req = urllib.request.Request(
        f"https://api.pwnedpasswords.com/range/{prefix}",
        headers={"Add-Padding": "true", "User-Agent": "synthlab-password-check"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310  # nosec B310
            body = resp.read().decode("utf-8")
    except OSError:
        return False  # fail-open: la caída de HIBP no debe impedir registrarse
    return any(line.split(":")[0] == suffix and not line.endswith(":0") for line in body.splitlines())


def policy_errors(password: str, *, email: str = "", name: str = "", hibp: bool = False) -> str | None:
    if not isinstance(password, str):
        return "Contraseña no válida."
    if len(password) < MIN_LEN:
        return f"La contraseña debe tener al menos {MIN_LEN} caracteres."
    if len(password) > MAX_LEN:
        return f"La contraseña no puede superar {MAX_LEN} caracteres."
    low = password.lower()
    if low in COMMON or len(set(low)) < 5:
        return "Esa contraseña es demasiado común o repetitiva."
    local = email.split("@")[0].lower()
    if (local and len(local) >= 4 and local in low) or (name and len(name) >= 4 and name.lower() in low):
        return "La contraseña no puede contener tu nombre ni tu correo."
    if hibp and _pwned(password):
        return "Esa contraseña aparece en filtraciones públicas. Elige otra."
    return None

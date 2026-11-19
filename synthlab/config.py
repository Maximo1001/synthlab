"""Configuración por variables de entorno. Seguro por defecto: sin SYNTHLAB_ENV=development
la app arranca en modo producción y exige SECRET_KEY y PUBLIC_URL."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def load_config() -> dict:
    env = os.environ.get("SYNTHLAB_ENV", "production").strip().lower()
    dev = env in {"development", "testing"}
    secret = os.environ.get("SYNTHLAB_SECRET_KEY", "")
    if not secret:
        if not dev:
            raise RuntimeError(
                "SYNTHLAB_SECRET_KEY es obligatoria en producción "
                "(genera una con: python -c 'import secrets;print(secrets.token_urlsafe(64))')"
            )
        secret = secrets.token_urlsafe(64)  # efímera: las sesiones mueren al reiniciar
    if not dev and len(secret) < 32:
        raise RuntimeError("SYNTHLAB_SECRET_KEY demasiado corta (mínimo 32 caracteres)")

    public_url = os.environ.get("SYNTHLAB_PUBLIC_URL", "").rstrip("/")
    if not public_url:
        if not dev:
            raise RuntimeError("SYNTHLAB_PUBLIC_URL es obligatoria en producción (p.ej. https://synthlab.example)")
        public_url = ""  # desarrollo: se usa el host de cada petición (security.public_url)

    secure_cookies = _bool("SYNTHLAB_SECURE_COOKIES", not dev)
    instance = Path(os.environ.get("SYNTHLAB_INSTANCE_DIR", ROOT / "instance"))

    return {
        "ENV": env,
        "DEV": dev,
        "TESTING": env == "testing",
        "SECRET_KEY": secret,
        "PUBLIC_URL": public_url,
        "INSTANCE_DIR": instance,
        "DATABASE": os.environ.get("SYNTHLAB_DATABASE", str(instance / "synthlab.db")),
        "SECURITY_LOG": os.environ.get("SYNTHLAB_SECURITY_LOG", str(instance / "seguridad.log")),
        "FRONTEND_DIR": Path(os.environ.get("SYNTHLAB_FRONTEND_DIR", ROOT)),
        # Cookies: prefijo __Host- sólo es válido con Secure
        "SECURE_COOKIES": secure_cookies,
        "SESSION_COOKIE": "__Host-sl_sid" if secure_cookies else "sl_sid",
        "CSRF_COOKIE": "__Host-sl_csrf" if secure_cookies else "sl_csrf",
        "SESSION_IDLE_MINUTES": _int("SYNTHLAB_SESSION_IDLE_MINUTES", 30),
        "SESSION_ABSOLUTE_HOURS": _int("SYNTHLAB_SESSION_ABSOLUTE_HOURS", 12),
        "MAX_CONTENT_LENGTH": 64 * 1024,
        # Proxy inverso (nginx) delante: nº de saltos de confianza para X-Forwarded-*
        "TRUSTED_PROXIES": _int("SYNTHLAB_TRUSTED_PROXIES", 0),
        "TRUSTED_HOSTS": [h for h in os.environ.get("SYNTHLAB_TRUSTED_HOSTS", "").split(",") if h] or None,
        # Política de cuentas
        "REQUIRE_EMAIL_VERIFICATION": _bool("SYNTHLAB_REQUIRE_EMAIL_VERIFICATION", True),
        "LOCKOUT_THRESHOLD": _int("SYNTHLAB_LOCKOUT_THRESHOLD", 5),
        "LOCKOUT_MINUTES": _int("SYNTHLAB_LOCKOUT_MINUTES", 15),
        "ADMIN_REQUIRE_MFA": _bool("SYNTHLAB_ADMIN_REQUIRE_MFA", not dev),
        "HIBP_CHECK": _bool("SYNTHLAB_HIBP_CHECK", False),
        "EXPOSE_DEV_LINKS": dev and _bool("SYNTHLAB_EXPOSE_DEV_LINKS", True),
        # Correo
        "MAIL_BACKEND": os.environ.get("SYNTHLAB_MAIL_BACKEND", "console"),  # console | smtp
        "MAIL_FROM": os.environ.get("SYNTHLAB_MAIL_FROM", "SYNTHLAB <no-reply@synthlab.local>"),
        "SMTP_HOST": os.environ.get("SYNTHLAB_SMTP_HOST", ""),
        "SMTP_PORT": _int("SYNTHLAB_SMTP_PORT", 587),
        "SMTP_USER": os.environ.get("SYNTHLAB_SMTP_USER", ""),
        "SMTP_PASSWORD": os.environ.get("SYNTHLAB_SMTP_PASSWORD", ""),
    }

"""Controles transversales: sesiones de servidor, CSRF, rate limiting, cabeceras, auditoría."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, Response, current_app, g, jsonify, request

from .db import execute, get_db, now, query_one

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


# ---------------------------------------------------------------- utilidades
def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def public_url() -> str:
    """URL pública para enlaces de correo. En producción es fija (evita envenenar enlaces
    de reset con la cabecera Host); en desarrollo, si no se define, se usa la del request."""
    return current_app.config["PUBLIC_URL"] or request.host_url.rstrip("/")


def client_ip() -> str:
    # request.remote_addr ya viene corregido por ProxyFix sólo si hay proxies de confianza.
    return request.remote_addr or "-"


def api_error(message: str, status: int, **extra: Any) -> tuple[Response, int]:
    return jsonify({"error": message, **extra}), status


def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------- auditoría
def audit(event: str, status: int = 200, detail: str = "", user: Any = None) -> None:
    """Registro de seguridad. Mismo contrato JSON que leen las reglas Wazuh del curso:
    ts/app/evento/usuario/ip/metodo/ruta/estado/detalle. Nunca registrar secretos."""
    u = user if user is not None else getattr(g, "user", None)
    uid = u["id"] if u else None
    label = u["email"] if u else "-"
    ts = now()
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        "app": "synthlab",
        "evento": event,
        "usuario": label,
        "ip": client_ip(),
        "metodo": request.method,
        "ruta": request.path,
        "estado": status,
        "detalle": detail[:300],
    }
    try:
        execute(
            "INSERT INTO audit_log (ts, event, user_id, user_label, ip, method, path, status, detail)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, event, uid, label, record["ip"], request.method, request.path, status, detail[:300]),
        )
    except Exception:  # la auditoría nunca debe tumbar la petición
        current_app.logger.exception("audit_log insert failed")
    path = current_app.config["SECURITY_LOG"]
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        current_app.logger.warning("No se pudo escribir el log de seguridad en %s", path)


# ---------------------------------------------------------------- rate limiting
def rate_limited(key: str, limit: int, window: int) -> int:
    """Ventana fija persistida en SQLite (compartida entre workers de gunicorn).
    Devuelve 0 si se permite, o los segundos a esperar si se supera el límite."""
    db = get_db()
    ts = now()
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT window_start, hits FROM rate_limits WHERE key = ?", (key,)).fetchone()
        if row is None or ts - row["window_start"] >= window:
            db.execute(
                "INSERT INTO rate_limits (key, window_start, hits) VALUES (?, ?, 1)"
                " ON CONFLICT(key) DO UPDATE SET window_start = excluded.window_start, hits = 1",
                (key, ts),
            )
            db.execute("COMMIT")
            return 0
        if row["hits"] >= limit:
            db.execute("COMMIT")
            return max(1, window - (ts - row["window_start"]))
        db.execute("UPDATE rate_limits SET hits = hits + 1 WHERE key = ?", (key,))
        db.execute("COMMIT")
        return 0
    except Exception:
        db.execute("ROLLBACK")
        raise


def limit(scope: str, limit_: int, window: int, *, by: str = "ip") -> Callable:
    """Decorador de límite por IP (o por usuario autenticado si by='user')."""

    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            ident = str(g.user["id"]) if by == "user" and getattr(g, "user", None) else client_ip()
            if current_app.config.get("RATELIMIT_DISABLED"):
                return fn(*args, **kwargs)
            wait = rate_limited(f"{scope}:{ident}", limit_, window)
            if wait:
                audit("rate_limit", 429, scope)
                resp, status = api_error("Demasiadas peticiones. Inténtalo más tarde.", 429)
                resp.headers["Retry-After"] = str(wait)
                return resp, status
            return fn(*args, **kwargs)

        return wrapper

    return deco


# ---------------------------------------------------------------- sesiones
def create_session(resp: Response, user_id: int) -> None:
    """Emite una sesión NUEVA (rotación tras login → evita fijación de sesión)."""
    token = new_token(32)
    ts = now()
    execute(
        "INSERT INTO sessions (user_id, token_hash, created_at, last_seen, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, sha256(token), ts, ts, client_ip(), (request.user_agent.string or "")[:200]),
    )
    cfg = current_app.config
    resp.set_cookie(
        cfg["SESSION_COOKIE"],
        token,
        max_age=cfg["SESSION_ABSOLUTE_HOURS"] * 3600,
        secure=cfg["SECURE_COOKIES"],
        httponly=True,
        samesite="Strict",
        path="/",
    )
    issue_csrf(resp)  # nuevo token CSRF ligado a la nueva sesión


def destroy_session(resp: Response) -> None:
    token = request.cookies.get(current_app.config["SESSION_COOKIE"])
    if token:
        execute("DELETE FROM sessions WHERE token_hash = ?", (sha256(token),))
    resp.delete_cookie(
        current_app.config["SESSION_COOKIE"], path="/", secure=current_app.config["SECURE_COOKIES"], samesite="Strict"
    )


def load_session() -> None:
    g.user = None
    g.session_id = None
    token = request.cookies.get(current_app.config["SESSION_COOKIE"])
    if not token or len(token) > 100:
        return
    row = query_one(
        "SELECT s.id AS sid, s.created_at, s.last_seen, u.* FROM sessions s"
        " JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (sha256(token),),
    )
    if row is None:
        return
    cfg = current_app.config
    ts = now()
    expired = (
        ts - row["last_seen"] > cfg["SESSION_IDLE_MINUTES"] * 60
        or ts - row["created_at"] > cfg["SESSION_ABSOLUTE_HOURS"] * 3600
    )
    if expired or row["disabled"]:
        execute("DELETE FROM sessions WHERE id = ?", (row["sid"],))
        return
    if ts - row["last_seen"] > 60:  # no escribir en cada petición
        execute("UPDATE sessions SET last_seen = ? WHERE id = ?", (ts, row["sid"]))
    g.user = row
    g.session_id = row["sid"]


# ---------------------------------------------------------------- CSRF
def issue_csrf(resp: Response) -> str:
    token = new_token(32)
    cfg = current_app.config
    resp.set_cookie(cfg["CSRF_COOKIE"], token, secure=cfg["SECURE_COOKIES"], httponly=True, samesite="Strict", path="/")
    g.csrf_token = token
    return token


def csrf_protect() -> tuple[Response, int] | None:
    """Defensa en profundidad para métodos que cambian estado:
    1) Fetch Metadata (Sec-Fetch-Site) 2) Origin == PUBLIC_URL/host 3) token doble-envío
    (cookie HttpOnly + cabecera X-CSRF-Token obtenida de /api/csrf, comparación en tiempo constante)."""
    if request.method in SAFE_METHODS or not request.path.startswith("/api/"):
        return None
    site = request.headers.get("Sec-Fetch-Site")
    if site and site not in {"same-origin", "none"}:
        audit("csrf_rechazado", 403, f"sec-fetch-site={site}")
        return api_error("Petición rechazada (origen cruzado).", 403)
    origin = request.headers.get("Origin")
    if origin:
        allowed = {public_url(), request.host_url.rstrip("/")}
        if origin.rstrip("/") not in allowed:
            audit("csrf_rechazado", 403, f"origin={origin[:100]}")
            return api_error("Petición rechazada (origen no permitido).", 403)
    cookie = request.cookies.get(current_app.config["CSRF_COOKIE"], "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        audit("csrf_rechazado", 403, "token ausente o inválido")
        return api_error("Token CSRF inválido. Recarga la página.", 403)
    if not request.is_json:
        return api_error("Content-Type debe ser application/json.", 415)
    return None


# ---------------------------------------------------------------- autorización
def login_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not getattr(g, "user", None):
            return api_error("Necesitas iniciar sesión.", 401)
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn: Callable) -> Callable:
    @wraps(fn)
    @login_required
    def wrapper(*args: Any, **kwargs: Any):
        if g.user["role"] != "admin":
            audit("acceso_denegado", 403, "admin")
            return api_error("No autorizado.", 403)
        if current_app.config["ADMIN_REQUIRE_MFA"] and not g.user["totp_secret"]:
            return api_error("Activa la verificación en dos pasos para usar el panel.", 403, code="mfa_required")
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------- cabeceras
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "style-src-attr 'unsafe-inline'",  # sólo atributos style= (variables CSS); sin <style>/JS inline
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "media-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def security_headers(resp: Response) -> Response:
    h = resp.headers
    csp = CSP + ("; upgrade-insecure-requests" if current_app.config["SECURE_COOKIES"] else "")
    h["Content-Security-Policy"] = csp
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "strict-origin-when-cross-origin"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    h["Cross-Origin-Resource-Policy"] = "same-origin"
    if current_app.config["SECURE_COOKIES"]:
        h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    if request.path.startswith("/api/"):
        h["Cache-Control"] = "no-store"
    h.pop("Server", None)
    return resp


def register(app: Flask) -> None:
    app.before_request(load_session)
    app.before_request(csrf_protect)
    app.after_request(security_headers)

"""/api/auth — registro, verificación, login (+2FA), logout, recuperación de contraseña."""

from __future__ import annotations

import re
import secrets

from flask import Blueprint, current_app, g, jsonify, make_response, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import mailer, totp
from .db import execute, get_db, now, query_one
from .passwords import DUMMY_HASH, hash_password, needs_rehash, policy_errors, verify_password
from .security import (
    api_error,
    audit,
    client_ip,
    create_session,
    destroy_session,
    issue_csrf,
    json_body,
    limit,
    new_token,
    public_url,
    rate_limited,
    sha256,
)

bp = Blueprint("auth", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[^\s@<>()\[\],;:\"]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}$")
NAME_RE = re.compile(r"^[^\x00-\x1f<>]{2,40}$")
GENERIC_LOGIN_ERROR = "Correo o contraseña incorrectos."


def norm_email(raw: object) -> str:
    return raw.strip().lower() if isinstance(raw, str) else ""


def valid_email(email: str) -> bool:
    return len(email) <= 254 and bool(EMAIL_RE.match(email))


def valid_name(name: object) -> bool:
    return isinstance(name, str) and bool(NAME_RE.match(name.strip()))


def public_user(u) -> dict:
    return {
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        "role": u["role"],
        "email_verified": bool(u["email_verified"]),
        "mfa": bool(u["totp_secret"]),
        "created_at": u["created_at"],
        "last_login_at": u["last_login_at"],
    }


def issue_token(user_id: int, purpose: str, ttl: int) -> str:
    token = new_token(32)
    execute(
        "UPDATE tokens SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL", (now(), user_id, purpose)
    )  # sólo el último enlace es válido
    execute(
        "INSERT INTO tokens (user_id, purpose, token_hash, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, purpose, sha256(token), now() + ttl),
    )
    return token


def consume_token(token: object, purpose: str):
    if not isinstance(token, str) or not 20 <= len(token) <= 100:
        return None
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    row = db.execute(
        "SELECT * FROM tokens WHERE token_hash = ? AND purpose = ? AND used_at IS NULL AND expires_at > ?",
        (sha256(token), purpose, now()),
    ).fetchone()
    if row:
        db.execute("UPDATE tokens SET used_at = ? WHERE id = ?", (now(), row["id"]))
    db.execute("COMMIT")
    return row


def _link(param: str, token: str) -> str:
    return f"{public_url()}/?{param}={token}#account"


def _mfa_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="synthlab-mfa-pending")


# ------------------------------------------------------------------ CSRF bootstrap
@bp.get("/csrf")
def csrf():
    token = request.cookies.get(current_app.config["CSRF_COOKIE"])
    if token and 20 <= len(token) <= 100:
        return jsonify({"csrf": token})
    resp = make_response()
    token = issue_csrf(resp)
    resp.set_data(jsonify({"csrf": token}).get_data())
    resp.mimetype = "application/json"
    return resp


# ------------------------------------------------------------------ registro
@bp.post("/auth/register")
@limit("register", 5, 3600)
def register():
    data = json_body()
    email, name, password = norm_email(data.get("email")), data.get("name"), data.get("password")
    if data.get("website"):  # honeypot anti-bots
        return jsonify({"ok": True, "message": "Revisa tu correo para activar la cuenta."}), 202
    if not valid_email(email):
        return api_error("Escribe un correo válido.", 400)
    if not valid_name(name):
        return api_error("El nombre debe tener entre 2 y 40 caracteres.", 400)
    name = name.strip()
    err = policy_errors(password, email=email, name=name, hibp=current_app.config["HIBP_CHECK"])
    if err:
        return api_error(err, 400)

    cfg = current_app.config
    message = (
        "Cuenta creada. Revisa tu correo para activarla."
        if cfg["REQUIRE_EMAIL_VERIFICATION"]
        else "Cuenta creada. Ya puedes iniciar sesión."
    )
    extra: dict = {}
    existing = query_one("SELECT id FROM users WHERE email = ?", (email,))
    if existing:
        # Respuesta idéntica: no revelamos qué correos existen. Avisamos al titular.
        mailer.send(
            email,
            "Intento de registro en SYNTHLAB",
            "Alguien ha intentado crear una cuenta con tu correo. Si fuiste tú, inicia sesión "
            "o recupera tu contraseña. Si no, puedes ignorar este mensaje.",
        )
        audit("registro_duplicado", 202, email)
        return jsonify({"ok": True, "message": message}), 202

    ts = now()
    cur = execute(
        "INSERT INTO users (email, name, password_hash, email_verified, created_at, updated_at,"
        " password_changed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, name, hash_password(password), 0 if cfg["REQUIRE_EMAIL_VERIFICATION"] else 1, ts, ts, ts),
    )
    uid = cur.lastrowid
    if cfg["REQUIRE_EMAIL_VERIFICATION"]:
        token = issue_token(uid, "verify", 24 * 3600)
        link = _link("verify", token)
        mailer.send(
            email,
            "Activa tu cuenta de SYNTHLAB",
            f"Hola {name},\n\nActiva tu cuenta en las próximas 24 h:\n{link}\n\n"
            "Si no te has registrado, ignora este correo.",
        )
        if cfg["EXPOSE_DEV_LINKS"]:
            extra["dev_link"] = link
    audit("registro", 202, email, user={"id": uid, "email": email})
    return jsonify({"ok": True, "message": message, **extra}), 202


@bp.post("/auth/verify")
@limit("verify", 20, 3600)
def verify_email():
    row = consume_token(json_body().get("token"), "verify")
    if not row:
        return api_error("El enlace no es válido o ha caducado.", 400)
    execute("UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?", (now(), row["user_id"]))
    audit("email_verificado", 200, user=query_one("SELECT * FROM users WHERE id = ?", (row["user_id"],)))
    return jsonify({"ok": True, "message": "Correo verificado. Ya puedes iniciar sesión."})


@bp.post("/auth/resend-verification")
@limit("resend", 3, 3600)
def resend_verification():
    email = norm_email(json_body().get("email"))
    u = query_one("SELECT * FROM users WHERE email = ?", (email,)) if valid_email(email) else None
    if u and not u["email_verified"]:
        token = issue_token(u["id"], "verify", 24 * 3600)
        mailer.send(
            email, "Activa tu cuenta de SYNTHLAB", f"Activa tu cuenta en las próximas 24 h:\n{_link('verify', token)}"
        )
    return jsonify({"ok": True, "message": "Si la cuenta existe y está pendiente, te hemos reenviado el enlace."}), 202


# ------------------------------------------------------------------ login
def _register_failure(u) -> None:
    cfg = current_app.config
    fails = u["failed_logins"] + 1
    locked_until = None
    if fails >= cfg["LOCKOUT_THRESHOLD"]:
        # bloqueo progresivo: 15, 30, 60... min (tope 24 h)
        factor = 2 ** min(fails - cfg["LOCKOUT_THRESHOLD"], 6)
        locked_until = now() + min(cfg["LOCKOUT_MINUTES"] * 60 * factor, 86400)
    execute(
        "UPDATE users SET failed_logins = ?, locked_until = COALESCE(?, locked_until) WHERE id = ?",
        (fails, locked_until, u["id"]),
    )
    if locked_until and fails == cfg["LOCKOUT_THRESHOLD"]:
        audit("cuenta_bloqueada", 423, f"{fails} fallos", user=u)
        mailer.send(
            u["email"],
            "Cuenta de SYNTHLAB bloqueada temporalmente",
            "Hemos detectado varios intentos fallidos de acceso y hemos bloqueado tu cuenta "
            "temporalmente. Si no fuiste tú, cambia tu contraseña con «He olvidado mi contraseña».",
        )


def _finish_login(u, method: str):
    execute("UPDATE users SET failed_logins = 0, locked_until = NULL, last_login_at = ? WHERE id = ?", (now(), u["id"]))
    fresh = query_one("SELECT * FROM users WHERE id = ?", (u["id"],))
    resp = make_response()
    resp.mimetype = "application/json"
    create_session(resp, u["id"])
    resp.set_data(jsonify({"ok": True, "user": public_user(fresh), "csrf": g.csrf_token}).get_data())
    audit("login_ok", 200, method, user=u)
    return resp


@bp.post("/auth/login")
@limit("login", 10, 300)
def login():
    data = json_body()
    email, password = norm_email(data.get("email")), data.get("password")
    if not valid_email(email) or not isinstance(password, str) or len(password) > 256:
        verify_password(DUMMY_HASH, "x")
        return api_error(GENERIC_LOGIN_ERROR, 401)
    # límite adicional por cuenta (frena credential stuffing distribuido)
    if not current_app.config.get("RATELIMIT_DISABLED") and rate_limited(f"login-acct:{sha256(email)}", 20, 3600):
        audit("rate_limit", 429, "login por cuenta")
        return api_error("Demasiados intentos. Inténtalo más tarde.", 429)

    u = query_one("SELECT * FROM users WHERE email = ?", (email,))
    if u is None:
        verify_password(DUMMY_HASH, password)  # igualar tiempos
        audit("login_fallido", 401, f"usuario inexistente {email}")
        return api_error(GENERIC_LOGIN_ERROR, 401)
    if u["locked_until"] and u["locked_until"] > now():
        verify_password(DUMMY_HASH, password)
        audit("login_bloqueado", 401, user=u)
        return api_error(GENERIC_LOGIN_ERROR, 401)
    if not verify_password(u["password_hash"], password):
        _register_failure(u)
        audit("login_fallido", 401, "contraseña incorrecta", user=u)
        return api_error(GENERIC_LOGIN_ERROR, 401)
    if u["disabled"]:
        audit("login_deshabilitado", 403, user=u)
        return api_error("Esta cuenta está deshabilitada.", 403)
    if needs_rehash(u["password_hash"]):
        execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), u["id"]))
    if not u["email_verified"]:
        return api_error("Verifica tu correo antes de iniciar sesión.", 403, code="unverified")
    if u["totp_secret"]:
        pending = _mfa_serializer().dumps({"uid": u["id"], "pc": u["password_changed_at"]})
        audit("login_mfa_pendiente", 200, user=u)
        return jsonify({"ok": True, "mfa_required": True, "mfa_token": pending})
    return _finish_login(u, "password")


@bp.post("/auth/login/mfa")
@limit("login-mfa", 10, 300)
def login_mfa():
    data = json_body()
    try:
        claims = _mfa_serializer().loads(str(data.get("mfa_token", "")), max_age=300)
    except (BadSignature, SignatureExpired):
        return api_error("La verificación ha caducado. Vuelve a iniciar sesión.", 401)
    u = query_one("SELECT * FROM users WHERE id = ?", (claims.get("uid"),))
    if not u or not u["totp_secret"] or u["password_changed_at"] != claims.get("pc") or u["disabled"]:
        return api_error("La verificación ha caducado. Vuelve a iniciar sesión.", 401)
    if not current_app.config.get("RATELIMIT_DISABLED") and rate_limited(f"mfa-user:{u['id']}", 5, 300):
        audit("rate_limit", 429, "mfa", user=u)
        return api_error("Demasiados intentos. Espera unos minutos.", 429)
    code = str(data.get("code", ""))
    step = totp.verify(u["totp_secret"], code, u["totp_last_step"])
    if step is not None:
        execute("UPDATE users SET totp_last_step = ? WHERE id = ?", (step, u["id"]))
        return _finish_login(u, "password+totp")
    # código de recuperación (un solo uso)
    norm = code.strip().replace("-", "").replace(" ", "").lower()
    if len(norm) == 10:
        rc = query_one(
            "SELECT id FROM recovery_codes WHERE user_id = ? AND code_hash = ? AND used_at IS NULL",
            (u["id"], sha256(norm)),
        )
        if rc:
            execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?", (now(), rc["id"]))
            audit("mfa_codigo_recuperacion", 200, user=u)
            return _finish_login(u, "password+recovery")
    _register_failure(u)
    audit("mfa_fallido", 401, user=u)
    return api_error("Código incorrecto.", 401)


@bp.post("/auth/logout")
def logout():
    resp = make_response(jsonify({"ok": True}))
    if g.user:
        audit("logout", 200)
    destroy_session(resp)
    issue_csrf(resp)
    return resp


# ------------------------------------------------------------------ recuperación
@bp.post("/auth/forgot")
@limit("forgot", 5, 3600)
def forgot():
    email = norm_email(json_body().get("email"))
    extra: dict = {}
    u = query_one("SELECT * FROM users WHERE email = ?", (email,)) if valid_email(email) else None
    if u and not u["disabled"]:
        token = issue_token(u["id"], "reset", 30 * 60)
        link = _link("reset", token)
        mailer.send(
            email,
            "Restablece tu contraseña de SYNTHLAB",
            f"Para elegir una nueva contraseña abre este enlace (válido 30 min, un solo uso):\n"
            f"{link}\n\nSi no lo has pedido, ignora este correo: tu contraseña sigue igual.",
        )
        audit("reset_solicitado", 202, user=u)
        if current_app.config["EXPOSE_DEV_LINKS"]:
            extra["dev_link"] = link
    else:
        audit("reset_solicitado", 202, f"sin cuenta {email[:80]}")
    return jsonify(
        {"ok": True, "message": "Si existe una cuenta con ese correo, te hemos enviado un enlace.", **extra}
    ), 202


@bp.post("/auth/reset")
@limit("reset", 10, 3600)
def reset():
    data = json_body()
    token, password = data.get("token"), data.get("password")
    # validamos la política ANTES de consumir el token para no quemarlo por un error de formato
    if not isinstance(token, str):
        return api_error("El enlace no es válido o ha caducado.", 400)
    pre = query_one(
        "SELECT u.* FROM tokens t JOIN users u ON u.id = t.user_id WHERE t.token_hash = ?"
        " AND t.purpose = 'reset' AND t.used_at IS NULL AND t.expires_at > ?",
        (sha256(token), now()),
    )
    if not pre:
        return api_error("El enlace no es válido o ha caducado.", 400)
    err = policy_errors(password, email=pre["email"], name=pre["name"], hibp=current_app.config["HIBP_CHECK"])
    if err:
        return api_error(err, 400)
    row = consume_token(token, "reset")
    if not row:
        return api_error("El enlace no es válido o ha caducado.", 400)
    ts = now()
    execute(
        "UPDATE users SET password_hash = ?, password_changed_at = ?, updated_at = ?, failed_logins = 0,"
        " locked_until = NULL, email_verified = 1 WHERE id = ?",
        (hash_password(password), ts, ts, row["user_id"]),
    )
    execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))  # cierra todas las sesiones
    audit("reset_ok", 200, user=pre)
    mailer.send(
        pre["email"],
        "Tu contraseña de SYNTHLAB ha cambiado",
        f"Se ha cambiado la contraseña de tu cuenta desde la IP {client_ip()}. "
        "Si no fuiste tú, contacta con nosotros inmediatamente.",
    )
    return jsonify({"ok": True, "message": "Contraseña actualizada. Inicia sesión con la nueva."})


def generate_recovery_codes(user_id: int) -> list[str]:
    execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
    codes = []
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    for _ in range(8):
        raw = "".join(secrets.choice(alphabet) for _ in range(10))
        execute("INSERT INTO recovery_codes (user_id, code_hash) VALUES (?, ?)", (user_id, sha256(raw)))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes

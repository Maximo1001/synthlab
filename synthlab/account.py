"""/api/me — perfil, contraseña, 2FA, sesiones activas, exportación RGPD y baja."""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, make_response

from . import mailer, totp
from .auth import generate_recovery_codes, public_user, valid_name
from .db import execute, now, query_all, query_one
from .passwords import hash_password, policy_errors, verify_password
from .security import api_error, audit, destroy_session, json_body, limit, login_required

bp = Blueprint("account", __name__, url_prefix="/api/me")


def _reauth(password: object) -> bool:
    """Operaciones sensibles exigen la contraseña actual (re-autenticación)."""
    return isinstance(password, str) and verify_password(g.user["password_hash"], password)


@bp.get("")
@login_required
def me():
    return jsonify({"user": public_user(g.user)})


@bp.patch("")
@login_required
def update_profile():
    name = json_body().get("name")
    if not valid_name(name):
        return api_error("El nombre debe tener entre 2 y 40 caracteres.", 400)
    execute("UPDATE users SET name = ?, updated_at = ? WHERE id = ?", (name.strip(), now(), g.user["id"]))
    audit("perfil_actualizado", 200)
    return jsonify({"user": public_user(query_one("SELECT * FROM users WHERE id = ?", (g.user["id"],)))})


@bp.post("/password")
@login_required
@limit("change-pw", 5, 900, by="user")
def change_password():
    data = json_body()
    if not _reauth(data.get("current")):
        audit("password_cambio_fallido", 401)
        return api_error("La contraseña actual no es correcta.", 401)
    new = data.get("new")
    if isinstance(new, str) and verify_password(g.user["password_hash"], new):
        return api_error("La nueva contraseña debe ser distinta de la actual.", 400)
    err = policy_errors(new, email=g.user["email"], name=g.user["name"], hibp=current_app.config["HIBP_CHECK"])
    if err:
        return api_error(err, 400)
    ts = now()
    execute(
        "UPDATE users SET password_hash = ?, password_changed_at = ?, updated_at = ? WHERE id = ?",
        (hash_password(new), ts, ts, g.user["id"]),
    )
    # cerrar el resto de sesiones; mantener la actual
    execute("DELETE FROM sessions WHERE user_id = ? AND id != ?", (g.user["id"], g.session_id))
    audit("password_cambiada", 200)
    mailer.send(
        g.user["email"],
        "Tu contraseña de SYNTHLAB ha cambiado",
        "Se ha cambiado la contraseña de tu cuenta y se han cerrado tus otras sesiones. "
        "Si no fuiste tú, restablécela inmediatamente.",
    )
    return jsonify({"ok": True, "message": "Contraseña actualizada. Se han cerrado tus otras sesiones."})


# ------------------------------------------------------------------ sesiones
@bp.get("/sessions")
@login_required
def sessions():
    rows = query_all(
        "SELECT id, created_at, last_seen, ip, user_agent FROM sessions WHERE user_id = ? ORDER BY last_seen DESC",
        (g.user["id"],),
    )
    return jsonify({"sessions": [dict(r) | {"current": r["id"] == g.session_id} for r in rows]})


@bp.delete("/sessions/<int:sid>")
@login_required
def revoke_session(sid: int):
    cur = execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (sid, g.user["id"]))
    if not cur.rowcount:
        return api_error("Sesión no encontrada.", 404)
    audit("sesion_revocada", 200, str(sid))
    return jsonify({"ok": True})


@bp.post("/sessions/revoke-others")
@login_required
def revoke_others():
    cur = execute("DELETE FROM sessions WHERE user_id = ? AND id != ?", (g.user["id"], g.session_id))
    audit("sesiones_revocadas", 200, str(cur.rowcount))
    return jsonify({"ok": True, "revoked": cur.rowcount})


# ------------------------------------------------------------------ 2FA (TOTP)
@bp.post("/2fa/setup")
@login_required
@limit("2fa-setup", 10, 900, by="user")
def mfa_setup():
    if g.user["totp_secret"]:
        return api_error("La verificación en dos pasos ya está activa.", 409)
    if not _reauth(json_body().get("password")):
        return api_error("La contraseña no es correcta.", 401)
    secret = totp.new_secret()
    execute("UPDATE users SET totp_pending = ? WHERE id = ?", (secret, g.user["id"]))
    return jsonify({"secret": secret, "uri": totp.provisioning_uri(secret, g.user["email"])})


@bp.post("/2fa/enable")
@login_required
@limit("2fa-enable", 10, 900, by="user")
def mfa_enable():
    pending = g.user["totp_pending"]
    if not pending:
        return api_error("Primero genera la clave.", 400)
    step = totp.verify(pending, str(json_body().get("code", "")), None)
    if step is None:
        return api_error("Código incorrecto. Revisa la hora de tu móvil.", 400)
    execute(
        "UPDATE users SET totp_secret = ?, totp_pending = NULL, totp_last_step = ? WHERE id = ?",
        (pending, step, g.user["id"]),
    )
    codes = generate_recovery_codes(g.user["id"])
    audit("2fa_activado", 200)
    mailer.send(
        g.user["email"], "Verificación en dos pasos activada", "Has activado la verificación en dos pasos en SYNTHLAB."
    )
    return jsonify({"ok": True, "recovery_codes": codes})


@bp.post("/2fa/disable")
@login_required
@limit("2fa-disable", 5, 900, by="user")
def mfa_disable():
    data = json_body()
    if not g.user["totp_secret"]:
        return api_error("La verificación en dos pasos no está activa.", 400)
    if not _reauth(data.get("password")):
        return api_error("La contraseña no es correcta.", 401)
    if totp.verify(g.user["totp_secret"], str(data.get("code", "")), g.user["totp_last_step"]) is None:
        return api_error("Código incorrecto.", 400)
    execute(
        "UPDATE users SET totp_secret = NULL, totp_pending = NULL, totp_last_step = NULL WHERE id = ?", (g.user["id"],)
    )
    execute("DELETE FROM recovery_codes WHERE user_id = ?", (g.user["id"],))
    audit("2fa_desactivado", 200)
    mailer.send(
        g.user["email"],
        "Verificación en dos pasos desactivada",
        "Se ha desactivado la verificación en dos pasos de tu cuenta. Si no fuiste tú, "
        "cambia tu contraseña de inmediato.",
    )
    return jsonify({"ok": True})


@bp.post("/2fa/recovery-codes")
@login_required
@limit("2fa-codes", 3, 3600, by="user")
def mfa_new_codes():
    if not g.user["totp_secret"]:
        return api_error("Activa antes la verificación en dos pasos.", 400)
    if not _reauth(json_body().get("password")):
        return api_error("La contraseña no es correcta.", 401)
    audit("2fa_codigos_regenerados", 200)
    return jsonify({"recovery_codes": generate_recovery_codes(g.user["id"])})


# ------------------------------------------------------------------ RGPD
@bp.get("/export")
@login_required
@limit("export", 5, 3600, by="user")
def export():
    uid = g.user["id"]
    data = {
        "perfil": public_user(g.user),
        "patrones": [
            dict(r)
            for r in query_all(
                "SELECT id, name, bpm, steps, share_slug, created_at, updated_at FROM patterns WHERE user_id = ?",
                (uid,),
            )
        ],
        "favoritos": [r["product"] for r in query_all("SELECT product FROM favorites WHERE user_id = ?", (uid,))],
        "sesiones": [
            dict(r)
            for r in query_all("SELECT created_at, last_seen, ip, user_agent FROM sessions WHERE user_id = ?", (uid,))
        ],
        "actividad": [
            dict(r)
            for r in query_all(
                "SELECT ts, event, ip, path, status FROM audit_log WHERE user_id = ? ORDER BY ts DESC LIMIT 500", (uid,)
            )
        ],
    }
    audit("datos_exportados", 200)
    resp = make_response(jsonify(data))
    resp.headers["Content-Disposition"] = 'attachment; filename="synthlab-mis-datos.json"'
    return resp


@bp.delete("")
@login_required
@limit("delete-account", 5, 3600, by="user")
def delete_account():
    if not _reauth(json_body().get("password")):
        audit("baja_fallida", 401)
        return api_error("La contraseña no es correcta.", 401)
    user = dict(g.user)
    audit("cuenta_eliminada", 200)
    execute("DELETE FROM users WHERE id = ?", (user["id"],))  # cascada: sesiones, patrones, favoritos...
    execute("UPDATE audit_log SET user_label = '[eliminado]' WHERE user_id = ?", (user["id"],))
    g.user = None
    resp = make_response(jsonify({"ok": True}))
    destroy_session(resp)
    return resp

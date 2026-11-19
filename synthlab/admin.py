"""/api/admin — panel de administración (rol admin + 2FA obligatorio en producción)."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from .db import execute, now, query_all, query_one
from .security import admin_required, api_error, audit, json_body

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _page() -> tuple[int, int]:
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    return page, (page - 1) * 25


@bp.get("/stats")
@admin_required
def stats():
    day = now() - 86400
    q = lambda sql, p=(): query_one(sql, p)["n"]  # noqa: E731
    return jsonify(
        {
            "users": q("SELECT COUNT(*) AS n FROM users"),
            "verified": q("SELECT COUNT(*) AS n FROM users WHERE email_verified = 1"),
            "mfa": q("SELECT COUNT(*) AS n FROM users WHERE totp_secret IS NOT NULL"),
            "locked": q("SELECT COUNT(*) AS n FROM users WHERE locked_until > ?", (now(),)),
            "sessions": q("SELECT COUNT(*) AS n FROM sessions"),
            "patterns": q("SELECT COUNT(*) AS n FROM patterns"),
            "messages_open": q("SELECT COUNT(*) AS n FROM messages WHERE handled = 0"),
            "subscribers": q("SELECT COUNT(*) AS n FROM newsletter WHERE confirmed = 1"),
            "failed_logins_24h": q(
                "SELECT COUNT(*) AS n FROM audit_log WHERE event = 'login_fallido' AND ts > ?", (day,)
            ),
            "csrf_blocked_24h": q(
                "SELECT COUNT(*) AS n FROM audit_log WHERE event = 'csrf_rechazado' AND ts > ?", (day,)
            ),
            "rate_limited_24h": q("SELECT COUNT(*) AS n FROM audit_log WHERE event = 'rate_limit' AND ts > ?", (day,)),
        }
    )


@bp.get("/users")
@admin_required
def users():
    page, offset = _page()
    term = request.args.get("q", "")[:80]
    like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = query_all(
        "SELECT id, email, name, role, email_verified, disabled, locked_until, totp_secret IS NOT NULL AS mfa,"
        " created_at, last_login_at FROM users WHERE email LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\'"
        " ORDER BY id DESC LIMIT 25 OFFSET ?",
        (like, like, offset),
    )
    return jsonify({"users": [dict(r) for r in rows], "page": page})


@bp.post("/users/<int:uid>")
@admin_required
def user_action(uid: int):
    action = json_body().get("action")
    target = query_one("SELECT * FROM users WHERE id = ?", (uid,))
    if not target:
        return api_error("Usuario no encontrado.", 404)
    if uid == g.user["id"]:
        return api_error("No puedes aplicarte acciones a ti mismo.", 400)
    sql = {
        "disable": ("UPDATE users SET disabled = 1 WHERE id = ?", True),
        "enable": ("UPDATE users SET disabled = 0 WHERE id = ?", False),
        "unlock": ("UPDATE users SET locked_until = NULL, failed_logins = 0 WHERE id = ?", False),
        "promote": ("UPDATE users SET role = 'admin' WHERE id = ?", True),
        "demote": ("UPDATE users SET role = 'user' WHERE id = ?", True),
        "logout": ("UPDATE users SET updated_at = updated_at WHERE id = ?", True),
    }.get(action if isinstance(action, str) else "")
    if not sql:
        return api_error("Acción no válida.", 400)
    execute(sql[0], (uid,))
    if sql[1]:  # cambios de privilegio/estado invalidan las sesiones del usuario afectado
        execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
    audit("admin_accion", 200, f"{action} -> {target['email']}")
    return jsonify({"ok": True})


@bp.get("/audit")
@admin_required
def audit_log():
    page, offset = _page()
    event = request.args.get("event", "")[:40]
    rows = query_all(
        "SELECT ts, event, user_label, ip, method, path, status, detail FROM audit_log"
        " WHERE (? = '' OR event = ?) ORDER BY id DESC LIMIT 25 OFFSET ?",
        (event, event, offset),
    )
    return jsonify({"events": [dict(r) for r in rows], "page": page})


@bp.get("/messages")
@admin_required
def messages():
    page, offset = _page()
    rows = query_all(
        "SELECT id, name, email, body, created_at, handled FROM messages ORDER BY handled, id DESC LIMIT 25 OFFSET ?",
        (offset,),
    )
    return jsonify({"messages": [dict(r) for r in rows], "page": page})


@bp.post("/messages/<int:mid>/handled")
@admin_required
def message_handled(mid: int):
    cur = execute("UPDATE messages SET handled = 1 WHERE id = ?", (mid,))
    return jsonify({"ok": True}) if cur.rowcount else api_error("No encontrado.", 404)

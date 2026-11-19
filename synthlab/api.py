"""/api — patrones del secuenciador, favoritos, contacto, newsletter, salud."""

from __future__ import annotations

import json

from flask import Blueprint, current_app, g, jsonify

from . import mailer
from .auth import norm_email, valid_email
from .db import execute, now, query_all, query_one
from .security import api_error, audit, client_ip, json_body, limit, login_required, new_token, public_url, sha256

bp = Blueprint("api", __name__, url_prefix="/api")

PRODUCTS = {"keystone-49", "orbit-dj-2", "helix-one", "slicer-s4", "pulse-16", "core-io"}
MAX_PATTERNS = 50
ROWS, STEPS = 4, 16


def _valid_steps(steps: object) -> bool:
    return (
        isinstance(steps, list)
        and len(steps) == ROWS
        and all(isinstance(r, list) and len(r) == STEPS and all(v in (0, 1) for v in r) for r in steps)
    )


def _pattern_out(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "bpm": r["bpm"],
        "steps": json.loads(r["steps"]),
        "shared": r["share_slug"],
        "updated_at": r["updated_at"],
    }


def _pattern_in(data: dict) -> tuple[dict | None, str | None]:
    name, bpm, steps = data.get("name"), data.get("bpm"), data.get("steps")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or any(ord(c) < 32 for c in name):
        return None, "El nombre debe tener entre 1 y 40 caracteres."
    if not isinstance(bpm, int) or isinstance(bpm, bool) or not 60 <= bpm <= 180:
        return None, "El BPM debe estar entre 60 y 180."
    if not _valid_steps(steps):
        return None, "Patrón no válido."
    return {"name": name.strip(), "bpm": bpm, "steps": json.dumps(steps, separators=(",", ":"))}, None


def _own_pattern(pid: int):
    # Autorización por objeto: la condición user_id = ? impide el IDOR. Respuesta 404 (no 403)
    # para no confirmar que el recurso existe.
    return query_one("SELECT * FROM patterns WHERE id = ? AND user_id = ?", (pid, g.user["id"]))


@bp.get("/health")
def health():
    query_one("SELECT 1")
    return jsonify({"status": "ok"})


# ------------------------------------------------------------------ patrones
@bp.get("/patterns")
@login_required
def patterns_list():
    rows = query_all("SELECT * FROM patterns WHERE user_id = ? ORDER BY updated_at DESC", (g.user["id"],))
    return jsonify({"patterns": [_pattern_out(r) for r in rows]})


@bp.post("/patterns")
@login_required
@limit("pattern-write", 60, 3600, by="user")
def patterns_create():
    p, err = _pattern_in(json_body())
    if err:
        return api_error(err, 400)
    count = query_one("SELECT COUNT(*) AS n FROM patterns WHERE user_id = ?", (g.user["id"],))["n"]
    if count >= MAX_PATTERNS:
        return api_error(f"Has alcanzado el máximo de {MAX_PATTERNS} patrones.", 409)
    ts = now()
    cur = execute(
        "INSERT INTO patterns (user_id, name, bpm, steps, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (g.user["id"], p["name"], p["bpm"], p["steps"], ts, ts),
    )
    return jsonify({"pattern": _pattern_out(_own_pattern(cur.lastrowid))}), 201


@bp.get("/patterns/<int:pid>")
@login_required
def patterns_get(pid: int):
    r = _own_pattern(pid)
    return jsonify({"pattern": _pattern_out(r)}) if r else api_error("No encontrado.", 404)


@bp.put("/patterns/<int:pid>")
@login_required
@limit("pattern-write", 60, 3600, by="user")
def patterns_update(pid: int):
    if not _own_pattern(pid):
        return api_error("No encontrado.", 404)
    p, err = _pattern_in(json_body())
    if err:
        return api_error(err, 400)
    execute(
        "UPDATE patterns SET name = ?, bpm = ?, steps = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (p["name"], p["bpm"], p["steps"], now(), pid, g.user["id"]),
    )
    return jsonify({"pattern": _pattern_out(_own_pattern(pid))})


@bp.delete("/patterns/<int:pid>")
@login_required
def patterns_delete(pid: int):
    cur = execute("DELETE FROM patterns WHERE id = ? AND user_id = ?", (pid, g.user["id"]))
    return jsonify({"ok": True}) if cur.rowcount else api_error("No encontrado.", 404)


@bp.post("/patterns/<int:pid>/share")
@login_required
def patterns_share(pid: int):
    r = _own_pattern(pid)
    if not r:
        return api_error("No encontrado.", 404)
    enable = json_body().get("enabled", True) is True
    slug = (r["share_slug"] or new_token(9)) if enable else None  # 72 bits: no enumerable
    execute("UPDATE patterns SET share_slug = ? WHERE id = ? AND user_id = ?", (slug, pid, g.user["id"]))
    return jsonify({"shared": slug})


@bp.get("/shared/<slug>")
@limit("shared", 120, 60)
def shared(slug: str):
    if not 8 <= len(slug) <= 20:
        return api_error("No encontrado.", 404)
    r = query_one(
        "SELECT p.*, u.name AS author FROM patterns p JOIN users u ON u.id = p.user_id WHERE p.share_slug = ?", (slug,)
    )
    if not r:
        return api_error("No encontrado.", 404)
    return jsonify(
        {
            "pattern": {
                "name": r["name"],
                "bpm": r["bpm"],
                "steps": json.loads(r["steps"]),
                "author": r["author"].split(" ")[0],
            }
        }
    )


# ------------------------------------------------------------------ favoritos
@bp.get("/favorites")
@login_required
def favorites():
    rows = query_all("SELECT product FROM favorites WHERE user_id = ?", (g.user["id"],))
    return jsonify({"favorites": [r["product"] for r in rows]})


@bp.put("/favorites/<product>")
@login_required
def favorite_add(product: str):
    if product not in PRODUCTS:
        return api_error("Producto desconocido.", 404)
    execute(
        "INSERT OR IGNORE INTO favorites (user_id, product, created_at) VALUES (?, ?, ?)",
        (g.user["id"], product, now()),
    )
    return jsonify({"ok": True})


@bp.delete("/favorites/<product>")
@login_required
def favorite_del(product: str):
    execute("DELETE FROM favorites WHERE user_id = ? AND product = ?", (g.user["id"], product))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ contacto
@bp.post("/contact")
@limit("contact", 5, 3600)
def contact():
    data = json_body()
    if data.get("website"):  # honeypot
        return jsonify({"ok": True}), 202
    name, email, body = data.get("name"), norm_email(data.get("email")), data.get("message")
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 60:
        return api_error("Escribe tu nombre.", 400)
    if not valid_email(email):
        return api_error("Escribe un correo válido.", 400)
    if not isinstance(body, str) or not 10 <= len(body.strip()) <= 2000:
        return api_error("El mensaje debe tener entre 10 y 2000 caracteres.", 400)
    execute(
        "INSERT INTO messages (name, email, body, ip, created_at) VALUES (?, ?, ?, ?, ?)",
        (name.strip(), email, body.strip(), client_ip(), now()),
    )
    audit("contacto", 202, email)
    return jsonify({"ok": True, "message": "¡Gracias! Te responderemos pronto."}), 202


# ------------------------------------------------------------------ newsletter (doble opt-in)
@bp.post("/newsletter")
@limit("newsletter", 5, 3600)
def newsletter():
    email = norm_email(json_body().get("email"))
    if not valid_email(email):
        return api_error("Escribe un correo válido.", 400)
    extra: dict = {}
    row = query_one("SELECT confirmed FROM newsletter WHERE email = ?", (email,))
    if not row or not row["confirmed"]:
        token = new_token(24)
        execute(
            "INSERT INTO newsletter (email, token_hash, created_at) VALUES (?, ?, ?)"
            " ON CONFLICT(email) DO UPDATE SET token_hash = excluded.token_hash",
            (email, sha256(token), now()),
        )
        link = f"{public_url()}/?newsletter={token}#home"
        mailer.send(
            email,
            "Confirma tu suscripción a SYNTHLAB",
            f"Confirma que quieres recibir novedades:\n{link}\n\nSi no lo has pedido, ignóralo.",
        )
        if current_app.config["EXPOSE_DEV_LINKS"]:
            extra["dev_link"] = link
    return jsonify({"ok": True, "message": "Revisa tu correo para confirmar la suscripción.", **extra}), 202


@bp.post("/newsletter/confirm")
@limit("newsletter-confirm", 20, 3600)
def newsletter_confirm():
    token = json_body().get("token")
    if not isinstance(token, str) or len(token) > 100:
        return api_error("Enlace no válido.", 400)
    cur = execute(
        "UPDATE newsletter SET confirmed = 1, token_hash = '' WHERE token_hash = ? AND confirmed = 0", (sha256(token),)
    )
    if not cur.rowcount:
        return api_error("Enlace no válido o ya usado.", 400)
    return jsonify({"ok": True, "message": "Suscripción confirmada. ¡Bienvenido!"})

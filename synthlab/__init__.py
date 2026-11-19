"""SYNTHLAB — fábrica de la aplicación Flask."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import click
from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from . import account, admin, api, auth, security
from .config import load_config
from .db import close_db, connect, init_db

__version__ = "1.0.0"


def create_app(overrides: dict | None = None) -> Flask:
    cfg = load_config()
    if overrides:
        cfg.update(overrides)
    frontend = Path(cfg["FRONTEND_DIR"])

    app = Flask(__name__, static_folder=str(frontend / "static"), static_url_path="/static")
    app.config.update(cfg)
    app.json.sort_keys = False
    logging.basicConfig(level=logging.INFO if cfg["DEV"] else logging.WARNING)

    if cfg["TRUSTED_PROXIES"]:
        n = cfg["TRUSTED_PROXIES"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)  # type: ignore[method-assign]

    if not cfg["DEV"] and cfg["MAIL_BACKEND"] == "console":
        app.logger.warning("MAIL_BACKEND=console en producción: los enlaces de activación irán al log.")

    init_db(cfg["DATABASE"])
    app.teardown_appcontext(close_db)
    security.register(app)
    for bp in (auth.bp, account.bp, api.bp, admin.bp):
        app.register_blueprint(bp)

    # --------------------------------------------------------- frontend
    # Sólo se sirven index.html y /static: nunca el resto del repositorio.
    @app.get("/")
    def index() -> Response:
        resp = send_from_directory(frontend, "index.html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.get("/robots.txt")
    def robots() -> Response:
        return Response("User-agent: *\nDisallow: /api/\n", mimetype="text/plain")

    @app.get("/.well-known/security.txt")
    def security_txt() -> Response:
        expires = time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(time.time() + 180 * 86400))
        body = f"Contact: {security.public_url()}/#about\nExpires: {expires}\nPreferred-Languages: es, en\n"
        return Response(body, mimetype="text/plain")

    # --------------------------------------------------------- errores (sin trazas al cliente)
    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description or exc.name}), exc.code
        return exc

    @app.errorhandler(Exception)
    def unhandled(exc: Exception):
        app.logger.exception("Error no controlado")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Error interno."}), 500
        return Response("Error interno.", status=500, mimetype="text/plain")

    # --------------------------------------------------------- CLI
    @app.cli.command("create-admin")
    @click.option("--email", required=True)
    @click.option("--name", default="Admin")
    @click.password_option()
    def create_admin(email: str, name: str, password: str) -> None:
        """Crea (o promueve) un administrador."""
        from .db import now
        from .passwords import hash_password, policy_errors

        err = policy_errors(password, email=email, name=name)
        if err:
            raise click.ClickException(err)
        con = connect(app.config["DATABASE"])
        ts = now()
        con.execute(
            "INSERT INTO users (email, name, password_hash, role, email_verified, created_at, updated_at,"
            " password_changed_at) VALUES (?, ?, ?, 'admin', 1, ?, ?, ?)"
            " ON CONFLICT(email) DO UPDATE SET role = 'admin', password_hash = excluded.password_hash,"
            " email_verified = 1",
            (email.strip().lower(), name, hash_password(password), ts, ts, ts),
        )
        con.close()
        click.echo(f"Administrador listo: {email}. Activa 2FA en «Mi cuenta» antes de usar el panel.")

    @app.cli.command("cleanup")
    def cleanup() -> None:
        """Purga sesiones caducadas, tokens usados, rate-limits viejos y auditoría > 180 días."""
        from .db import now

        con = connect(app.config["DATABASE"])
        ts = now()
        con.execute(
            "DELETE FROM sessions WHERE last_seen < ? OR created_at < ?",
            (ts - app.config["SESSION_IDLE_MINUTES"] * 60, ts - app.config["SESSION_ABSOLUTE_HOURS"] * 3600),
        )
        con.execute("DELETE FROM tokens WHERE expires_at < ? OR used_at IS NOT NULL", (ts,))
        con.execute("DELETE FROM rate_limits WHERE window_start < ?", (ts - 86400,))
        con.execute("DELETE FROM audit_log WHERE ts < ?", (ts - 180 * 86400,))
        con.close()
        click.echo("Limpieza completada.")

    return app

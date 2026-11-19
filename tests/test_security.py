from __future__ import annotations

import json

import pytest

from synthlab import create_app

from .conftest import PASSWORD, Api

STEPS = [[1, 0, 0, 0] * 4, [0] * 16, [0, 0, 1, 0] * 4, [0] * 16]


def test_security_headers(api):
    r = api.get("/")
    assert r.status_code == 200
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp.split("style-src-attr")[0]
    assert "frame-ancestors 'none'" in csp
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert api.get("/api/health").headers["Cache-Control"] == "no-store"


def test_frontend_has_no_inline_script(api):
    html = api.get("/").get_data(as_text=True)
    assert "<script>" not in html and "<style>" not in html


def test_repo_files_not_exposed(api):
    for path in [
        "/pyproject.toml",
        "/synthlab/config.py",
        "/instance/synthlab.db",
        "/.env",
        "/static/../pyproject.toml",
        "/login-sql/app.py",
    ]:
        assert api.get(path).status_code == 404, path


def test_csrf_required(app, make_user):
    a = make_user()
    r = a.post("/api/patterns", {"name": "x", "bpm": 100, "steps": STEPS}, csrf=False)
    assert r.status_code == 403
    r = a.c.post("/api/patterns", json={"name": "x", "bpm": 100, "steps": STEPS}, headers={"X-CSRF-Token": "falso"})
    assert r.status_code == 403


def test_cross_site_requests_blocked(make_user):
    a = make_user()
    r = a.c.post(
        "/api/patterns",
        json={"name": "x", "bpm": 100, "steps": STEPS},
        headers={"X-CSRF-Token": a.csrf, "Sec-Fetch-Site": "cross-site"},
    )
    assert r.status_code == 403
    r = a.c.post(
        "/api/patterns",
        json={"name": "x", "bpm": 100, "steps": STEPS},
        headers={"X-CSRF-Token": a.csrf, "Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_form_posts_rejected(make_user):
    a = make_user()
    r = a.c.post("/api/auth/logout", data={"x": 1}, headers={"X-CSRF-Token": a.csrf})
    assert r.status_code == 415


def test_idor_patterns(app, make_user):
    ana = make_user()
    pid = ana.post("/api/patterns", {"name": "Privado", "bpm": 120, "steps": STEPS}).get_json()["pattern"]["id"]
    eve = make_user(email="eve@example.com", name="Eve Mallory")
    assert eve.get(f"/api/patterns/{pid}").status_code == 404
    assert eve.put(f"/api/patterns/{pid}", {"name": "pwned", "bpm": 100, "steps": STEPS}).status_code == 404
    assert eve.delete(f"/api/patterns/{pid}").status_code == 404
    assert eve.post(f"/api/patterns/{pid}/share").status_code == 404
    assert ana.get(f"/api/patterns/{pid}").get_json()["pattern"]["name"] == "Privado"


def test_pattern_validation(make_user):
    a = make_user()
    bad = [
        {"name": "", "bpm": 100, "steps": STEPS},
        {"name": "x", "bpm": 999, "steps": STEPS},
        {"name": "x", "bpm": True, "steps": STEPS},
        {"name": "x", "bpm": 100, "steps": [[2] * 16] * 4},
        {"name": "x", "bpm": 100, "steps": [[0] * 15] * 4},
        {"name": "x", "bpm": 100, "steps": "DROP TABLE"},
    ]
    for body in bad:
        assert a.post("/api/patterns", body).status_code == 400, body


def test_xss_payload_stored_as_data(make_user):
    a = make_user()
    payload = "<img src=x onerror=alert(1)>"
    r = a.post("/api/patterns", {"name": payload, "bpm": 100, "steps": STEPS})
    assert r.status_code == 201
    assert r.headers["Content-Type"].startswith("application/json")  # nunca HTML


def test_sqli_in_admin_search_is_inert(app, make_user):
    adm = make_user(email="root@example.com", name="Root Admin")
    from synthlab.db import connect

    con = connect(app.config["DATABASE"])
    con.execute("UPDATE users SET role = 'admin' WHERE email = 'root@example.com'")
    adm.post("/api/auth/login", {"email": "root@example.com", "password": PASSWORD})
    r = adm.get("/api/admin/users?q=' OR 1=1 --")
    assert r.status_code == 200 and r.get_json()["users"] == []
    r = adm.get("/api/admin/users?q=%")  # comodín escapado: literal
    assert r.get_json()["users"] == []


def test_shared_pattern_public_readonly(app, make_user):
    a = make_user()
    pid = a.post("/api/patterns", {"name": "Compartido", "bpm": 90, "steps": STEPS}).get_json()["pattern"]["id"]
    slug = a.post(f"/api/patterns/{pid}/share", {"enabled": True}).get_json()["shared"]
    anon = Api(app.test_client())
    r = anon.get(f"/api/shared/{slug}")
    assert r.status_code == 200 and r.get_json()["pattern"]["author"] == "Ana"
    assert "email" not in json.dumps(r.get_json())
    a.post(f"/api/patterns/{pid}/share", {"enabled": False})
    assert anon.get(f"/api/shared/{slug}").status_code == 404


def test_admin_requires_role(make_user):
    a = make_user()
    assert a.get("/api/admin/stats").status_code == 403
    anon_status = Api(a.c.application.test_client()).get("/api/admin/stats").status_code
    assert anon_status == 401


def test_admin_requires_mfa_when_enforced(app, make_user):
    app.config["ADMIN_REQUIRE_MFA"] = True
    adm = make_user(email="root@example.com", name="Root Admin")
    from synthlab.db import connect

    connect(app.config["DATABASE"]).execute("UPDATE users SET role = 'admin'")
    r = adm.get("/api/admin/stats")
    assert r.status_code == 403 and r.get_json()["code"] == "mfa_required"


def test_rate_limit_login(app, make_user):
    make_user(login=False)
    app.config["RATELIMIT_DISABLED"] = False
    a = Api(app.test_client())
    codes = [a.post("/api/auth/login", {"email": "x@example.com", "password": "x" * 12}).status_code for _ in range(12)]
    assert codes[-1] == 429


def test_audit_log_written(app, make_user):
    a = make_user()
    a.post("/api/auth/login", {"email": "ana@example.com", "password": "mala-contraseña-1"})
    with open(app.config["SECURITY_LOG"], encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh]
    assert {"registro", "login_ok", "login_fallido"} <= {e["evento"] for e in events}
    assert set(events[0]) == {"ts", "app", "evento", "usuario", "ip", "metodo", "ruta", "estado", "detalle"}
    with open(app.config["SECURITY_LOG"], encoding="utf-8") as fh:
        raw = fh.read()
    assert PASSWORD not in raw and "mala-contraseña-1" not in raw


def test_production_requires_secret(monkeypatch):
    monkeypatch.setenv("SYNTHLAB_ENV", "production")
    monkeypatch.delenv("SYNTHLAB_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


def test_production_cookies_secure(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNTHLAB_ENV", "production")
    monkeypatch.setenv("SYNTHLAB_SECRET_KEY", "k" * 64)
    monkeypatch.setenv("SYNTHLAB_PUBLIC_URL", "https://synthlab.example")
    monkeypatch.setenv("SYNTHLAB_DATABASE", str(tmp_path / "p.db"))
    monkeypatch.setenv("SYNTHLAB_SECURITY_LOG", str(tmp_path / "p.log"))
    app = create_app()
    assert app.config["SESSION_COOKIE"].startswith("__Host-")
    r = app.test_client().get("/api/csrf", base_url="https://synthlab.example")
    assert "Secure" in r.headers["Set-Cookie"]
    assert "max-age=63072000" in r.headers["Strict-Transport-Security"]


def test_contact_and_newsletter(api):
    assert (
        api.post(
            "/api/contact", {"name": "Leo", "email": "leo@example.com", "message": "Hola, me encanta el laboratorio."}
        ).status_code
        == 202
    )
    assert api.post("/api/contact", {"name": "L", "email": "no", "message": "x"}).status_code == 400
    from .conftest import link_token

    assert api.post("/api/newsletter", {"email": "leo@example.com"}).status_code == 202
    tok = link_token()
    assert api.post("/api/newsletter/confirm", {"token": tok}).status_code == 200
    assert api.post("/api/newsletter/confirm", {"token": tok}).status_code == 400


def test_favorites_allowlist(make_user):
    a = make_user()
    assert a.put("/api/favorites/helix-one").status_code == 200
    assert a.put("/api/favorites/../../etc").status_code == 404
    assert a.get("/api/favorites").get_json()["favorites"] == ["helix-one"]

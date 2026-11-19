from __future__ import annotations

import json

from synthlab import mailer, totp
from synthlab.db import connect

from .conftest import PASSWORD, Api, link_token


def test_register_verify_login_logout(api):
    r = api.post("/api/auth/register", {"email": "Ana@Example.com", "name": "Ana", "password": PASSWORD})
    assert r.status_code == 202
    # sin verificar no entra
    r = api.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 403 and r.get_json()["code"] == "unverified"
    assert api.post("/api/auth/verify", {"token": link_token()}).status_code == 200
    r = api.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert api.get("/api/me").get_json()["user"]["email"] == "ana@example.com"
    assert api.post("/api/auth/logout").status_code == 200
    assert api.get("/api/me").status_code == 401


def test_verify_token_single_use(api):
    api.post("/api/auth/register", {"email": "b@example.com", "name": "Bea", "password": PASSWORD})
    tok = link_token()
    assert api.post("/api/auth/verify", {"token": tok}).status_code == 200
    assert api.post("/api/auth/verify", {"token": tok}).status_code == 400


def test_password_stored_as_argon2id(app, make_user):
    make_user()
    con = connect(app.config["DATABASE"])
    h = con.execute("SELECT password_hash FROM users").fetchone()[0]
    assert h.startswith("$argon2id$") and PASSWORD not in h


def test_password_policy(api):
    for bad in ["corta", "password1234", "aaaaaaaaaaaaaaa", "x" * 200]:
        r = api.post("/api/auth/register", {"email": "c@example.com", "name": "Carla", "password": bad})
        assert r.status_code == 400
    r = api.post("/api/auth/register", {"email": "carla@example.com", "name": "Carla", "password": "carla-suena-bien"})
    assert r.status_code == 400  # contiene el correo


def test_no_user_enumeration(api, make_user):
    make_user()
    mailer.OUTBOX.clear()
    dup = api.post("/api/auth/register", {"email": "ana@example.com", "name": "Otra", "password": PASSWORD})
    new = api.post("/api/auth/register", {"email": "nuevo@example.com", "name": "Nuevo", "password": PASSWORD})
    assert dup.status_code == new.status_code == 202
    assert dup.get_json()["message"] == new.get_json()["message"]
    bad_pw = api.post("/api/auth/login", {"email": "ana@example.com", "password": "incorrecta-123456"})
    no_user = api.post("/api/auth/login", {"email": "nadie@example.com", "password": "incorrecta-123456"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.get_json() == no_user.get_json()
    f1 = api.post("/api/auth/forgot", {"email": "ana@example.com"}).get_json()["message"]
    f2 = api.post("/api/auth/forgot", {"email": "nadie@example.com"}).get_json()["message"]
    assert f1 == f2


def test_lockout_after_failures(app, make_user):
    make_user(login=False)
    a = Api(app.test_client())
    for _ in range(app.config["LOCKOUT_THRESHOLD"]):
        a.post("/api/auth/login", {"email": "ana@example.com", "password": "mala-contraseña-1"})
    r = a.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 401  # bloqueada aunque la contraseña sea buena
    assert any("bloqueada" in m["Subject"] for m in mailer.OUTBOX)


def test_password_reset_revokes_sessions(app, make_user):
    victim = make_user()
    other = Api(app.test_client())
    other.post("/api/auth/forgot", {"email": "ana@example.com"})
    tok = link_token()
    assert other.post("/api/auth/reset", {"token": tok, "password": "corta"}).status_code == 400
    r = other.post("/api/auth/reset", {"token": tok, "password": "Nueva-Clave-De-Estudio-9"})
    assert r.status_code == 200
    assert other.post("/api/auth/reset", {"token": tok, "password": "Otra-Clave-De-Estudio-9"}).status_code == 400
    assert victim.get("/api/me").status_code == 401  # sesión antigua revocada
    r = other.post("/api/auth/login", {"email": "ana@example.com", "password": "Nueva-Clave-De-Estudio-9"})
    assert r.status_code == 200


def test_session_cookie_flags(app, api):
    api.post("/api/auth/register", {"email": "d@example.com", "name": "Dani", "password": PASSWORD})
    api.post("/api/auth/verify", {"token": link_token()})
    r = api.post("/api/auth/login", {"email": "d@example.com", "password": PASSWORD})
    cookies = r.headers.getlist("Set-Cookie")
    sid = next(c for c in cookies if c.startswith(app.config["SESSION_COOKIE"]))
    assert "HttpOnly" in sid and "SameSite=Strict" in sid


def test_session_rotation_on_login(app, make_user):
    a = make_user(login=False)
    a.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    first = a.c.get_cookie(app.config["SESSION_COOKIE"]).value
    a.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    assert a.c.get_cookie(app.config["SESSION_COOKIE"]).value != first


def test_mfa_flow(app, make_user):
    a = make_user()
    assert a.post("/api/me/2fa/setup", {"password": "mala"}).status_code == 401
    secret = a.post("/api/me/2fa/setup", {"password": PASSWORD}).get_json()["secret"]
    assert a.post("/api/me/2fa/enable", {"code": "000000"}).status_code == 400
    r = a.post("/api/me/2fa/enable", {"code": totp.current_code(secret)})
    codes = r.get_json()["recovery_codes"]
    assert len(codes) == 8
    a.post("/api/auth/logout")
    a.c.get("/api/csrf")
    a.csrf = a.c.get("/api/csrf").get_json()["csrf"]
    r = a.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    assert r.get_json()["mfa_required"] is True
    assert a.get("/api/me").status_code == 401  # aún no hay sesión
    mfa_token = r.get_json()["mfa_token"]
    assert a.post("/api/auth/login/mfa", {"mfa_token": mfa_token, "code": "123456"}).status_code == 401
    r = a.post("/api/auth/login/mfa", {"mfa_token": mfa_token, "code": codes[0]})
    assert r.status_code == 200
    # el código de recuperación es de un solo uso
    a.post("/api/auth/logout")
    a.csrf = a.c.get("/api/csrf").get_json()["csrf"]
    t = a.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD}).get_json()["mfa_token"]
    assert a.post("/api/auth/login/mfa", {"mfa_token": t, "code": codes[0]}).status_code == 401


def test_totp_replay_rejected():
    s = totp.new_secret()
    code = totp.current_code(s, at=1_000_000)
    step = totp.verify(s, code, None, at=1_000_000)
    assert step is not None
    assert totp.verify(s, code, step, at=1_000_000) is None


def test_delete_account_requires_password_and_cascades(app, make_user):
    a = make_user()
    a.post("/api/patterns", {"name": "Groove", "bpm": 100, "steps": [[0] * 16] * 4})
    assert a.delete("/api/me", {"password": "mala"}).status_code == 401
    assert a.delete("/api/me", {"password": PASSWORD}).status_code == 200
    con = connect(app.config["DATABASE"])
    assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM patterns").fetchone()[0] == 0


def test_export_contains_user_data(make_user):
    a = make_user()
    a.put("/api/favorites/helix-one")
    data = json.loads(a.get("/api/me/export").data)
    assert data["perfil"]["email"] == "ana@example.com" and data["favoritos"] == ["helix-one"]
    assert "password_hash" not in json.dumps(data)


def test_change_password_revokes_other_sessions(app, make_user):
    a = make_user()
    b = Api(app.test_client())
    b.post("/api/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    assert b.get("/api/me").status_code == 200
    r = a.post("/api/me/password", {"current": PASSWORD, "new": "Otra-Clave-Mucho-Mejor-1"})
    assert r.status_code == 200
    assert a.get("/api/me").status_code == 200
    assert b.get("/api/me").status_code == 401

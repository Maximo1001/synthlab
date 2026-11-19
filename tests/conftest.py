from __future__ import annotations

import pytest

from synthlab import create_app, mailer

PASSWORD = "Sintetizador-Modular-77"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNTHLAB_ENV", "testing")
    app = create_app(
        {
            "DATABASE": str(tmp_path / "test.db"),
            "SECURITY_LOG": str(tmp_path / "seguridad.log"),
            "RATELIMIT_DISABLED": True,
            "PUBLIC_URL": "http://localhost",
            "ADMIN_REQUIRE_MFA": False,
        }
    )
    mailer.OUTBOX.clear()
    yield app


class Api:
    """Cliente que se comporta como el frontend: pide /api/csrf y envía JSON + cabecera."""

    def __init__(self, client):
        self.c = client
        self.csrf = client.get("/api/csrf").get_json()["csrf"]

    def _send(self, method, url, json=None, csrf=True):
        headers = {"X-CSRF-Token": self.csrf} if csrf else {}
        r = self.c.open(url, method=method, json=json if json is not None else {}, headers=headers)
        body = r.get_json(silent=True) or {}
        if isinstance(body, dict) and body.get("csrf"):
            self.csrf = body["csrf"]
        return r

    def get(self, url):
        return self.c.get(url)

    def post(self, url, json=None, **kw):
        return self._send("POST", url, json, **kw)

    def put(self, url, json=None, **kw):
        return self._send("PUT", url, json, **kw)

    def patch(self, url, json=None, **kw):
        return self._send("PATCH", url, json, **kw)

    def delete(self, url, json=None, **kw):
        return self._send("DELETE", url, json, **kw)


@pytest.fixture
def api(app):
    return Api(app.test_client())


def link_token(app_outbox_index=-1) -> str:
    body = mailer.OUTBOX[app_outbox_index].get_content()
    for word in body.split():
        if "?verify=" in word or "?reset=" in word or "?newsletter=" in word:
            return word.split("=", 1)[1].split("#", 1)[0]
    raise AssertionError("sin enlace en el correo")


@pytest.fixture
def make_user(app):
    def _make(email="ana@example.com", name="Ana López", password=PASSWORD, login=True):
        a = Api(app.test_client())
        r = a.post("/api/auth/register", {"email": email, "name": name, "password": password})
        assert r.status_code == 202, r.get_json()
        assert a.post("/api/auth/verify", {"token": link_token()}).status_code == 200
        if login:
            r = a.post("/api/auth/login", {"email": email, "password": password})
            assert r.status_code == 200, r.get_json()
        return a

    return _make

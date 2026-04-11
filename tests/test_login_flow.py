from fastapi.testclient import TestClient
import app.main as main_module


def test_index_allows_anonymous_with_env(monkeypatch):
    monkeypatch.setenv("CHEATER_ALLOW_ANON", "1")
    client = TestClient(main_module.app)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    assert "cheter" in resp.text


def test_login_post_success_sets_cookie(monkeypatch):
    monkeypatch.setattr(main_module, "check_credentials", lambda u, p: True)
    client = TestClient(main_module.app)
    resp = client.post("/login", data={"username": "toru", "password": "jejeje"}, follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "username=" in resp.headers.get("set-cookie", "")


def test_login_post_invalid(monkeypatch):
    monkeypatch.setattr(main_module, "check_credentials", lambda u, p: False)
    client = TestClient(main_module.app)
    resp = client.post("/login", data={"username": "bad", "password": "x"}, follow_redirects=False)
    assert resp.status_code == 400
    assert "ID またはパスワードが違います" in resp.text

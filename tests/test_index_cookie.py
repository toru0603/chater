from fastapi.testclient import TestClient
import app.main as main_module


def test_login_get_redirects_when_logged_in():
    client = TestClient(main_module.app)
    client.cookies.set("username", "toru")
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers.get("location", "") == "/"


def test_index_with_cookie_shows_user():
    client = TestClient(main_module.app)
    client.cookies.set("username", "toru")
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    assert "toru" in resp.text

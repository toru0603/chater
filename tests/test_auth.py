import app.auth as auth


def test_check_credentials_tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    monkeypatch.setattr(auth, "DB_PATH", db_path)
    # Initialize a fresh DB at the tmp path
    auth.init_db()
    assert auth.check_credentials("toru", "jejeje")
    assert not auth.check_credentials("toru", "wrong")
    assert not auth.check_credentials("noone", "pw")


def test_plaintext_fallback(tmp_path, monkeypatch):
    db_path = tmp_path / "users_plain.db"
    monkeypatch.setattr(auth, "DB_PATH", db_path)
    # Force plaintext fallback
    monkeypatch.setattr(auth, "BCRYPT_AVAILABLE", False)
    auth.init_db()
    assert auth.check_credentials("toru", "jejeje")

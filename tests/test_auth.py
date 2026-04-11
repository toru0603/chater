from __future__ import annotations

import boto3
import pytest
from botocore.exceptions import ClientError

import app.auth as auth


def _make_table(name: str, region: str = "us-east-1") -> object:
    return boto3.resource("dynamodb", region_name=region).create_table(
        TableName=name,
        AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )


def _patch_auth(monkeypatch, table_name: str = "TestUsers", endpoint: str | None = None) -> None:
    monkeypatch.setattr(auth, "_TABLE_NAME", table_name)
    monkeypatch.setattr(auth, "_DYNAMODB_ENDPOINT", endpoint)
    monkeypatch.setattr(auth, "_DEFAULT_REGION", "us-east-1")


def test_check_credentials_dynamodb(monkeypatch):
    """Credentials round-trip via moto-mocked DynamoDB."""
    from moto import mock_aws

    with mock_aws():
        _patch_auth(monkeypatch)
        _make_table("TestUsers")
        auth.init_db()

        assert auth.check_credentials("toru", "jejeje")
        assert not auth.check_credentials("toru", "wrong")
        assert not auth.check_credentials("noone", "pw")


def test_plaintext_fallback(monkeypatch):
    """Credentials work when bcrypt is unavailable (plaintext fallback)."""
    from moto import mock_aws

    with mock_aws():
        _patch_auth(monkeypatch, table_name="TestUsersPlain")
        monkeypatch.setattr(auth, "BCRYPT_AVAILABLE", False)
        _make_table("TestUsersPlain")
        auth.init_db()

        assert auth.check_credentials("toru", "jejeje")


def test_init_db_with_dynamodb_endpoint(monkeypatch):
    """init_db creates the table when DYNAMODB_ENDPOINT is set (local dev path)."""
    from unittest.mock import MagicMock, patch

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_table.put_item.return_value = {}

    _patch_auth(monkeypatch, table_name="LocalUsers", endpoint="http://localhost:8001")

    with patch("boto3.client", return_value=mock_client), patch.object(auth, "_get_table", return_value=mock_table):
        auth.init_db()

    mock_client.create_table.assert_called_once()
    mock_table.put_item.assert_called_once()


def test_init_db_table_already_exists(monkeypatch):
    """init_db handles ResourceInUseException silently when table already exists."""
    from unittest.mock import MagicMock, patch

    error_response = {"Error": {"Code": "ResourceInUseException", "Message": "Table already exists"}}
    mock_client = MagicMock()
    mock_client.create_table.side_effect = ClientError(error_response, "CreateTable")
    mock_table = MagicMock()
    mock_table.put_item.return_value = {}

    _patch_auth(monkeypatch, table_name="ExistingUsers", endpoint="http://localhost:8001")

    with patch("boto3.client", return_value=mock_client), patch.object(auth, "_get_table", return_value=mock_table):
        auth.init_db()  # Should not raise

    mock_table.put_item.assert_called_once()


def test_init_db_user_already_seeded(monkeypatch):
    """init_db silently ignores ConditionalCheckFailedException when user already seeded."""
    from moto import mock_aws

    with mock_aws():
        _patch_auth(monkeypatch)
        _make_table("TestUsers")
        auth.init_db()  # Seeds the user
        auth.init_db()  # User already exists → ConditionalCheckFailedException → no-op

        assert auth.check_credentials("toru", "jejeje")


def test_check_credentials_get_item_error(monkeypatch):
    """check_credentials returns False when DynamoDB get_item raises ClientError."""
    from moto import mock_aws
    from unittest.mock import MagicMock, patch

    with mock_aws():
        _patch_auth(monkeypatch)
        _make_table("TestUsers")

        error_response = {"Error": {"Code": "InternalServerError", "Message": "boom"}}
        with patch.object(auth, "_get_table") as mock_table:
            mock_table.return_value.get_item.side_effect = ClientError(error_response, "GetItem")
            assert not auth.check_credentials("toru", "jejeje")


def test_check_credentials_bad_bcrypt_hash(monkeypatch):
    """check_credentials returns False when bcrypt.checkpw raises an exception."""
    from moto import mock_aws

    with mock_aws():
        _patch_auth(monkeypatch)
        _make_table("TestUsers")
        auth.init_db()

        # Corrupt the stored hash so bcrypt.checkpw raises ValueError
        boto3.resource("dynamodb", region_name="us-east-1").Table("TestUsers").put_item(
            Item={"username": "toru", "password_hash": "not-a-valid-bcrypt-hash"},
        )
        assert not auth.check_credentials("toru", "jejeje")

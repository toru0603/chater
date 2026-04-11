import app.auth as auth


def test_check_credentials_dynamodb(monkeypatch):
    """Credentials round-trip via moto-mocked DynamoDB."""
    import boto3
    from moto import mock_aws

    with mock_aws():
        monkeypatch.setattr(auth, "_TABLE_NAME", "TestUsers")
        monkeypatch.setattr(auth, "_DYNAMODB_ENDPOINT", None)
        monkeypatch.setattr(auth, "_DEFAULT_REGION", "us-east-1")

        # Bootstrap the mocked table
        boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="TestUsers",
            AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        auth.init_db()

        assert auth.check_credentials("toru", "jejeje")
        assert not auth.check_credentials("toru", "wrong")
        assert not auth.check_credentials("noone", "pw")


def test_plaintext_fallback(monkeypatch):
    """Credentials work when bcrypt is unavailable (plaintext fallback)."""
    import boto3
    from moto import mock_aws

    with mock_aws():
        monkeypatch.setattr(auth, "_TABLE_NAME", "TestUsersPlain")
        monkeypatch.setattr(auth, "_DYNAMODB_ENDPOINT", None)
        monkeypatch.setattr(auth, "_DEFAULT_REGION", "us-east-1")
        monkeypatch.setattr(auth, "BCRYPT_AVAILABLE", False)

        boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="TestUsersPlain",
            AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        auth.init_db()

        assert auth.check_credentials("toru", "jejeje")

from __future__ import annotations

import logging
import os

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except Exception:
    bcrypt = None
    BCRYPT_AVAILABLE = False

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_TABLE_NAME = os.environ.get("USERS_TABLE", "ChaterUsers")
_DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")


def _get_dynamodb_kwargs() -> dict:
    kwargs: dict = {"region_name": _DEFAULT_REGION}
    if _DYNAMODB_ENDPOINT:
        kwargs["endpoint_url"] = _DYNAMODB_ENDPOINT
    return kwargs


def _get_table():
    dynamodb = boto3.resource("dynamodb", **_get_dynamodb_kwargs())
    return dynamodb.Table(_TABLE_NAME)


def init_db() -> None:
    """Ensure the ChaterUsers table exists (local only) and seed the default user."""
    if _DYNAMODB_ENDPOINT:
        # Local development: create the table if it doesn't exist yet
        client = boto3.client("dynamodb", **_get_dynamodb_kwargs())
        try:
            client.create_table(
                TableName=_TABLE_NAME,
                AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
                KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
                BillingMode="PAY_PER_REQUEST",
            )
            logger.info("Created DynamoDB table %s", _TABLE_NAME)
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("ResourceInUseException",):
                raise

    # Seed default user 'toru' if not present
    default_pw = "jejeje"
    if BCRYPT_AVAILABLE and bcrypt is not None:
        pw_hash = bcrypt.hashpw(default_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    else:
        pw_hash = default_pw

    try:
        table = _get_table()
        table.put_item(
            Item={"username": "toru", "password_hash": pw_hash},
            ConditionExpression="attribute_not_exists(username)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            logger.warning("init_db seed user failed: %s", e)


def check_credentials(username: str, password: str) -> bool:
    """Return True if username/password is valid according to ChaterUsers DynamoDB table."""
    table = _get_table()
    try:
        response = table.get_item(Key={"username": username})
    except ClientError:
        return False
    item = response.get("Item")
    if not item:
        return False
    stored = item.get("password_hash", "")
    if BCRYPT_AVAILABLE and bcrypt is not None:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    return password == stored


# Initialize DB on import — failures are non-fatal (e.g., in test environments)
try:
    init_db()
except Exception as exc:
    logger.warning("init_db failed on import: %s", exc)

"""
AWS Lambda handler for API Gateway WebSocket API.

Routes:
  $connect    - store connection in DynamoDB
  $disconnect - remove connection, notify peers
  $default    - route messages (join, leave, chat, offer, answer, candidate, audio, camera)

For local development, set DYNAMODB_ENDPOINT=http://localhost:8001 to use DynamoDB Local.
The module-level _local_sender can be overridden to inject a custom send function
(used by scripts/local_ws_server.py).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Callable, Optional

import boto3
from boto3.dynamodb.conditions import Key

CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "ChaterConnections")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
MAX_PARTICIPANTS = 2
DEFAULT_COLORS = [
    "#e11d48", "#f97316", "#f59e0b", "#10b981", "#06b6d4",
    "#3b82f6", "#8b5cf6", "#ec4899", "#6366f1", "#14b8a6",
]

# Can be overridden by local_ws_server.py for local development
_local_sender: Optional[Callable[[str, Any], None]] = None


def set_local_sender(fn: Callable[[str, Any], None]) -> None:
    global _local_sender
    _local_sender = fn


def _get_dynamodb():
    kwargs = {"endpoint_url": DYNAMODB_ENDPOINT} if DYNAMODB_ENDPOINT else {}
    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1"), **kwargs)


def _get_table():
    return _get_dynamodb().Table(CONNECTIONS_TABLE)


def _get_apigw_client(domain: str, stage: str):
    return boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{domain}/{stage}",
    )


def _assign_color(participant_id: str) -> str:
    return DEFAULT_COLORS[int(participant_id[:8], 16) % len(DEFAULT_COLORS)]


def _send(client_or_none, connection_id: str, data: Any, table) -> bool:
    """Send JSON to a connection. Returns False if connection is stale."""
    if _local_sender is not None:
        _local_sender(connection_id, data)
        return True
    try:
        client_or_none.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode("utf-8"),
        )
        return True
    except client_or_none.exceptions.GoneException:
        table.delete_item(Key={"connectionId": connection_id})
        return False


def _get_room_connections(table, room_code: str) -> list[dict]:
    resp = table.query(
        IndexName="RoomCodeIndex",
        KeyConditionExpression=Key("roomCode").eq(room_code),
    )
    return resp.get("Items", [])


# ── Route handlers ──────────────────────────────────────────────────────────


def _handle_connect(event: dict, connection_id: str, table) -> dict:
    qs = event.get("queryStringParameters") or {}
    room_code = qs.get("roomCode", "").strip()
    if not room_code:
        return {"statusCode": 400, "body": "roomCode query param required"}

    existing = _get_room_connections(table, room_code)
    if len(existing) >= MAX_PARTICIPANTS:
        return {"statusCode": 400, "body": "Room is full"}

    participant_id = uuid.uuid4().hex
    color = _assign_color(participant_id)
    role = "host" if not existing else "guest"

    table.put_item(Item={
        "connectionId": connection_id,
        "roomCode": room_code,
        "participantId": participant_id,
        "name": "Guest",
        "role": role,
        "color": color,
        "joinedAt": int(time.time()),
        "ttl": int(time.time()) + 86400,
    })
    return {"statusCode": 200}


def _handle_disconnect(event: dict, connection_id: str, table, apigw_client) -> dict:
    item = table.get_item(Key={"connectionId": connection_id}).get("Item")
    if not item:
        return {"statusCode": 200}

    table.delete_item(Key={"connectionId": connection_id})
    participant_id = item["participantId"]

    for peer in _get_room_connections(table, item["roomCode"]):
        _send(apigw_client, peer["connectionId"], {"type": "peer-left", "id": participant_id}, table)
        _send(apigw_client, peer["connectionId"], {
            "type": "participant-left",
            "id": participant_id,
            "name": item.get("name", "Guest"),
        }, table)

    return {"statusCode": 200}


def _handle_message(event: dict, connection_id: str, table, apigw_client) -> dict:
    try:
        message = json.loads(event.get("body") or "{}")
    except Exception:
        return {"statusCode": 400, "body": "Invalid JSON"}

    conn = table.get_item(Key={"connectionId": connection_id}).get("Item")
    if not conn:
        return {"statusCode": 400, "body": "Connection not found"}

    msg_type = message.get("type")

    if msg_type == "join":
        name = str(message.get("name") or "Guest").strip() or "Guest"
        table.update_item(
            Key={"connectionId": connection_id},
            UpdateExpression="SET #n = :n",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":n": name},
        )
        conn["name"] = name

        _send(apigw_client, connection_id, {
            "type": "joined",
            "room_code": conn["roomCode"],
            "participant_id": conn["participantId"],
            "role": conn["role"],
            "name": name,
            "color": conn["color"],
        }, table)

        others = [c for c in _get_room_connections(table, conn["roomCode"])
                  if c["connectionId"] != connection_id]
        if not others:
            _send(apigw_client, connection_id, {
                "type": "waiting",
                "room_code": conn["roomCode"],
                "message": f"room {conn['roomCode']} is waiting for a peer",
            }, table)
        else:
            _send(apigw_client, connection_id, {
                "type": "participants",
                "room_code": conn["roomCode"],
                "participants": [
                    {"id": p["participantId"], "name": p["name"],
                     "role": p["role"], "color": p["color"]}
                    for p in others
                ],
            }, table)
            for peer in others:
                _send(apigw_client, peer["connectionId"], {
                    "type": "participant-joined",
                    "room_code": conn["roomCode"],
                    "id": conn["participantId"],
                    "name": name,
                    "role": conn["role"],
                    "color": conn["color"],
                }, table)
        return {"statusCode": 200}

    if msg_type == "leave":
        return _handle_disconnect(event, connection_id, table, apigw_client)

    if msg_type == "chat":
        text = str(message.get("text") or "").strip()
        if text:
            for c in _get_room_connections(table, conn["roomCode"]):
                _send(apigw_client, c["connectionId"], {
                    "type": "chat",
                    "from": conn["participantId"],
                    "from_name": conn["name"],
                    "text": text,
                    "color": conn["color"],
                }, table)
        return {"statusCode": 200}

    if msg_type in ("audio", "camera"):
        enabled = message.get("enabled")
        for c in _get_room_connections(table, conn["roomCode"]):
            if c["connectionId"] != connection_id:
                _send(apigw_client, c["connectionId"], {
                    "type": msg_type,
                    "from": conn["participantId"],
                    "from_name": conn["name"],
                    "enabled": enabled,
                }, table)
        return {"statusCode": 200}

    if msg_type in ("offer", "answer", "candidate"):
        target_id = message.get("target")
        if target_id:
            room_conns = _get_room_connections(table, conn["roomCode"])
            target = next((c for c in room_conns if c["participantId"] == target_id), None)
            if target:
                _send(apigw_client, target["connectionId"], {
                    "type": "signal",
                    "signal_type": msg_type,
                    "data": message.get("data"),
                    "from": conn["participantId"],
                    "from_name": conn["name"],
                }, table)
        return {"statusCode": 200}

    return {"statusCode": 200}


# ── Lambda entry point ───────────────────────────────────────────────────────


def handler(event: dict, context: Any) -> dict:
    route = event["requestContext"]["routeKey"]
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    table = _get_table()
    apigw_client = _get_apigw_client(domain, stage) if _local_sender is None else None

    if route == "$connect":
        return _handle_connect(event, connection_id, table)
    if route == "$disconnect":
        return _handle_disconnect(event, connection_id, table, apigw_client)
    return _handle_message(event, connection_id, table, apigw_client)

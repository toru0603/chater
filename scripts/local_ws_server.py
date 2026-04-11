"""
Local WebSocket server that simulates API Gateway WebSocket behavior.

Uses ws_handler.py business logic with DynamoDB Local for state storage.
Requires the 'websockets' package: pip install websockets

Usage:
  docker-compose up dynamodb-local        # start DynamoDB Local
  ./scripts/init-dynamodb-local.sh        # create table (first time only)
  python scripts/local_ws_server.py       # start WS server on ws://localhost:8002

Then start the HTTP server in another terminal:
  WS_URL=ws://localhost:8002 uvicorn app.main:app --reload

Frontend connects to ws://localhost:8002?roomCode=1234
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

# Allow importing ws_handler from the project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../infra/cdk/src/handlers"))

import ws_handler  # noqa: E402

os.environ.setdefault("CONNECTIONS_TABLE", "ChaterConnections")
os.environ.setdefault("DYNAMODB_ENDPOINT", "http://localhost:8001")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-northeast-1")
# Dummy credentials for DynamoDB Local
os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    print("Install websockets: pip install websockets")
    sys.exit(1)

HOST = os.environ.get("WS_LOCAL_HOST", "localhost")
PORT = int(os.environ.get("WS_LOCAL_PORT", "8002"))

# connectionId -> websocket object (for sending back to clients)
_active_connections: dict[str, WebSocketServerProtocol] = {}


def _send_local(connection_id: str, data: object) -> None:
    """Called by ws_handler._send() instead of APIGW Management API."""
    ws = _active_connections.get(connection_id)
    if ws:
        asyncio.ensure_future(ws.send(json.dumps(data)))


ws_handler.set_local_sender(_send_local)


async def _handle_ws(websocket: WebSocketServerProtocol, path: str) -> None:
    # Parse roomCode from query string
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(f"ws://localhost{websocket.path}")
    qs = parse_qs(parsed.query)
    room_code = (qs.get("roomCode") or qs.get("roomcode") or [""])[0]

    connection_id = uuid.uuid4().hex
    _active_connections[connection_id] = websocket

    # Simulate $connect
    connect_event = {
        "requestContext": {
            "routeKey": "$connect",
            "connectionId": connection_id,
            "domainName": "localhost",
            "stage": "local",
        },
        "queryStringParameters": {"roomCode": room_code},
    }
    result = ws_handler.handler(connect_event, None)
    if result.get("statusCode") != 200:
        await websocket.close(1008, result.get("body", "rejected"))
        del _active_connections[connection_id]
        return

    try:
        async for raw in websocket:
            event = {
                "requestContext": {
                    "routeKey": "$default",
                    "connectionId": connection_id,
                    "domainName": "localhost",
                    "stage": "local",
                },
                "body": raw,
            }
            ws_handler.handler(event, None)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _active_connections.pop(connection_id, None)
        disconnect_event = {
            "requestContext": {
                "routeKey": "$disconnect",
                "connectionId": connection_id,
                "domainName": "localhost",
                "stage": "local",
            },
        }
        ws_handler.handler(disconnect_event, None)


async def main() -> None:
    print(f"Local WS server listening on ws://{HOST}:{PORT}")
    print(f"DynamoDB endpoint: {os.environ['DYNAMODB_ENDPOINT']}")
    async with websockets.serve(_handle_ws, HOST, PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())

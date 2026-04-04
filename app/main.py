from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .room_manager import RoomFullError, RoomManager


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="cheter")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
room_manager = RoomManager()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request, "app_name": "cheter"},
    )


@app.websocket("/ws/{room_code}")
async def websocket_room(websocket: WebSocket, room_code: str) -> None:
    await websocket.accept()

    participant_id = ""
    room_name = ""
    try:
        join_message = await websocket.receive_json()
        if join_message.get("type") != "join":
            await websocket.send_json({"type": "error", "message": "join message is required"})
            await websocket.close(code=1008)
            return

        room_name = str(join_message.get("name") or "Guest")
        participant, peer = await room_manager.add_participant(room_code, room_name, websocket)
        participant_id = participant.id

        await websocket.send_json(
            {
                "type": "joined",
                "room_code": room_code,
                "participant_id": participant.id,
                "role": participant.role,
                "name": room_name,
            }
        )

        if peer is None:
            await websocket.send_json(
                {
                    "type": "waiting",
                    "room_code": room_code,
                    "message": f"room {room_code} is waiting for a peer",
                }
            )
        else:
            await participant.websocket.send_json(
                {
                    "type": "matched",
                    "room_code": room_code,
                    "role": participant.role,
                    "peer_name": peer.name,
                    "peer_id": peer.id,
                }
            )
            await peer.websocket.send_json(
                {
                    "type": "matched",
                    "room_code": room_code,
                    "role": peer.role,
                    "peer_name": participant.name,
                    "peer_id": participant.id,
                }
            )

        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "leave":
                break

            if message_type in {"offer", "answer", "candidate"}:
                peer = await room_manager.get_peer(participant_id)
                if peer is None:
                    continue
                await peer.websocket.send_json(
                    {
                        "type": "signal",
                        "signal_type": message_type,
                        "data": message.get("data"),
                        "from": room_name,
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        if participant_id:
            peer, empty = await room_manager.remove_participant(participant_id)
            if peer is not None:
                try:
                    await peer.websocket.send_json({"type": "peer-left", "room_code": room_code})
                except Exception:
                    pass
            if not empty and room_name:
                try:
                    await websocket.close()
                except Exception:
                    pass

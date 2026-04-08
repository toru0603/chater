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
                "color": participant.color,
            }
        )

        if not peer:
            await websocket.send_json(
                {
                    "type": "waiting",
                    "room_code": room_code,
                    "message": f"room {room_code} is waiting for peers",
                }
            )
        else:
            # Inform both participants that they've been matched (1:1)
            await websocket.send_json(
                {
                    "type": "matched",
                    "room_code": room_code,
                    "peer": {"id": peer.id, "name": peer.name, "role": peer.role, "color": peer.color},
                }
            )
            try:
                await peer.websocket.send_json(
                    {
                        "type": "matched",
                        "room_code": room_code,
                        "peer": {"id": participant.id, "name": participant.name, "role": participant.role, "color": participant.color},
                    }
                )
            except Exception:
                pass

        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "leave":
                break

            # chat messages - broadcast to room
            if message_type == "chat":
                text = message.get("text", "")
                if not text:
                    continue
                participants = await room_manager.get_room_participants(room_code)
                for p in participants:
                    try:
                        await p.websocket.send_json(
                            {
                                "type": "chat",
                                "from": participant.id,
                                "from_name": participant.name,
                                "text": text,
                                "color": participant.color,
                            }
                        )
                    except Exception:
                        pass
                continue

            # camera on/off - notify peers about sender's camera state
            if message_type == "camera":
                enabled = bool(message.get("enabled"))
                participants = await room_manager.get_room_participants(room_code)
                for p in participants:
                    try:
                        await p.websocket.send_json(
                            {
                                "type": "camera",
                                "from": participant.id,
                                "from_name": participant.name,
                                "enabled": enabled,
                            }
                        )
                    except Exception:
                        pass
                continue

            if message_type in {"offer", "answer", "candidate"}:
                target_id = message.get("target")
                # If no target specified, and this is a 1:1 room, forward to the peer
                if not target_id:
                    target = await room_manager.get_peer(participant.id)
                    if not target:
                        continue
                else:
                    target = await room_manager.get_participant(target_id)
                    if not target:
                        continue
                await target.websocket.send_json(
                    {
                        "type": "signal",
                        "signal_type": message_type,
                        "data": message.get("data"),
                        "from": participant.id,
                        "from_name": participant.name,
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        if participant_id:
            # capture removed participant info before removal
            removed_info = await room_manager.get_participant(participant_id)
            remaining_peer, empty = await room_manager.remove_participant(participant_id)
            if remaining_peer is not None:
                try:
                    await remaining_peer.websocket.send_json(
                        {"type": "peer-left", "id": removed_info.id if removed_info else participant_id, "name": removed_info.name if removed_info else ""}
                    )
                except Exception:
                    pass
            # ensure websocket is closed
            try:
                await websocket.close()
            except Exception:
                pass

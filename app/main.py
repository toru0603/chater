from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .room_manager import RoomManager


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="cheter")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
room_manager = RoomManager()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    import os
    # Allow bypassing any auth/login flow for E2E/tests or local dev by setting CHEATER_ALLOW_ANON=1.
    # When enabled, always serve the application index (with #name input) so Playwright tests can proceed.
    if os.environ.get("CHEATER_ALLOW_ANON"):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"request": request, "app_name": "cheter"},
        )
    # Default behavior: render index (preserve existing behavior)
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
        participant, existing = await room_manager.add_participant(room_code, room_name, websocket)
        participant_id = participant.id
        peer = existing[0] if existing else None

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
                    "message": f"room {room_code} is waiting for a peer",
                }
            )
        else:
            # Send participants list to the newcomer and notify existing peer of new join
            # participants message is used by clients to initiate offers to existing participants
            try:
                await websocket.send_json(
                    {
                        "type": "participants",
                        "room_code": room_code,
                        "participants": [
                            {"id": p.id, "name": p.name, "role": p.role, "color": p.color}
                            for p in existing
                        ],
                    }
                )
            except Exception:
                pass
            try:
                if peer:
                    await peer.websocket.send_json(
                        {
                            "type": "participant-joined",
                            "id": participant.id,
                            "name": participant.name,
                            "role": participant.role,
                            "color": participant.color,
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

            # audio/camera toggle messages - broadcast to peers
            if message_type in {"audio", "camera"}:
                enabled = message.get("enabled")
                enabled_bool: bool | None = None
                # coerce string true/false to boolean
                if isinstance(enabled, str):
                    if enabled.lower() in ("true", "1", "yes", "on"):
                        enabled_bool = True
                    elif enabled.lower() in ("false", "0", "no", "off"):
                        enabled_bool = False
                    else:
                        enabled_bool = bool(enabled)
                else:
                    enabled_bool = bool(enabled) if enabled is not None else None

                participants = await room_manager.get_room_participants(room_code)
                for p in participants:
                    if p.id == participant.id:
                        continue
                    try:
                        await p.websocket.send_json(
                            {
                                "type": message_type,
                                "from": participant.id,
                                "from_name": participant.name,
                                "enabled": enabled_bool,
                            }
                        )
                    except Exception:
                        pass
                continue

            if message_type in {"offer", "answer", "candidate"}:
                target_id = message.get("target")
                target = None
                if target_id:
                    target = await room_manager.get_participant(target_id)
                else:
                    # No explicit target: try get_peer, but fallback to scanning room participants if get_peer raises
                    try:
                        target = await room_manager.get_peer(participant.id)
                    except Exception:
                        participants = await room_manager.get_room_participants(room_code)
                        peers = [p for p in participants if p.id != participant.id]
                        target = peers[0] if peers else None
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
            removed, remaining, empty = await room_manager.remove_participant(participant_id)
            peer = remaining[0] if remaining else None
            if peer is not None:
                try:
                    await peer.websocket.send_json({"type": "peer-left", "id": participant_id})
                except Exception:
                    pass
            # notify remaining participants about the departed participant
            if removed is not None:
                for p in remaining:
                    try:
                        await p.websocket.send_json(
                            {
                                "type": "participant-left",
                                "id": removed.id,
                                "name": removed.name,
                            }
                        )
                    except Exception:
                        pass
            # ensure websocket is closed
            try:
                await websocket.close()
            except Exception:
                pass

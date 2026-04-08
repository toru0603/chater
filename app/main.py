from __future__ import annotations

from pathlib import Path
import asyncio
import os

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .room_manager import RoomManager, RoomFullError

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
    participant = None
    try:
        join_message = await websocket.receive_json()
        if join_message.get("type") != "join":
            await websocket.send_json({"type": "error", "message": "join message is required"})
            await websocket.close(code=1008)
            return

        room_name = str(join_message.get("name") or "Guest")
        participant, existing = await room_manager.add_participant(room_code, room_name, websocket)
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

        if not existing:
            await websocket.send_json(
                {
                    "type": "waiting",
                    "room_code": room_code,
                    "message": f"room {room_code} is waiting for peers",
                }
            )
        else:
            # Build payloads
            participants_payload = [
                {"id": p.id, "name": p.name, "role": p.role, "color": p.color} for p in existing
            ]
            new_participant_payload = {"id": participant.id, "name": participant.name, "role": participant.role, "color": participant.color}

            # Send 'participants' to existing peers and the list of existing to the new participant concurrently
            try:
                tasks = []
                for p in existing:
                    payload = {
                        "type": "participants",
                        "room_code": room_code,
                        "participants": [new_participant_payload],
                    }
                    if os.environ.get('DEBUG_E2E'):
                        print(f"SERVER DEBUG: queue participants to existing {p.id} about {participant.id}")
                    tasks.append(asyncio.create_task(p.websocket.send_json(payload)))

                new_payload = {
                    "type": "participants",
                    "room_code": room_code,
                    "participants": participants_payload,
                }
                if os.environ.get('DEBUG_E2E'):
                    print(f"SERVER DEBUG: queue participants to new participant {participant.id} participants: {[p.id for p in existing]}")
                tasks.append(asyncio.create_task(websocket.send_json(new_payload)))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                if os.environ.get('DEBUG_E2E'):
                    print(f"SERVER DEBUG: participants send results: {results}")
            except Exception:
                if os.environ.get('DEBUG_E2E'):
                    print(f"SERVER DEBUG: participants send failed overall for {participant.id}")

            # Send 'matched' notifications concurrently
            try:
                tasks = []
                for p in existing:
                    payload = {
                        "type": "matched",
                        "room_code": room_code,
                        "participants": [new_participant_payload],
                    }
                    if os.environ.get('DEBUG_E2E'):
                        print(f"SERVER DEBUG: queue matched to existing {p.id} about {participant.id}")
                    tasks.append(asyncio.create_task(p.websocket.send_json(payload)))

                new_payload = {
                    "type": "matched",
                    "room_code": room_code,
                    "participants": participants_payload,
                }
                if os.environ.get('DEBUG_E2E'):
                    print(f"SERVER DEBUG: queue matched to new participant {participant.id} participants: {[p.id for p in existing]}")
                tasks.append(asyncio.create_task(websocket.send_json(new_payload)))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                if os.environ.get('DEBUG_E2E'):
                    print(f"SERVER DEBUG: matched send results: {results}")
            except Exception:
                if os.environ.get('DEBUG_E2E'):
                    print(f"SERVER DEBUG: matched send failed overall for {participant.id}")

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
                    if p.id == participant.id:
                        continue
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
                target = None
                if target_id:
                    target = await room_manager.get_participant(target_id)
                else:
                    # prefer room_manager.get_peer if available
                    try:
                        target = await room_manager.get_peer(participant.id)
                    except Exception:
                        # fallback to scanning room participants
                        peers = [p for p in await room_manager.get_room_participants(room_code) if p.id != participant.id]
                        if len(peers) == 1:
                            target = peers[0]
                        else:
                            continue

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
            if removed is not None:
                for p in remaining:
                    try:
                        # send legacy-compatible 'peer-left' first
                        await p.websocket.send_json({"type": "peer-left", "id": removed.id, "name": removed.name})
                        # then send the newer 'participant-left' event
                        await p.websocket.send_json({"type": "participant-left", "id": removed.id, "name": removed.name})
                        if os.environ.get('DEBUG_E2E'):
                            print(f"SERVER DEBUG: sent peer-left and participant-left to {p.id} removed:{removed.id}")
                    except Exception:
                        if os.environ.get('DEBUG_E2E'):
                            print(f"SERVER DEBUG: peer-left/participant-left send failed to {p.id}")
            # ensure websocket is closed
            try:
                await websocket.close()
            except Exception:
                pass


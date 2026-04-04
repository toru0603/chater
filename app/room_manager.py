from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket


class RoomFullError(Exception):
    pass


@dataclass(slots=True)
class Participant:
    id: str
    name: str
    room_code: str
    role: str
    websocket: WebSocket
    joined_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class Room:
    code: str
    participants: dict[str, Participant] = field(default_factory=dict)

    def peer_of(self, participant_id: str) -> Optional[Participant]:
        for pid, participant in self.participants.items():
            if pid != participant_id:
                return participant
        return None


class RoomManager:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def add_participant(self, room_code: str, name: str, websocket: WebSocket) -> tuple[Participant, Optional[Participant]]:
        async with self._lock:
            room = self._rooms.setdefault(room_code, Room(code=room_code))
            if len(room.participants) >= 2:
                raise RoomFullError(room_code)

            role = "host" if not room.participants else "guest"
            participant = Participant(
                id=uuid.uuid4().hex,
                name=name,
                room_code=room_code,
                role=role,
                websocket=websocket,
            )
            peer = room.peer_of(next(iter(room.participants.keys()))) if room.participants else None
            room.participants[participant.id] = participant
            if len(room.participants) == 2:
                peer = room.peer_of(participant.id)
            return participant, peer

    async def remove_participant(self, participant_id: str) -> tuple[Optional[Participant], bool]:
        async with self._lock:
            room = next((room for room in self._rooms.values() if participant_id in room.participants), None)
            if room is None:
                return None, False

            room.participants.pop(participant_id, None)
            peer = room.peer_of(participant_id)
            empty = len(room.participants) == 0
            if empty:
                self._rooms.pop(room.code, None)
            return peer, empty

    async def get_peer(self, participant_id: str) -> Optional[Participant]:
        async with self._lock:
            room = next((room for room in self._rooms.values() if participant_id in room.participants), None)
            if room is None:
                return None
            return room.peer_of(participant_id)

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from fastapi import WebSocket

MAX_PARTICIPANTS = 2

DEFAULT_COLORS = [
    "#e11d48",
    "#f97316",
    "#f59e0b",
    "#10b981",
    "#06b6d4",
    "#3b82f6",
    "#8b5cf6",
    "#ec4899",
    "#6366f1",
    "#14b8a6",
]


class RoomFullError(Exception):
    pass


@dataclass(slots=True)
class Participant:
    id: str
    name: str
    room_code: str
    role: str
    color: str
    websocket: WebSocket
    joined_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class Room:
    code: str
    participants: Dict[str, Participant] = field(default_factory=dict)

    def peers_of(self, participant_id: str) -> List[Participant]:
        return [p for pid, p in self.participants.items() if pid != participant_id]

    def participant_list(self) -> List[Participant]:
        return list(self.participants.values())


class RoomManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def add_participant(self, room_code: str, name: str, websocket: WebSocket) -> tuple[Participant, List[Participant]]:
        async with self._lock:
            room = self._rooms.setdefault(room_code, Room(code=room_code))
            if len(room.participants) >= MAX_PARTICIPANTS:
                raise RoomFullError(room_code)

            role = "host" if not room.participants else "guest"
            pid = uuid.uuid4().hex
            color = DEFAULT_COLORS[int(pid[:8], 16) % len(DEFAULT_COLORS)]
            participant = Participant(
                id=pid,
                name=name,
                room_code=room_code,
                role=role,
                color=color,
                websocket=websocket,
            )
            existing = list(room.participants.values())
            room.participants[participant.id] = participant
            return participant, existing

    async def remove_participant(self, participant_id: str) -> tuple[Optional[Participant], List[Participant], bool]:
        async with self._lock:
            room = next((room for room in self._rooms.values() if participant_id in room.participants), None)
            if room is None:
                return None, [], False

            removed = room.participants.pop(participant_id, None)
            remaining = list(room.participants.values())
            empty = len(room.participants) == 0
            if empty:
                self._rooms.pop(room.code, None)
            return removed, remaining, empty

    async def get_participant(self, participant_id: str) -> Optional[Participant]:
        async with self._lock:
            for room in self._rooms.values():
                if participant_id in room.participants:
                    return room.participants.get(participant_id)
            return None

    async def get_room_participants(self, room_code: str) -> List[Participant]:
        async with self._lock:
            room = self._rooms.get(room_code)
            return list(room.participants.values()) if room else []

    async def get_peer(self, participant_id: str) -> Optional[Participant]:
        async with self._lock:
            for room in self._rooms.values():
                if participant_id in room.participants:
                    for pid, p in room.participants.items():
                        if pid != participant_id:
                            return p
                    return None
            return None

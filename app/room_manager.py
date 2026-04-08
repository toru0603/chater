from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from fastapi import WebSocket


# Maximum participants per room (default 10). Can be adjusted for testing via env var if needed.
MAX_PARTICIPANTS = 10

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


class RoomManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def add_participant(self, room_code: str, name: str, websocket: WebSocket) -> tuple[Participant, Optional[Participant]]:
        """Add a participant and return (participant, peer).

        For the first participant in a room, peer is None. For the second, peer is the existing participant.
        """
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

            # existing peer (for 1:1) is the first participant if present
            peer = next(iter(room.participants.values())) if room.participants else None
            room.participants[participant.id] = participant
            return participant, peer

    async def remove_participant(self, participant_id: str) -> tuple[Optional[Participant], bool]:
        """Remove participant and return (remaining_peer, empty).

        remaining_peer is the other participant if present, otherwise None. empty is True when the room becomes empty.
        """
        async with self._lock:
            room = next((room for room in self._rooms.values() if participant_id in room.participants), None)
            if room is None:
                return None, False

            removed = room.participants.pop(participant_id, None)
            remaining = list(room.participants.values())
            empty = len(room.participants) == 0
            if empty:
                self._rooms.pop(room.code, None)
            peer_after_remove = remaining[0] if remaining else None
            return peer_after_remove, empty

    async def get_peer(self, participant_id: str) -> Optional[Participant]:
        async with self._lock:
            for room in self._rooms.values():
                if participant_id in room.participants:
                    peers = [p for pid, p in room.participants.items() if pid != participant_id]
                    return peers[0] if peers else None
            return None

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

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from fastapi import WebSocket

# Tests expect rooms to be pairwise (host + guest)
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

    def participant_list(self) -> List[Participant]:
        return list(self.participants.values())


class RoomManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def add_participant(
        self, room_code: str, name: str, websocket: WebSocket
    ) -> Tuple[Participant, Optional[Participant]]:
        """Add a participant. Returns (participant, peer) where peer is None for the
        first participant and the existing participant for the second joiner.
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

            # determine peer (None if first participant)
            peer: Optional[Participant] = None
            if room.participants:
                # only one existing participant supported by tests
                peer = next(iter(room.participants.values()))

            room.participants[participant.id] = participant
            return participant, peer

    async def remove_participant(
        self, participant_id: str
    ) -> Tuple[Optional[Participant], bool]:
        """Remove a participant and return (peer_after_remove, empty).

        peer_after_remove is the remaining participant (if any), empty is True when
        the room becomes empty after removal.
        """
        async with self._lock:
            room = next(
                (r for r in self._rooms.values() if participant_id in r.participants),
                None,
            )
            if room is None:
                return None, False

            # remove and compute remaining
            room.participants.pop(participant_id, None)
            remaining = list(room.participants.values())
            empty = len(room.participants) == 0
            if empty:
                self._rooms.pop(room.code, None)

            peer_after_remove = remaining[0] if remaining else None
            return peer_after_remove, empty

    async def get_peer(self, participant_id: str) -> Optional[Participant]:
        """Return the other participant in the same room, or None if not found."""
        async with self._lock:
            for room in self._rooms.values():
                if participant_id in room.participants:
                    for pid, p in room.participants.items():
                        if pid != participant_id:
                            return p
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

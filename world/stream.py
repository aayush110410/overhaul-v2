"""Streaming layer for world sessions: binary frame codec + WS/SSE endpoints.

Protocol spec: ``shared/contracts/world_frame.md``. The binary format keeps
2000-agent 5 Hz streaming around 164 KB/s — JSON would be ~10× that.
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from typing import Any, Dict, List, Sequence

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

MAGIC = 0x574C4431  # "WLD1" little-endian
_HEADER = struct.Struct("<IIdHHI")  # magic, seq, sim_time_s, count, flags, reserved
_AGENT = struct.Struct("<ffHBBBBH")  # lon, lat, bearing10, speed, mode, state, class, pad

MODE_CODES = {"car": 0, "two_wheeler": 1, "auto": 2, "bus": 3, "walk": 4, "freight": 5}
STATE_CODES = {"moving": 0, "queued": 1, "congested": 2, "arrived": 3}
_MODE_NAMES = {v: k for k, v in MODE_CODES.items()}
_STATE_NAMES = {v: k for k, v in STATE_CODES.items()}

_KEEPALIVE_S = 20.0
_SSE_MIN_FRAME_GAP_S = 0.5  # SSE fallback ≤2 Hz


def pack_frame(seq: int, sim_time_s: float, agents: Sequence[Any]) -> bytes:
    """Pack agents (objects with lon/lat/bearing/speed_kmh/mode/state/agent_class)."""
    parts = [_HEADER.pack(MAGIC, seq & 0xFFFFFFFF, float(sim_time_s), len(agents), 0, 0)]
    for a in agents:
        parts.append(
            _AGENT.pack(
                float(a.lon),
                float(a.lat),
                int(round(a.bearing * 10)) % 3600,
                min(255, max(0, int(round(a.speed_kmh)))),
                MODE_CODES.get(a.mode, 0),
                STATE_CODES.get(a.state, 0),
                int(a.agent_class) & 0xFF,
                0,
            )
        )
    return b"".join(parts)


def unpack_frame(buf: bytes) -> Dict[str, Any]:
    """Decode a binary frame (tests + the SSE JSON fallback)."""
    magic, seq, sim_time_s, count, flags, _ = _HEADER.unpack_from(buf, 0)
    if magic != MAGIC:
        raise ValueError(f"bad frame magic: {magic:#x}")
    expected = _HEADER.size + count * _AGENT.size
    if len(buf) < expected:
        raise ValueError(f"truncated frame: {len(buf)} < {expected}")
    agents: List[Dict[str, Any]] = []
    for i in range(count):
        lon, lat, brg, spd, mode, state, cls, _pad = _AGENT.unpack_from(
            buf, _HEADER.size + i * _AGENT.size
        )
        agents.append(
            {
                "lon": lon,
                "lat": lat,
                "bearing": brg / 10.0,
                "speed_kmh": spd,
                "mode": _MODE_NAMES.get(mode, "car"),
                "state": _STATE_NAMES.get(state, "moving"),
                "agent_class": cls,
            }
        )
    return {
        "seq": seq,
        "sim_time_s": sim_time_s,
        "agent_count": count,
        "flags": flags,
        "agents": agents,
    }


# ── FastAPI surface ──

router = APIRouter()


def _get_session(session_id: str):
    from world.session import SESSIONS

    return SESSIONS.get(session_id)


@router.websocket("/ws/world/{session_id}")
async def world_ws(websocket: WebSocket, session_id: str) -> None:
    session = _get_session(session_id)
    if session is None:
        await websocket.close(code=4404, reason="unknown session")
        return
    await websocket.accept()
    queue = session.subscribe()
    try:
        await websocket.send_json(session.hello_message())
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_S)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue
            if item is None:
                await websocket.send_json({"type": "end"})
                break
            if isinstance(item, (bytes, bytearray)):
                await websocket.send_bytes(item)
            else:
                await websocket.send_json(item)
    except WebSocketDisconnect:
        pass
    except Exception:  # client gone mid-send etc. — never crash the app
        logger.debug("world ws closed uncleanly", exc_info=True)
    finally:
        session.unsubscribe(queue)


@router.get("/world/{session_id}/stream")
async def world_sse(session_id: str) -> StreamingResponse:
    """SSE fallback: same JSON messages; frames decoded server-side at ≤2 Hz."""
    session = _get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")

    async def gen():
        queue = session.subscribe()
        last_frame = 0.0
        try:
            yield f"data: {json.dumps(session.hello_message())}\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield 'data: {"type": "ping"}\n\n'
                    continue
                if item is None:
                    yield 'data: {"type": "end"}\n\n'
                    break
                if isinstance(item, (bytes, bytearray)):
                    now = time.monotonic()
                    if now - last_frame < _SSE_MIN_FRAME_GAP_S:
                        continue
                    last_frame = now
                    payload = unpack_frame(item)
                    payload["type"] = "frame"
                    yield f"data: {json.dumps(payload)}\n\n"
                else:
                    yield f"data: {json.dumps(item)}\n\n"
        finally:
            session.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

"""Tests for the binary world-frame codec (spec: shared/contracts/world_frame.md)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from world.stream import MAGIC, pack_frame, unpack_frame


@dataclass
class _A:
    lon: float
    lat: float
    bearing: float
    speed_kmh: float
    mode: str
    state: str
    agent_class: int


AGENTS = [
    _A(77.391, 28.535, 123.4, 42.7, "car", "moving", 0),
    _A(-73.986, 40.748, 359.96, 0.0, "bus", "queued", 0),
    _A(77.209, 28.614, 0.0, 260.0, "walk", "arrived", 1),  # speed clamps to 255
]


def test_frame_length_and_magic():
    buf = pack_frame(seq=7, sim_time_s=123.5, agents=AGENTS)
    assert len(buf) == 24 + 16 * len(AGENTS)
    assert int.from_bytes(buf[:4], "little") == MAGIC


def test_round_trip_with_quantization():
    frame = unpack_frame(pack_frame(seq=42, sim_time_s=9000.25, agents=AGENTS))
    assert frame["seq"] == 42
    assert frame["sim_time_s"] == 9000.25
    assert frame["agent_count"] == len(AGENTS)

    for orig, got in zip(AGENTS, frame["agents"]):
        assert abs(got["lon"] - orig.lon) < 1e-4  # f32 precision
        assert abs(got["lat"] - orig.lat) < 1e-4
        assert abs(got["bearing"] - (orig.bearing % 360)) < 0.11 or (
            orig.bearing % 360 > 359.9 and got["bearing"] in (0.0, 359.9)
        )
        assert got["speed_kmh"] == min(255, round(orig.speed_kmh))
        assert got["mode"] == orig.mode
        assert got["state"] == orig.state
        assert got["agent_class"] == orig.agent_class


def test_empty_frame():
    frame = unpack_frame(pack_frame(seq=1, sim_time_s=0.0, agents=[]))
    assert frame["agent_count"] == 0
    assert frame["agents"] == []


def test_bad_magic_rejected():
    buf = bytearray(pack_frame(seq=1, sim_time_s=0.0, agents=AGENTS))
    buf[0] ^= 0xFF
    with pytest.raises(ValueError, match="magic"):
        unpack_frame(bytes(buf))


def test_truncated_frame_rejected():
    buf = pack_frame(seq=1, sim_time_s=0.0, agents=AGENTS)
    with pytest.raises(ValueError, match="truncated"):
        unpack_frame(buf[:-4])

# World Stream Protocol (v1)

Transport for the Living World map: `WS /ws/world/{session_id}` (primary) and
`GET /world/{session_id}/stream` (SSE JSON fallback, frames throttled to ≤2 Hz).

A WebSocket client receives two kinds of messages:

1. **Binary agent frames** (~5 Hz) — positions of every agent, little-endian:

   **Header — 24 bytes**
   | offset | type | field | notes |
   |---|---|---|---|
   | 0 | u32 | magic | `0x574C4431` ("WLD1" LE) |
   | 4 | u32 | seq | monotonically increasing |
   | 8 | f64 | sim_time_s | sim-seconds since session start |
   | 16 | u16 | agent_count | |
   | 18 | u16 | flags | reserved, 0 |
   | 20 | u32 | reserved | 0 |

   **Per agent — 16 bytes** (agent `i` is the same entity in every frame; the
   `hello` message carries the manifest)
   | offset | type | field | notes |
   |---|---|---|---|
   | 0 | f32 | lon | degrees |
   | 4 | f32 | lat | degrees |
   | 8 | u16 | bearing | tenths of a degree, 0–3599 |
   | 10 | u8 | speed | km/h, clamped 0–255 |
   | 11 | u8 | mode | 0 car · 1 two_wheeler · 2 auto · 3 bus · 4 walk · 5 freight |
   | 12 | u8 | state | 0 moving · 1 queued · 2 congested · 3 arrived |
   | 13 | u8 | class | 0 swarm · 1 sentinel |
   | 14 | u16 | pad | 0 |

   2050 agents × 16 B × 5 Hz ≈ 164 KB/s (~1.3 Mbps).

2. **JSON text messages** — `{"type": ...}`:
   - `hello` — region (key/display_name/center/bbox/timezone), conditions,
     weather, `agents.total`, `agents.sentinel_indices`, corridor `roads`
     geojson, `speed`, `sim_clock_s`.
   - `weather` — full WeatherState (visuals + physics agree by construction).
   - `metrics` — `sim_clock`, `avg_speed_kmh`, `congestion_pct`, `arrived`,
     `en_route`.
   - `phase` — cognition/engine lifecycle beats.
   - `sentinel_thought` — `idx` (frame index), `segment`, `mood`, `why`,
     `route`, `confidence` (only after cognitive events; LLM-derived when
     cognition is on, physics-fallback otherwise).
   - `engines` — 7-domain refresh results (metrics/impacts/confidence).
   - `report` — end-of-warmup policy brief.
   - `ping` — keepalive (every ~20 s of silence); `end` — session over.

The SSE fallback emits the same JSON messages; binary frames are decoded
server-side into `{"type": "frame", ...unpack_frame()...}` at ≤2 Hz.

Reference codec: `world/stream.py` (`pack_frame` / `unpack_frame`);
JS mirror: `landing-react/src/world/frameCodec.js`.

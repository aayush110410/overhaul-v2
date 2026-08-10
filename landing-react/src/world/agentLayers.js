// deck.gl layers for the living agents: procedural low-poly vehicle meshes
// (no glTF pipeline needed), one SimpleMeshLayer per transport mode, plus
// distinct pickable sentinel beacons with a pulsing halo.
//
// Mesh convention: +X = forward, +Y = left, +Z = up, units = meters.
// deck.gl orientation is [pitch, yaw, roll] with yaw CCW around +Z from +X,
// so a compass bearing (CW from north) maps to yaw = 90 - bearing.

import { SimpleMeshLayer } from '@deck.gl/mesh-layers'
import { ScatterplotLayer } from '@deck.gl/layers'
import { MODES, STATES } from './frameCodec'

// ── procedural meshes ──

function pushBox(pos, nrm, cx, cy, cz, sx, sy, sz) {
  const x0 = cx - sx / 2, x1 = cx + sx / 2
  const y0 = cy - sy / 2, y1 = cy + sy / 2
  const z0 = cz - sz / 2, z1 = cz + sz / 2
  // 6 faces × 2 triangles, outward normals
  const faces = [
    [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1], [1, 0, 0]],
    [[x0, y1, z0], [x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [-1, 0, 0]],
    [[x1, y1, z0], [x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [0, 1, 0]],
    [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1], [0, -1, 0]],
    [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [0, 0, 1]],
    [[x0, y1, z0], [x1, y1, z0], [x1, y0, z0], [x0, y0, z0], [0, 0, -1]],
  ]
  for (const [a, b, c, d, n] of faces) {
    for (const v of [a, b, c, a, c, d]) pos.push(v[0], v[1], v[2])
    for (let i = 0; i < 6; i++) nrm.push(n[0], n[1], n[2])
  }
}

function makeMesh(boxes) {
  const pos = []
  const nrm = []
  for (const b of boxes) pushBox(pos, nrm, ...b)
  return {
    attributes: {
      positions: { value: new Float32Array(pos), size: 3 },
      normals: { value: new Float32Array(nrm), size: 3 },
    },
  }
}

// [cx, cy, cz, sx, sy, sz] — meters, +X forward.
const MESHES = {
  car: makeMesh([
    [0, 0, 0.55, 4.4, 1.8, 1.0],   // body
    [-0.3, 0, 1.25, 2.2, 1.6, 0.6], // cabin
  ]),
  two_wheeler: makeMesh([
    [0, 0, 0.5, 1.9, 0.6, 0.7],    // bike
    [-0.1, 0, 1.25, 0.6, 0.5, 0.9], // rider
  ]),
  auto: makeMesh([
    [0, 0, 0.8, 2.6, 1.4, 1.5],
    [1.1, 0, 0.5, 0.5, 0.9, 0.9],  // nose
  ]),
  bus: makeMesh([[0, 0, 1.6, 11.0, 2.5, 3.0]]),
  walk: makeMesh([
    [0, 0, 0.85, 0.4, 0.5, 1.5],
    [0, 0, 1.75, 0.3, 0.3, 0.3],   // head
  ]),
  freight: makeMesh([
    [-1.0, 0, 1.7, 6.0, 2.4, 3.0], // trailer
    [3.0, 0, 1.2, 2.0, 2.2, 2.0],  // cab
  ]),
  sentinel: makeMesh([
    [0, 0, 4.0, 1.6, 1.6, 8.0],    // beacon column
    [0, 0, 9.0, 3.2, 3.2, 1.0],    // crown
  ]),
}

// Realistic-ish paint palettes per mode (varied per agent for life).
const PALETTES = {
  car: [[235, 235, 235], [180, 185, 190], [40, 42, 48], [140, 30, 35], [55, 75, 120]],
  two_wheeler: [[30, 30, 34], [160, 40, 40], [50, 90, 150]],
  auto: [[240, 200, 40], [70, 160, 60]], // CNG yellow-green
  bus: [[225, 120, 30], [50, 130, 70]],
  walk: [[200, 170, 140], [90, 110, 150], [150, 90, 90]],
  freight: [[190, 190, 195], [120, 90, 60]],
}

const QUEUED_TINT = [255, 64, 48] // brake-light red

function colorFor(agent, index) {
  const mode = MODES[agent.mode] || 'car'
  const palette = PALETTES[mode] || PALETTES.car
  const base = palette[index % palette.length]
  if (STATES[agent.state] === 'queued') {
    return [
      Math.min(255, base[0] * 0.5 + QUEUED_TINT[0] * 0.5),
      base[1] * 0.5,
      base[2] * 0.5,
      255,
    ]
  }
  return [base[0], base[1], base[2], 255]
}

const MOOD_COLORS = {
  stable: [80, 220, 255],
  optimistic: [90, 255, 150],
  frustrated: [255, 170, 60],
  panicked: [255, 80, 80],
}

const DAY_MATERIAL = { ambient: 0.45, diffuse: 0.7, shininess: 40, specularColor: [200, 200, 220] }
const NIGHT_MATERIAL = { ambient: 0.85, diffuse: 0.35, shininess: 60, specularColor: [255, 240, 200] }
const HEADLIGHT_MODES = new Set(['car', 'auto', 'bus', 'freight', 'two_wheeler'])
const HEADLIGHT_OFFSET_M = 2.4

/**
 * Build the deck.gl layer stack for one render tick.
 * `agents` is the mutable dead-reckoned array; `tick` invalidates accessors.
 * `night` brightens materials and adds headlight glows so traffic reads
 * against the dark basemap.
 */
export function buildAgentLayers({ agents, tick, sentinelMoods = {}, onSentinelClick, sizeScale = 2.5, night = false }) {
  const layers = []
  const byMode = new Map()
  const sentinels = []
  for (let i = 0; i < agents.length; i++) {
    const a = agents[i]
    if (STATES[a.state] === 'arrived') continue
    if (a.cls === 1) {
      sentinels.push({ ...a, idx: i })
      continue
    }
    const mode = MODES[a.mode] || 'car'
    if (!byMode.has(mode)) byMode.set(mode, [])
    byMode.get(mode).push({ ...a, idx: i })
  }

  for (const [mode, data] of byMode) {
    layers.push(
      new SimpleMeshLayer({
        id: `agents-${mode}`,
        data,
        mesh: MESHES[mode],
        getPosition: (d) => [d.lon, d.lat],
        getOrientation: (d) => [0, 90 - d.bearing, 0],
        getColor: (d) => colorFor(d, d.idx),
        sizeScale,
        material: night ? NIGHT_MATERIAL : DAY_MATERIAL,
        pickable: false,
        updateTriggers: { getPosition: tick, getOrientation: tick, getColor: tick },
      }),
    )
  }

  if (night) {
    const lit = []
    for (const [mode, data] of byMode) {
      if (!HEADLIGHT_MODES.has(mode)) continue
      for (const d of data) lit.push(d)
    }
    layers.push(
      new ScatterplotLayer({
        id: 'headlights',
        data: lit,
        getPosition: (d) => {
          const rad = (d.bearing * Math.PI) / 180
          return [
            d.lon + (HEADLIGHT_OFFSET_M * Math.sin(rad)) / (111320 * Math.cos((d.lat * Math.PI) / 180)),
            d.lat + (HEADLIGHT_OFFSET_M * Math.cos(rad)) / 110540,
          ]
        },
        getRadius: 1.6,
        radiusUnits: 'meters',
        radiusMinPixels: 1,
        getFillColor: [255, 244, 200, 210],
        stroked: false,
        pickable: false,
        updateTriggers: { getPosition: tick },
      }),
    )
  }

  const pulse = 0.6 + 0.4 * Math.sin((tick % 120) / 120 * Math.PI * 2)
  layers.push(
    new ScatterplotLayer({
      id: 'sentinel-halo',
      data: sentinels,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 26 * pulse + 14,
      radiusUnits: 'meters',
      getFillColor: (d) => [...(MOOD_COLORS[sentinelMoods[d.idx]] || MOOD_COLORS.stable), 60],
      stroked: false,
      pickable: false,
      updateTriggers: { getPosition: tick, getRadius: tick, getFillColor: tick },
    }),
    new SimpleMeshLayer({
      id: 'sentinels',
      data: sentinels,
      mesh: MESHES.sentinel,
      getPosition: (d) => [d.lon, d.lat],
      getOrientation: (d) => [0, 90 - d.bearing, 0],
      getColor: (d) => [...(MOOD_COLORS[sentinelMoods[d.idx]] || MOOD_COLORS.stable), 235],
      sizeScale: sizeScale * 0.9,
      pickable: true,
      onClick: (info) => info.object && onSentinelClick?.(info.object.idx),
      updateTriggers: { getPosition: tick, getOrientation: tick, getColor: tick },
    }),
  )
  return layers
}

// Binary world-frame decoder — mirrors world/stream.py.
// Spec: shared/contracts/world_frame.md (24 B header + 16 B per agent, LE).

export const FRAME_MAGIC = 0x574c4431 // "WLD1"
export const MODES = ['car', 'two_wheeler', 'auto', 'bus', 'walk', 'freight']
export const STATES = ['moving', 'queued', 'congested', 'arrived']

export function decodeFrame(buffer) {
  const dv = new DataView(buffer)
  if (dv.getUint32(0, true) !== FRAME_MAGIC) throw new Error('bad frame magic')
  const seq = dv.getUint32(4, true)
  const simTimeS = dv.getFloat64(8, true)
  const count = dv.getUint16(16, true)
  if (buffer.byteLength < 24 + count * 16) throw new Error('truncated frame')
  const agents = new Array(count)
  let off = 24
  for (let i = 0; i < count; i++, off += 16) {
    agents[i] = {
      lon: dv.getFloat32(off, true),
      lat: dv.getFloat32(off + 4, true),
      bearing: dv.getUint16(off + 8, true) / 10,
      speedKmh: dv.getUint8(off + 10),
      mode: dv.getUint8(off + 11),
      state: dv.getUint8(off + 12),
      cls: dv.getUint8(off + 13),
    }
  }
  return { seq, simTimeS, count, agents }
}

// Live connection to a world session: WS binary frames + JSON events,
// exponential-backoff reconnect, SSE fallback, and client-side dead-reckoning
// so 5 Hz server frames render as smooth 60 fps motion.

import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE, apiFetchJson } from '../api/config'
import { decodeFrame, STATES } from './frameCodec'

const MAX_WS_RETRIES = 3
const MAX_THOUGHTS = 60

const DEG_LAT_M = 110540
const DEG_LON_M = 111320

export function useWorldSocket() {
  const [status, setStatus] = useState('idle') // idle|starting|live|ended|error
  const [error, setError] = useState(null)
  const [session, setSession] = useState(null) // /world/start response
  const [hello, setHello] = useState(null)
  const [weather, setWeather] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [report, setReport] = useState(null)
  const [engines, setEngines] = useState(null)
  const [thoughts, setThoughts] = useState([])

  // Mutable live agent list — read by the render loop, never via React state.
  const agentsRef = useRef([])
  const simTimeRef = useRef(0)
  const speedRef = useRef(60)
  const lastFrameAtRef = useRef(0)
  const socketRef = useRef(null)
  const sseRef = useRef(null)
  const aliveRef = useRef(false)

  const handleJson = useCallback((msg) => {
    switch (msg.type) {
      case 'hello':
        setHello(msg)
        setWeather(msg.weather)
        speedRef.current = msg.speed
        setStatus('live')
        break
      case 'weather':
        setWeather(msg)
        break
      case 'metrics':
        setMetrics(msg)
        break
      case 'sentinel_thought':
        setThoughts((prev) => [msg, ...prev].slice(0, MAX_THOUGHTS))
        break
      case 'engines':
        setEngines(msg.domains)
        break
      case 'report':
        setReport(msg)
        break
      case 'phase':
        if (msg.phase === 'speed') speedRef.current = msg.speed
        break
      case 'error':
        setError(msg.message)
        setStatus('error')
        break
      case 'end':
        setStatus('ended')
        break
      default:
        break
    }
  }, [])

  const applyFrame = useCallback((frame) => {
    simTimeRef.current = frame.simTimeS
    lastFrameAtRef.current = performance.now()
    const live = agentsRef.current
    if (live.length !== frame.count) {
      agentsRef.current = frame.agents.map((a) => ({ ...a }))
      return
    }
    for (let i = 0; i < frame.count; i++) {
      const src = frame.agents[i]
      const dst = live[i]
      dst.lon = src.lon
      dst.lat = src.lat
      dst.bearing = src.bearing
      dst.speedKmh = src.speedKmh
      dst.mode = src.mode
      dst.state = src.state
      dst.cls = src.cls
    }
  }, [])

  // Advance displayed positions between frames (called from the render rAF).
  const deadReckon = useCallback((dtRealMs) => {
    const dtSim = (dtRealMs / 1000) * speedRef.current
    if (dtSim <= 0) return
    const live = agentsRef.current
    for (let i = 0; i < live.length; i++) {
      const a = live[i]
      if (STATES[a.state] !== 'moving' && STATES[a.state] !== 'congested') continue
      const dist = (a.speedKmh / 3.6) * dtSim // meters of sim travel
      const rad = (a.bearing * Math.PI) / 180
      a.lat += (dist * Math.cos(rad)) / DEG_LAT_M
      a.lon += (dist * Math.sin(rad)) / (DEG_LON_M * Math.cos((a.lat * Math.PI) / 180))
    }
  }, [])

  const openSse = useCallback((sessionId) => {
    const es = new EventSource(`${API_BASE}/world/${sessionId}/stream`)
    sseRef.current = es
    es.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'frame') {
        applyFrame({
          seq: msg.seq,
          simTimeS: msg.sim_time_s,
          count: msg.agent_count,
          agents: msg.agents.map((a) => ({
            lon: a.lon, lat: a.lat, bearing: a.bearing, speedKmh: a.speed_kmh,
            mode: 0, state: STATES.indexOf(a.state), cls: a.agent_class,
          })),
        })
      } else {
        handleJson(msg)
      }
    }
    es.onerror = () => {
      es.close()
      if (aliveRef.current) setStatus('error')
    }
  }, [applyFrame, handleJson])

  const openWs = useCallback((sessionId, attempt = 0) => {
    const wsBase = API_BASE.replace(/^http/, 'ws')
    const ws = new WebSocket(`${wsBase}/ws/world/${sessionId}`)
    ws.binaryType = 'arraybuffer'
    socketRef.current = ws
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') handleJson(JSON.parse(ev.data))
      else applyFrame(decodeFrame(ev.data))
    }
    ws.onclose = () => {
      if (!aliveRef.current) return
      if (attempt < MAX_WS_RETRIES) {
        setTimeout(() => aliveRef.current && openWs(sessionId, attempt + 1),
          1000 * 2 ** attempt)
      } else {
        openSse(sessionId) // degrade to SSE JSON at 2 Hz
      }
    }
  }, [applyFrame, handleJson, openSse])

  const start = useCallback(async (prompt, options = {}) => {
    setStatus('starting')
    setError(null)
    setReport(null)
    setThoughts([])
    setMetrics(null)
    agentsRef.current = []
    try {
      const info = await apiFetchJson('/world/start', {
        method: 'POST',
        body: JSON.stringify({ prompt, ...options }),
      })
      setSession(info)
      speedRef.current = info.speed
      aliveRef.current = true
      openWs(info.session_id)
      return info
    } catch (err) {
      setError(String(err.message || err))
      setStatus('error')
      return null
    }
  }, [openWs])

  const setSpeed = useCallback(async (speed) => {
    if (!session) return
    speedRef.current = speed
    try {
      await apiFetchJson(`/world/${session.session_id}/speed`, {
        method: 'POST',
        body: JSON.stringify({ speed }),
      })
    } catch {
      /* transient; server phase message will re-sync */
    }
  }, [session])

  const stop = useCallback(async () => {
    aliveRef.current = false
    socketRef.current?.close()
    sseRef.current?.close()
    if (session) {
      try {
        await apiFetchJson(`/world/${session.session_id}/stop`, { method: 'POST' })
      } catch { /* already gone */ }
    }
    setStatus('ended')
  }, [session])

  useEffect(() => () => { // unmount cleanup
    aliveRef.current = false
    socketRef.current?.close()
    sseRef.current?.close()
  }, [])

  return {
    status, error, session, hello, weather, metrics, report, engines, thoughts,
    agentsRef, simTimeRef, speedRef,
    start, stop, setSpeed, deadReckon,
  }
}

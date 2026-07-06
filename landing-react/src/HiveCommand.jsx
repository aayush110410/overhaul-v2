import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLocation, Link } from 'react-router-dom'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import ReactMarkdown from 'react-markdown'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers'
import { API_BASE } from './api/config'
import './HiveCommand.css'

const MAPBOX_TOKEN = (import.meta.env.VITE_MAPBOX_TOKEN || '').trim()
mapboxgl.accessToken = MAPBOX_TOKEN
const MAPBOX_STYLE = 'mapbox://styles/mapbox/dark-v11'

const SEGMENTS = [
  { key: 'office_workers', label: 'Office' },
  { key: 'gig_workers', label: 'Gig' },
  { key: 'students', label: 'Students' },
  { key: 'service_sector', label: 'Service' },
  { key: 'industrial_workers', label: 'Industrial' },
  { key: 'senior_citizens', label: 'Seniors' },
  { key: 'high_income', label: 'High-income' },
]
const MOOD_HEX = { frustrated: '#ff5470', adaptive: '#4cc9ff', stable: '#00ffa3', optimistic: '#ffd23f' }
const MOOD_RGB = { frustrated: [255, 84, 112], adaptive: [76, 201, 255], stable: [0, 255, 163], optimistic: [255, 210, 63] }
const VERDICT_HEX = { approve: '#00ffa3', conditional: '#ffd23f', reject: '#ff5470' }
const moodRGB = (m) => MOOD_RGB[m] || [150, 150, 160]

function congestionColor(c) {
  c = Math.max(0, Math.min(c, 1))
  if (c < 0.5) { const t = c / 0.5; return [Math.round(180 * t), 255, Math.round(140 * (1 - t))] }
  const t = (c - 0.5) / 0.5
  return [255, Math.round(255 - 200 * t), Math.round(70 * t)]
}

function buildParticles(geojson) {
  const feats = (geojson?.features || []).filter((f) => f.geometry?.type === 'LineString')
  const total = feats.reduce((s, f) => s + (f.properties?.flow || 0), 0) || 1
  const divisor = Math.max(total / 2200, 1)
  const parts = []
  feats.forEach((f, ei) => {
    const c = f.geometry.coordinates
    if (!c || c.length < 2) return
    const a = c[0], b = c[c.length - 1]
    const flow = f.properties?.flow || 0
    const cong = Math.min(f.properties?.congestion ?? 0.5, 1.2)
    const n = Math.max(2, Math.min(90, Math.round(flow / divisor)))
    const speed = 0.0022 + (1 - Math.min(cong, 1)) * 0.006
    const phase = (ei * 0.1372) % 1
    const color = congestionColor(cong)
    for (let i = 0; i < n; i++) parts.push({ a, b, t: (i / n + phase) % 1, speed, color, pos: a })
  })
  return parts
}

function computeCentroids(sentinels) {
  const acc = {}
  sentinels.forEach((s) => { const g = acc[s.segment] || (acc[s.segment] = { x: 0, y: 0, n: 0 }); g.x += s.coords[0]; g.y += s.coords[1]; g.n += 1 })
  const out = {}
  Object.entries(acc).forEach(([k, g]) => { out[k] = [g.x / g.n, g.y / g.n] })
  return out
}

function hiveMood(brains) {
  if (!brains || !brains.length) return { mood: 'idle', conf: 0 }
  const counts = {}
  let cs = 0
  brains.forEach((b) => { counts[b.segment_mood] = (counts[b.segment_mood] || 0) + 1; cs += b.confidence || 0 })
  const mood = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
  return { mood, conf: cs / brains.length }
}

export default function HiveCommand() {
  const location = useLocation()
  const [loading, setLoading] = useState(!location.state?.skipLoader)
  const mapContainer = useRef(null)
  const mapRef = useRef(null)
  const overlayRef = useRef(null)
  const animRef = useRef(null)
  const dataRef = useRef({ particles: [], sentinels: [], centroids: {} })

  const [simulationData, setSimulationData] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [traceStep, setTraceStep] = useState(-1)
  const [liveProgress, setLiveProgress] = useState(null)
  const [selectedSentinel, setSelectedSentinel] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  const isSimulating = traceStep >= 0

  useEffect(() => { const t = setTimeout(() => setLoading(false), 350); return () => clearTimeout(t) }, [])

  // Map + deck.gl overlay + animation
  useEffect(() => {
    if (loading || !mapContainer.current || mapRef.current || !MAPBOX_TOKEN) return
    const map = new mapboxgl.Map({
      container: mapContainer.current, style: MAPBOX_STYLE,
      center: [77.15, 28.6], zoom: 10, pitch: 58, bearing: -18, antialias: true,
    })
    mapRef.current = map

    map.on('load', () => {
      try { map.setFog({ color: 'rgb(6,6,8)', 'high-color': 'rgb(14,14,20)', 'horizon-blend': 0.25, 'star-intensity': 0.04 }) } catch (_) {}
      map.addSource('roads', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({
        id: 'roads-layer', type: 'line', source: 'roads',
        paint: {
          'line-color': ['interpolate', ['linear'], ['get', 'congestion'], 0, '#1c6', 0.5, '#ccff00', 0.85, '#ff8800', 1.1, '#ff3355'],
          'line-width': ['interpolate', ['linear'], ['get', 'congestion'], 0, 1.2, 1.2, 4.5],
          'line-opacity': 0.45, 'line-blur': 0.8,
        },
      })
      const overlay = new MapboxOverlay({ interleaved: false, layers: [] })
      map.addControl(overlay)
      overlayRef.current = overlay
      if (simulationData) applyToMap(simulationData)

      let frame = 0
      const loop = () => {
        frame += 1
        const now = performance.now()
        const d = dataRef.current
        const P = d.particles
        for (let i = 0; i < P.length; i++) {
          const p = P[i]; p.t += p.speed; if (p.t > 1) p.t -= 1
          p.pos = [p.a[0] + (p.b[0] - p.a[0]) * p.t, p.a[1] + (p.b[1] - p.a[1]) * p.t]
        }
        const pulse = 9 + Math.sin(now / 400) * 5
        const layers = []
        if (d.sentinels.length) {
          layers.push(new ArcLayer({
            id: 'hive-mesh', data: d.sentinels,
            getSourcePosition: (s) => s.coords, getTargetPosition: (s) => d.centroids[s.segment] || s.coords,
            getSourceColor: (s) => [...moodRGB(s.mood), 80], getTargetColor: (s) => [...moodRGB(s.mood), 6],
            getWidth: 1, opacity: 0.45,
          }))
        }
        if (P.length) {
          layers.push(new ScatterplotLayer({
            id: 'swarm', data: P, getPosition: (p) => p.pos, getFillColor: (p) => p.color,
            getRadius: 1.7, radiusUnits: 'pixels', radiusMinPixels: 1, radiusMaxPixels: 2.6, opacity: 0.55,
            updateTriggers: { getPosition: frame },
          }))
        }
        if (d.sentinels.length) {
          layers.push(new ScatterplotLayer({ id: 'probe-halo', data: d.sentinels, getPosition: (s) => s.coords, getFillColor: (s) => [...moodRGB(s.mood), 28], getRadius: pulse, radiusUnits: 'pixels' }))
          layers.push(new ScatterplotLayer({
            id: 'probe-core', data: d.sentinels, getPosition: (s) => s.coords, getFillColor: (s) => moodRGB(s.mood),
            stroked: true, getLineColor: [6, 6, 8], lineWidthMinPixels: 1.5, getRadius: 4.5, radiusUnits: 'pixels',
            pickable: true, onClick: (info) => { if (info.object) setSelectedSentinel(info.object) },
          }))
        }
        overlayRef.current && overlayRef.current.setProps({ layers })
        animRef.current = requestAnimationFrame(loop)
      }
      animRef.current = requestAnimationFrame(loop)
    })

    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); map.remove(); mapRef.current = null; overlayRef.current = null }
  }, [loading]) // eslint-disable-line react-hooks/exhaustive-deps

  const applyToMap = useCallback((data) => {
    const map = mapRef.current
    if (map && data?.geojson && map.getSource('roads')) map.getSource('roads').setData(data.geojson)
    const sentinels = (data?.sentinels || []).filter((s) => Array.isArray(s.coords) && s.coords.length === 2)
    dataRef.current = { particles: buildParticles(data?.geojson), sentinels, centroids: computeCentroids(sentinels) }
  }, [])

  const applyResult = (data) => { setSimulationData(data); applyToMap(data) }
  const runViaPost = async (q) => {
    const resp = await fetch(`${API_BASE}/simulate/hive`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: q, city: 'delhi', agent_count: 2000, sentinels: 14, timesteps: 4 }),
    })
    if (!resp.ok) throw new Error(`Backend ${resp.status}`)
    return resp.json()
  }

  const runSimulation = () => {
    if (!prompt.trim() || isSimulating) return
    const q = prompt.trim()
    setPrompt(''); setErrorMsg(null); setSelectedSentinel(null); setTraceStep(0); setLiveProgress('Connecting to hive…')
    const PHASE_TRACE = { start: 0, sentinels: 1, distill: 2, timestep: 3, engines: 3, report: 3 }
    let done = false, receivedAny = false, es = null
    const finish = () => { setTraceStep(-1); setLiveProgress(null); if (es) es.close() }
    const fail = (msg) => setErrorMsg(msg)
    const fallbackPost = () => { setLiveProgress('Running…'); runViaPost(q).then((d) => { done = true; applyResult(d) }).catch((e) => fail(e.message)).finally(finish) }
    if (typeof EventSource === 'undefined') { fallbackPost(); return }
    const params = new URLSearchParams({ prompt: q, city: 'delhi', agent_count: '2000', sentinels: '14', timesteps: '4' })
    es = new EventSource(`${API_BASE}/simulate/hive/stream?${params.toString()}`)
    es.onmessage = (e) => {
      let ev; try { ev = JSON.parse(e.data) } catch { return }
      receivedAny = true
      if (ev.phase in PHASE_TRACE) setTraceStep(PHASE_TRACE[ev.phase])
      switch (ev.phase) {
        case 'start': setLiveProgress(`Booting ${ev.sentinels} sentinels · ${ev.segments} brains · ${ev.agents} agents`); break
        case 'sentinels': setLiveProgress(`Step ${ev.step + 1} · ${ev.discoveries} sentinels reasoned${ev.fallbacks ? ` (${ev.fallbacks} physics)` : ''}`); break
        case 'distill': setLiveProgress(`Step ${ev.step + 1} · ${ev.distillations} minds distilling collective truth…`); break
        case 'timestep': setLiveProgress(`Step ${ev.step + 1}/${ev.total_steps} · ${ev.avg_speed_kmh} km/h · ${ev.inherited} inherited`); break
        case 'engines': setLiveProgress('Quantifying impact across 7 engines…'); break
        case 'report': setLiveProgress('Synthesizing the brief…'); break
        case 'done': done = true; applyResult(ev.state); finish(); break
        case 'error': done = true; fail(ev.message); finish(); break
        default: break
      }
    }
    es.onerror = () => { if (done) return; es.close(); if (!receivedAny) fallbackPost(); else { fail('stream interrupted'); finish() } }
  }

  const submit = (e) => { if (e.key === 'Enter') { e.preventDefault(); runSimulation() } }

  const hm = hiveMood(simulationData?.brains)
  const brainsByKey = {}
  ;(simulationData?.brains || []).forEach((b) => { brainsByKey[b.segment] = b })
  const report = simulationData?.report
  const km = report?.verdict?.key_metrics || {}
  const verdict = (report?.verdict?.verdict || '').toLowerCase()
  const vColor = VERDICT_HEX[verdict] || '#e8e8ea'
  const modeShifts = (simulationData?.timesteps || []).reduce((a, t) => a + (t.mode_shifts || 0), 0)

  return (
    <div className="hc-root">
      <div ref={mapContainer} className="hc-map" />
      {!MAPBOX_TOKEN && <div className="hc-map hc-map-fallback">Set VITE_MAPBOX_TOKEN to render the map.</div>}
      <div className="hc-vignette" />
      <div className="hc-grain" />

      <header className="hc-topbar">
        <div className="hc-brand">OVERHAUL<span>HIVE&nbsp;COMMAND</span></div>
        <div className="hc-status">
          <span className="hc-status-dot" style={{ background: MOOD_HEX[hm.mood] || '#3a3a3f' }} />
          <span className="hc-status-mood" style={{ color: MOOD_HEX[hm.mood] || '#8a8a90' }}>{hm.mood.toUpperCase()}</span>
          <span className="hc-status-sub">{simulationData ? `${Math.round(hm.conf * 100)}% consensus` : 'standby'}</span>
          <Link to="/" className="hc-exit">EXIT</Link>
        </div>
      </header>

      {/* IDLE HERO */}
      <AnimatePresence>
        {!simulationData && !isSimulating && (
          <motion.div className="hc-hero" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}>
            <div className="hc-hero-kicker">SENTINEL · SWARM · HIVE</div>
            <h1 className="hc-hero-title">Simulate reality<br /><em>before</em> you change it.</h1>
            <p className="hc-hero-sub">Ask a Delhi-NCR policy what-if. Fifty reasoning agents, seven collective minds, and seven impact engines return one defensible brief.</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* EDITORIAL BRIEFING */}
      <AnimatePresence>
        {simulationData && (
          <motion.aside className="hc-brief" initial={{ opacity: 0, x: -28 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -28 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
            <div className="hc-brief-scroll">
              <div className="hc-brief-verdict" style={{ '--v': vColor }}>
                <span className="hc-brief-kicker">POLICY VERDICT</span>
                <h2>{(verdict || 'analyzed').toUpperCase()}</h2>
                <span className="hc-brief-conf">{Math.round((report?.verdict?.confidence || 0) * 100)}% confidence · {simulationData.query}</span>
              </div>

              <div className="hc-metrics">
                <div className="hc-metric"><b>{km.avg_speed_kmh ?? '–'}</b><span>km/h avg</span></div>
                <div className="hc-metric"><b>{km.congestion_pct ?? '–'}<i>%</i></b><span>congestion</span></div>
                <div className="hc-metric"><b>{modeShifts.toLocaleString()}</b><span>mode shifts</span></div>
              </div>

              <div className="hc-brief-body"><ReactMarkdown>{report?.summary || ''}</ReactMarkdown></div>

              {report?.recommendations?.length > 0 && (
                <ul className="hc-recs">
                  {report.recommendations.slice(0, 4).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}

              <div className="hc-hive-strip">
                <div className="hc-hive-strip-label">HIVE · 7 SEGMENT MINDS</div>
                <div className="hc-hive-dots">
                  {SEGMENTS.map((s) => {
                    const t = brainsByKey[s.key]
                    const c = MOOD_HEX[t?.segment_mood] || '#3a3a3f'
                    return (
                      <div key={s.key} className="hc-hive-dot" title={`${s.label}: ${t?.segment_mood || '—'} ${Math.round((t?.confidence || 0) * 100)}%`}>
                        <span className="hc-dot" style={{ background: c, boxShadow: `0 0 8px ${c}` }} />
                        <span className="hc-dot-label">{s.label}</span>
                        <span className="hc-dot-conf">{Math.round((t?.confidence || 0) * 100)}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {simulationData.manifest && (
                <div className="hc-run-meta">
                  {simulationData.manifest.sentinels} sentinels · {simulationData.manifest.runtime_s}s ·{' '}
                  {Object.entries(simulationData.stats?.per_provider || {}).filter(([, v]) => v.calls > 0).map(([m, v]) => `${m} ${v.calls}`).join(' · ') || 'physics-only'}
                </div>
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* COMMAND SPOTLIGHT */}
      <div className={`hc-command ${isSimulating ? 'running' : ''}`}>
        {isSimulating ? (
          <div className="hc-command-progress">
            <span className="hc-orbit"><i /><i /><i /></span>
            <span className="hc-progress-text">{liveProgress || 'Running the hive…'}</span>
          </div>
        ) : (
          <>
            <span className="hc-command-icon">⌕</span>
            <input
              className="hc-command-input"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={submit}
              placeholder="Ask a policy what-if — e.g. congestion pricing in central Delhi…"
              autoFocus
            />
            <button className="hc-run" onClick={runSimulation} disabled={!prompt.trim()}>RUN</button>
          </>
        )}
      </div>
      {errorMsg && <div className="hc-error">{errorMsg}</div>}

      {/* SELECTED PROBE */}
      <AnimatePresence>
        {selectedSentinel && (
          <motion.div className="hc-probe" style={{ '--mood': MOOD_HEX[selectedSentinel.mood] || '#888' }}
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 14 }}>
            <div className="hc-probe-head">
              <span>SENTINEL · {selectedSentinel.segment}</span>
              <button onClick={() => setSelectedSentinel(null)}>×</button>
            </div>
            <div className="hc-probe-mood" style={{ color: MOOD_HEX[selectedSentinel.mood] }}>
              {selectedSentinel.mood} · {Math.round((selectedSentinel.confidence || 0) * 100)}%
            </div>
            <div className="hc-probe-why">“{selectedSentinel.trace?.why || 'physics-only Dijkstra (LLM unavailable)'}”</div>
            {selectedSentinel.trace?.route?.length > 0 && <div className="hc-probe-route">{selectedSentinel.trace.route.join('  →  ')}</div>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

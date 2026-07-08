// /world — the Living Map: a game-realistic 3D world where every agent
// (50 sentinels + the hive swarm) travels individually in real time.
// Photorealistic Mapbox Standard basemap with day/night light presets;
// vehicles are procedural low-poly meshes dead-reckoned between 5 Hz frames.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { useWorldSocket } from './world/useWorldSocket'
import { buildAgentLayers } from './world/agentLayers'
import { applyWeatherToMap, hazeOpacity, rainBucket, supportsNativePrecip } from './world/weatherFx'
import './WorldCommand.css'

const MAPBOX_TOKEN = (import.meta.env.VITE_MAPBOX_TOKEN || '').trim()
if (MAPBOX_TOKEN) mapboxgl.accessToken = MAPBOX_TOKEN

const SUGGESTIONS = [
  'What if it rains during rush hour in Noida?',
  'Simulate evening traffic in New York',
  'Add 500 electric buses in Delhi',
  'Diwali evening congestion in Gurgaon',
]

const SPEEDS = [
  { label: '⏸', value: 0 },
  { label: '1×', value: 60 },
  { label: '4×', value: 240 },
  { label: '10×', value: 600 },
]

function lightPresetFor(clockS) {
  const h = ((clockS % 86400) + 86400) % 86400 / 3600
  if (h < 5) return 'night'
  if (h < 7.5) return 'dawn'
  if (h < 17) return 'day'
  if (h < 19.5) return 'dusk'
  return 'night'
}

function zoomForBbox(bbox) {
  const width = Math.max(Math.abs(bbox[2] - bbox[0]), 0.01)
  return Math.max(9, Math.min(14.5, Math.log2(360 / width) - 0.5))
}

export default function WorldCommand() {
  const world = useWorldSocket()
  const [prompt, setPrompt] = useState('')
  const [sentinelIdx, setSentinelIdx] = useState(null)
  const [showReport, setShowReport] = useState(false)
  const [speedSel, setSpeedSel] = useState(60)

  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const overlayRef = useRef(null)
  const tickRef = useRef(0)
  const moodsRef = useRef({})
  const presetRef = useRef('day')
  const [night, setNight] = useState(false)
  const [nativePrecip, setNativePrecip] = useState(false)

  // Latest mood per sentinel index (for beacon colors + panel).
  useEffect(() => {
    const moods = {}
    for (const t of world.thoughts) if (!(t.idx in moods)) moods[t.idx] = t.mood
    moodsRef.current = moods
  }, [world.thoughts])

  useEffect(() => {
    if (world.report) setShowReport(true)
  }, [world.report])

  // ── map init (once) ──
  useEffect(() => {
    if (!MAPBOX_TOKEN || mapRef.current || !containerRef.current) return
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/standard',
      center: [77.25, 28.55],
      zoom: 3.2,
      pitch: 0,
      antialias: true,
      attributionControl: false,
    })
    map.on('style.load', () => {
      try { map.setConfigProperty('basemap', 'lightPreset', 'day') } catch { /* older style */ }
      const overlay = new MapboxOverlay({ interleaved: false, layers: [] })
      map.addControl(overlay)
      overlayRef.current = overlay
      setNativePrecip(supportsNativePrecip(map))
    })
    mapRef.current = map
    return () => {
      overlayRef.current = null
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Weather → map visuals (same WeatherState that slows the traffic).
  useEffect(() => {
    if (world.weather && mapRef.current) applyWeatherToMap(mapRef.current, world.weather)
  }, [world.weather, nativePrecip])

  // ── render loop: dead-reckon + rebuild layers + day/night preset ──
  useEffect(() => {
    if (world.status !== 'live') return undefined
    let raf
    let last = performance.now()
    const loop = (now) => {
      const dt = Math.min(now - last, 100)
      last = now
      world.deadReckon(dt)
      tickRef.current += 1
      const clock = (world.hello?.sim_clock_s || 0) + world.simTimeRef.current
      const preset = lightPresetFor(clock)
      overlayRef.current?.setProps({
        layers: buildAgentLayers({
          agents: world.agentsRef.current,
          tick: tickRef.current,
          sentinelMoods: moodsRef.current,
          onSentinelClick: setSentinelIdx,
          night: preset === 'night' || preset === 'dusk',
        }),
      })
      if (preset !== presetRef.current) {
        presetRef.current = preset
        setNight(preset === 'night' || preset === 'dusk')
        if (mapRef.current) {
          try { mapRef.current.setConfigProperty('basemap', 'lightPreset', preset) } catch { /* ignore */ }
        }
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [world.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const launch = useCallback(async (text) => {
    const q = (text || '').trim()
    if (!q || world.status === 'starting') return
    const info = await world.start(q, { agent_count: 1500, sentinels: 14, speed: 60 })
    setSpeedSel(60)
    if (info && mapRef.current) {
      mapRef.current.flyTo({
        center: info.region.center,
        zoom: zoomForBbox(info.region.bbox),
        pitch: 58,
        bearing: -15,
        duration: 4500,
        essential: true,
      })
    }
  }, [world])

  const changeSpeed = useCallback((value) => {
    setSpeedSel(value)
    world.setSpeed(value)
  }, [world])

  const sentinelThought = useMemo(() => {
    if (sentinelIdx == null) return null
    return world.thoughts.find((t) => t.idx === sentinelIdx) || { idx: sentinelIdx }
  }, [sentinelIdx, world.thoughts])

  const live = world.status === 'live'
  const wx = world.weather

  return (
    <div className="wc-root">
      {MAPBOX_TOKEN
        ? <div ref={containerRef} className="wc-map" />
        : <div className="wc-map wc-map-missing">Set VITE_MAPBOX_TOKEN to render the world map.</div>}

      {/* ── idle hero ── */}
      {(world.status === 'idle' || world.status === 'ended') && (
        <div className="wc-hero">
          <div className="wc-aurora" aria-hidden="true" />
          <h1>LIVING&nbsp;WORLD</h1>
          <p className="wc-tag">Name a place. Watch its streets come alive — every agent, individually.</p>
          <form
            className="wc-prompt"
            onSubmit={(e) => { e.preventDefault(); launch(prompt) }}
          >
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. what happens if it rains during rush hour in New York?"
              autoFocus
            />
            <button type="submit">SIMULATE</button>
          </form>
          <div className="wc-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => { setPrompt(s); launch(s) }}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {world.status === 'starting' && (
        <div className="wc-starting">
          <div className="wc-spinner" />
          <div>RESOLVING REGION · BUILDING ROADS · WAKING AGENTS…</div>
        </div>
      )}

      {world.status === 'error' && (
        <div className="wc-error">
          <strong>World failed to start.</strong> {world.error}
          <button onClick={() => window.location.reload()}>reset</button>
        </div>
      )}

      {/* ── atmosphere overlays (CSS rain when native GPU rain unavailable; smog haze) ── */}
      {live && !nativePrecip && rainBucket(wx) !== 'none' && (
        <div className={`wc-rain wc-rain-${rainBucket(wx)}`} aria-hidden="true" data-testid="rain-overlay" />
      )}
      {live && hazeOpacity(world.hello?.region?.aqi_baseline) > 0 && (
        <div
          className={`wc-haze ${night ? 'wc-haze-night' : ''}`}
          style={{ opacity: hazeOpacity(world.hello.region.aqi_baseline) }}
          aria-hidden="true"
          data-testid="haze-overlay"
        />
      )}

      {/* ── live HUD ── */}
      {live && world.hello && (
        <>
          <div className="wc-topbar">
            <div className="wc-chip wc-region">
              <span className="wc-dot" />
              {world.hello.region.display_name}
              {world.hello.roadnet_fallback && <em title="Live OSM unavailable — using built-in NCR corridors"> · fallback roads</em>}
            </div>
            {wx && (
              <div className="wc-chip" title={`source: ${wx.source}`}>
                {wx.condition.replace('_', ' ')} · {Math.round(wx.temp_c)}°C
                {wx.precip_mm_h > 0 && ` · ${wx.precip_mm_h} mm/h`}
              </div>
            )}
            <div className="wc-chip wc-clock">{world.metrics?.sim_clock || '—:—'}</div>
            <div className="wc-speeds">
              {SPEEDS.map((s) => (
                <button
                  key={s.value}
                  className={speedSel === s.value ? 'on' : ''}
                  onClick={() => changeSpeed(s.value)}
                >{s.label}</button>
              ))}
            </div>
            <button className="wc-stop" onClick={world.stop}>END</button>
          </div>

          <div className="wc-metrics">
            <div><b>{world.metrics?.en_route ?? '—'}</b><span>on the move</span></div>
            <div><b>{world.metrics?.avg_speed_kmh ?? '—'}</b><span>km/h avg</span></div>
            <div><b>{world.metrics?.congestion_pct ?? '—'}%</b><span>congested</span></div>
            <div><b>{world.metrics?.arrived ?? '—'}</b><span>arrived</span></div>
          </div>

          {world.thoughts.length > 0 && (
            <div className="wc-thoughts">
              <div className="wc-thoughts-head">SENTINEL MINDS</div>
              {world.thoughts.slice(0, 6).map((t, i) => (
                <button key={`${t.idx}-${i}`} className={`wc-thought mood-${t.mood}`}
                  onClick={() => setSentinelIdx(t.idx)}>
                  <b>#{t.idx}</b> {t.segment.replace('_', ' ')} · {t.mood}
                </button>
              ))}
            </div>
          )}

          {world.report && (
            <button className="wc-report-tab" onClick={() => setShowReport(true)}>⬒ BRIEF</button>
          )}
        </>
      )}

      {/* ── sentinel panel ── */}
      {sentinelThought && (
        <div className="wc-panel">
          <button className="wc-close" onClick={() => setSentinelIdx(null)}>✕</button>
          <h3>SENTINEL #{sentinelThought.idx}</h3>
          {sentinelThought.segment ? (
            <>
              <div className={`wc-mood mood-${sentinelThought.mood}`}>{sentinelThought.mood}</div>
              <p className="wc-why">{sentinelThought.why || 'physics routing (no LLM round yet)'}</p>
              {sentinelThought.route?.length > 0 && (
                <div className="wc-route">route: {sentinelThought.route.join(' → ')}</div>
              )}
              <div className="wc-meta">
                {sentinelThought.segment.replace('_', ' ')} · confidence{' '}
                {Math.round((sentinelThought.confidence || 0) * 100)}%
                {sentinelThought.fallback && ' · physics fallback'}
              </div>
            </>
          ) : <p className="wc-why">No reasoning round yet — thoughts arrive every 30 sim-minutes.</p>}
        </div>
      )}

      {/* ── report panel ── */}
      {showReport && world.report && (
        <div className="wc-panel wc-report">
          <button className="wc-close" onClick={() => setShowReport(false)}>✕</button>
          <h3>POLICY BRIEF</h3>
          <p className="wc-summary">{world.report.summary}</p>
          <div className="wc-brains">
            {(world.report.brains || []).map((b) => (
              <div key={b.segment} className={`wc-brain mood-${b.segment_mood}`}>
                <span>{b.label}</span>
                <em>{b.segment_mood} · {Math.round((b.confidence || 0) * 100)}%</em>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

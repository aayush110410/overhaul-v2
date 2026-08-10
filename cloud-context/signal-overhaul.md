# SIGNAL — /world + /hive UI overhaul (handoff & rebuild doc)

> **Why this doc exists.** The SIGNAL overhaul was implemented in a cloud session on 2026-07-09
> but the container was reclaimed and re-cloned at the last *pushed* commit (Phase 6,
> `b9b30b9c4`) **before the work was committed** — twice. All uncommitted SIGNAL code was lost
> each time. This doc is committed so the work survives resets: it embeds the full source of the
> new reusable fx library (the durable IP) and a precise, executable spec for the WorldCommand /
> agentLayers changes. **Next session: rebuild from this file, commit per phase, push immediately.**
>
> Standing rule reinforced (see mistakes.md 2026-07-09): on this ephemeral environment, **commit +
> push after every self-contained unit** — never batch a whole phase of uncommitted files.

Status: **NOT yet on the branch.** Shipped work = Living World Phases 0–6 (`b9b30b9c4`, PR #1).
SIGNAL sits on top of that, `/world` + `/hive` only (landing untouched).

---

## 1. Art direction — "SIGNAL"

Swiss-brutalist evolution of the existing lime brand (the daily-use award-UI formula —
Linear/Vercel/Arc): near-monochrome canvas, ONE signature accent, typography-led, one motion
personality, a few spectacular signature moves. The photoreal map stays the star; the HUD frames it.

- **Color**: canvas `#0A0A0B`, panel `#121214`, hairline `rgba(255,255,255,.08)`, ink `#F5F6F0`,
  muted `#9AA3A0`, **signal `#CCFF00`** (sole accent: focus/live/positive), warn `#FF9A3D`,
  **alert `#FF4D00`** (danger only: severe congestion/AQI, errors).
- **Banned**: cyan/purple, text gradients, glassmorphism/backdrop-blur (except ONE hero scrim),
  glow dots, soft shadows. One shadow token only (`2px 2px 0 #000`), CTA-only.
- **Type** (self-hosted npm, fixes the Google-Fonts sandbox block on these routes):
  `@fontsource-variable/space-grotesk` (display/UI, tight `-0.03em`) +
  `@fontsource/ibm-plex-mono` 400/500/600 (ALL data/labels, tabular numerals). 11px/0.18em caps labels.
- **Surface**: 1px hairlines + flat panels on an 8px grid, 4px max radius.
- **Motion**: `--sig-ease: cubic-bezier(.16,1,.3,1)`; durations 200/400/700ms; everything enters
  staggered-from-below 8px + fade; `prefers-reduced-motion` degrades every FX to a plain fade/static.
- **Three signature moves (the wow budget)**: (1) split-flap text, (2) odometer metrics,
  (3) choreographed HUD assembly after the camera fly-to lands + `layoutId` panel morphs.

---

## 2. Dependencies (with the mandatory gotcha)

```bash
cd landing-react
npm install --save @fontsource-variable/space-grotesk @fontsource/ibm-plex-mono
# --save PRUNES packages installed with --no-save — restore them or build/verify breaks:
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-save playwright @rollup/rollup-linux-x64-gnu @esbuild/linux-x64
```

Already installed (do NOT re-add): framer-motion 12, three 0.181, @react-three/fiber 9.4.2,
@react-three/drei 10.7.7. No Tailwind, no ogl. `chromium` at `/opt/pw-browsers/chromium`.

---

## 3. New files — full source (the durable IP)

### `src/theme/signal.css`
```css
/* SIGNAL — the OVERHAUL product design system. Shared by /world + /hive.
   Fonts self-hosted (npm @fontsource) — no Google Fonts dependency. */
@import '@fontsource-variable/space-grotesk';
@import '@fontsource/ibm-plex-mono/400.css';
@import '@fontsource/ibm-plex-mono/500.css';
@import '@fontsource/ibm-plex-mono/600.css';

:root {
  --sig-canvas:#0A0A0B; --sig-panel:#121214; --sig-panel-2:#17171a;
  --sig-hairline:rgba(255,255,255,.08); --sig-hairline-strong:rgba(255,255,255,.16);
  --sig-ink:#F5F6F0; --sig-muted:#9AA3A0;
  --sig-signal:#CCFF00; --sig-warn:#FF9A3D; --sig-alert:#FF4D00;
  --sig-font-display:'Space Grotesk Variable','Space Grotesk',system-ui,sans-serif;
  --sig-font-mono:'IBM Plex Mono',ui-monospace,monospace;
  --sig-ease:cubic-bezier(.16,1,.3,1);
  --sig-dur-1:200ms; --sig-dur-2:400ms; --sig-dur-3:700ms;
  --sig-radius:4px; --sig-shadow-cta:2px 2px 0 #000; /* the ONLY shadow */
}
.sig-label{font-family:var(--sig-font-mono);font-size:11px;font-weight:500;
  letter-spacing:.18em;text-transform:uppercase;color:var(--sig-muted);}
.sig-panel{background:var(--sig-panel);border:1px solid var(--sig-hairline);border-radius:var(--sig-radius);}
.sig-data{font-family:var(--sig-font-mono);font-variant-numeric:tabular-nums;color:var(--sig-ink);}
```

### `src/fx/useReducedMotion.js`
```js
import { useEffect, useState } from 'react'
export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}
```

### `src/fx/SplitFlap.jsx`
Airport-board flip: each char riffles a charset and lands on target, staggered L→R.
DOM textContent settles to exactly `text`. Reduced motion → static text.
Props: `{ text, className, charSet, flapMs=40, staggerMs=45 }`.
```jsx
import { useEffect, useRef, useState } from 'react'
import { usePrefersReducedMotion } from './useReducedMotion'
import './fx.css'
const DEFAULT_CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789·— '
function FlapChar({ target, charSet, flapMs, delayMs, reduced }) {
  const [char, setChar] = useState(reduced ? target : ' ')
  const [flipping, setFlipping] = useState(false)
  const timers = useRef([])
  useEffect(() => {
    timers.current.forEach(clearTimeout); timers.current = []
    if (reduced) { setChar(target); return undefined }
    setFlipping(true)
    const upper = target.toUpperCase()
    let idx = Math.floor(Math.random() * charSet.length)
    const start = setTimeout(function tick() {
      const current = charSet[idx % charSet.length]; setChar(current)
      if (current === upper || current === target) { setChar(target); setFlipping(false); return }
      idx += 1
      if (idx > charSet.length * 1.5) { setChar(target); setFlipping(false); return }
      timers.current.push(setTimeout(tick, flapMs))
    }, delayMs)
    timers.current.push(start)
    return () => timers.current.forEach(clearTimeout)
  }, [target, charSet, flapMs, delayMs, reduced])
  return <span className={`fx-flap-char${flipping ? ' flipping' : ''}`}
    style={{ '--fx-flap-ms': `${flapMs}ms` }}>{char === ' ' ? ' ' : char}</span>
}
export default function SplitFlap({ text, className='', charSet=DEFAULT_CHARSET, flapMs=40, staggerMs=45 }) {
  const reduced = usePrefersReducedMotion()
  return (
    <span className={`fx-flap ${className}`} aria-label={text}>
      {Array.from(text).map((ch, i) => (
        <FlapChar key={`${i}-${text}`} target={ch} charSet={charSet}
          flapMs={flapMs} delayMs={i * staggerMs} reduced={reduced} />
      ))}
    </span>
  )
}
```

### `src/fx/Odometer.jsx`
Rolling-drum digits (framer-motion spring). **Critical**: textContent === formatted number (no
hidden 0–9 strips) so the verify script's `Number(el.textContent) > 0` on `.wc-metrics b` passes.
Props: `{ value, className, decimals=0 }`.
```jsx
import { AnimatePresence, motion } from 'framer-motion'
import { usePrefersReducedMotion } from './useReducedMotion'
import './fx.css'
const SPRING = { type:'spring', stiffness:320, damping:32, mass:0.6 }
export default function Odometer({ value, className='', decimals=0 }) {
  const reduced = usePrefersReducedMotion()
  const text = Number.isFinite(Number(value)) ? Number(value).toFixed(decimals) : String(value ?? '—')
  if (reduced) return <span className={`fx-odo ${className}`}>{text}</span>
  return (
    <span className={`fx-odo ${className}`}>
      {Array.from(text).map((ch, i) => /\d/.test(ch) ? (
        <span className="fx-odo-col" key={`col-${i}`}>
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span key={ch} className="fx-odo-digit"
              initial={{ y:'0.9em', opacity:0 }} animate={{ y:0, opacity:1 }}
              exit={{ y:'-0.9em', opacity:0 }} transition={SPRING}>{ch}</motion.span>
          </AnimatePresence>
        </span>
      ) : <span key={`sep-${i}`}>{ch}</span>)}
    </span>
  )
}
```

### `src/fx/TextScramble.jsx`
Decrypt-in L→R. Props: `{ text, className, duration=900, delay=0 }`. Reduced motion → plain text.
```jsx
import { useEffect, useRef, useState } from 'react'
import { usePrefersReducedMotion } from './useReducedMotion'
import './fx.css'
const NOISE = '!<>-_\\/[]{}—=+*^?#________'
export default function TextScramble({ text, className='', duration=900, delay=0 }) {
  const reduced = usePrefersReducedMotion()
  const [display, setDisplay] = useState(reduced ? text : '')
  const raf = useRef(0)
  useEffect(() => {
    if (reduced) { setDisplay(text); return undefined }
    let start
    const step = (now) => {
      if (start === undefined) start = now + delay
      const t = Math.max(0, (now - start) / duration)
      const resolved = Math.floor(t * text.length)
      if (resolved >= text.length) { setDisplay(text); return }
      let out = text.slice(0, resolved)
      for (let i = resolved; i < text.length; i++)
        out += text[i] === ' ' ? ' ' : NOISE[(Math.random()*NOISE.length)|0]
      setDisplay(out)
      raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [text, duration, delay, reduced])
  return <span className={`fx-scramble ${className}`}>{display}</span>
}
```

### `src/fx/MagneticButton.jsx`
Cursor-magnet CTA; renders a real `<button>` (keeps `.wc-prompt button` selector valid).
Props: `{ children, className, strength=10, ...rest }`. Disabled for reduced motion / coarse pointer.
```jsx
import { motion, useSpring } from 'framer-motion'
import { usePrefersReducedMotion } from './useReducedMotion'
const SPRING = { stiffness:220, damping:18, mass:0.4 }
export default function MagneticButton({ children, className='', strength=10, ...rest }) {
  const reduced = usePrefersReducedMotion()
  const x = useSpring(0, SPRING), y = useSpring(0, SPRING)
  const coarse = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches
  const magnetic = !reduced && !coarse
  const onMove = (e) => {
    if (!magnetic) return
    const r = e.currentTarget.getBoundingClientRect()
    x.set(((e.clientX - r.left)/r.width - 0.5)*2*strength)
    y.set(((e.clientY - r.top)/r.height - 0.5)*2*strength)
  }
  const onLeave = () => { x.set(0); y.set(0) }
  return (
    <motion.button className={className} style={magnetic ? { x, y } : undefined}
      onPointerMove={onMove} onPointerLeave={onLeave}
      whileTap={magnetic ? { scale:0.97 } : undefined} {...rest}>{children}</motion.button>
  )
}
```

### `src/fx/ClickSpark.jsx`
Radial spark on pointerdown. **Ephemeral canvas** — mounted only during a ~450ms burst then
removed — so the live-mode invariant `document.querySelectorAll('canvas').length === 1` holds
(map canvas only). Mount ONCE per route root. Props: `{ color='#CCFF00' }`. Reduced motion → no-op.
```jsx
import { useEffect, useRef, useState } from 'react'
import { usePrefersReducedMotion } from './useReducedMotion'
import './fx.css'
const LIFE_MS = 450, RAYS = 8
export default function ClickSpark({ color = '#CCFF00' }) {
  const reduced = usePrefersReducedMotion()
  const [active, setActive] = useState(false)
  const bursts = useRef([]), canvasRef = useRef(null), raf = useRef(0)
  useEffect(() => {
    if (reduced) return undefined
    const onDown = (e) => { bursts.current.push({ x:e.clientX, y:e.clientY, t0:performance.now() }); setActive(true) }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [reduced])
  useEffect(() => {
    if (!active) return undefined
    const canvas = canvasRef.current
    canvas.width = window.innerWidth; canvas.height = window.innerHeight
    const ctx = canvas.getContext('2d')
    const draw = (now) => {
      ctx.clearRect(0,0,canvas.width,canvas.height)
      bursts.current = bursts.current.filter((b) => now - b.t0 < LIFE_MS)
      if (!bursts.current.length) { setActive(false); return }
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.lineCap = 'round'
      for (const b of bursts.current) {
        const t = (now - b.t0)/LIFE_MS, ease = 1-(1-t)**3
        ctx.globalAlpha = 1 - t
        for (let i=0;i<RAYS;i++){
          const a=(i/RAYS)*Math.PI*2, r0=6+ease*18, r1=r0+7*(1-t)
          ctx.beginPath()
          ctx.moveTo(b.x+Math.cos(a)*r0, b.y+Math.sin(a)*r0)
          ctx.lineTo(b.x+Math.cos(a)*r1, b.y+Math.sin(a)*r1); ctx.stroke()
        }
      }
      ctx.globalAlpha = 1
      raf.current = requestAnimationFrame(draw)
    }
    raf.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf.current)
  }, [active, color])
  if (reduced || !active) return null
  return <canvas ref={canvasRef} className="fx-spark-canvas" aria-hidden="true" />
}
```

### `src/fx/CityDiorama.jsx`
r3f hero for the idle screen: instanced night-city blocks + lime/white light-trails streaming the
street grid, fog, slow orbit, cursor parallax. `dpr={[1,1.5]}`, low-power. `accelerate` speeds
trails ×4.5 during launch. Reduced motion → `frameloop="demand"`, no orbit/trail motion.
**Parent must lazy-load it and STOP rendering it once `world.status === 'live'`** (so canvas count
returns to 1). Props: `{ accelerate=false }`.
```jsx
import { useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { usePrefersReducedMotion } from './useReducedMotion'
import './fx.css'
const GRID=26, CELL=1.6, STREET_EVERY=5, TRAILS=220, SIZE=GRID*CELL
const _m=new THREE.Matrix4(),_q=new THREE.Quaternion(),_s=new THREE.Vector3(),_p=new THREE.Vector3()
const isStreet=(i)=>i%STREET_EVERY===0
function mulberry(seed){let a=seed;return()=>{a|=0;a=(a+0x6d2b79f5)|0;let t=Math.imul(a^(a>>>15),1|a);
  t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296}}
function Blocks(){
  const { count, matrices } = useMemo(() => {
    const mats=[], rng=mulberry(7)
    for(let gx=0;gx<GRID;gx++)for(let gz=0;gz<GRID;gz++){
      if(isStreet(gx)||isStreet(gz))continue
      const x=(gx-GRID/2)*CELL, z=(gz-GRID/2)*CELL
      const centerBoost=1-(Math.abs(x)+Math.abs(z))/SIZE
      const h=0.4+rng()*2.2+centerBoost*2.6*rng()
      _p.set(x,h/2,z); _s.set(CELL*(0.55+rng()*0.25),h,CELL*(0.55+rng()*0.25))
      mats.push(_m.clone().compose(_p.clone(),_q,_s.clone()))
    }
    return { count:mats.length, matrices:mats }
  }, [])
  return (
    <instancedMesh ref={(mesh)=>{ if(!mesh)return
        matrices.forEach((m,i)=>mesh.setMatrixAt(i,m)); mesh.instanceMatrix.needsUpdate=true }}
      args={[undefined,undefined,count]}>
      <boxGeometry args={[1,1,1]} /><meshLambertMaterial color="#17171b" />
    </instancedMesh>
  )
}
function Trails({ accelerate, frozen }){
  const ref=useRef()
  const particles=useMemo(()=>{ const rng=mulberry(23)
    return Array.from({length:TRAILS},()=>{ const alongX=rng()>0.5
      const streetIdx=Math.floor(rng()*(GRID/STREET_EVERY))*STREET_EVERY
      return { alongX, lane:(streetIdx-GRID/2)*CELL+(rng()-0.5)*0.5, pos:(rng()-0.5)*SIZE,
        speed:(3+rng()*8)*(rng()>0.5?1:-1), len:0.9+rng()*1.6, lime:rng()>0.22 } }) },[])
  useFrame((_,dt)=>{ const mesh=ref.current; if(!mesh||frozen)return
    const boost=accelerate?4.5:1
    for(let i=0;i<TRAILS;i++){ const t=particles[i]; t.pos+=t.speed*boost*dt
      if(t.pos>SIZE/2)t.pos=-SIZE/2; if(t.pos<-SIZE/2)t.pos=SIZE/2
      _p.set(t.alongX?t.pos:t.lane,0.07,t.alongX?t.lane:t.pos)
      _s.set(t.alongX?t.len:0.09,0.05,t.alongX?0.09:t.len)
      mesh.setMatrixAt(i,_m.compose(_p,_q,_s)) }
    mesh.instanceMatrix.needsUpdate=true })
  return (
    <instancedMesh ref={(mesh)=>{ ref.current=mesh; if(!mesh)return
        const lime=new THREE.Color('#CCFF00'), white=new THREE.Color('#F5F6F0')
        for(let i=0;i<TRAILS;i++)mesh.setColorAt(i,particles[i].lime?lime:white)
        if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true }}
      args={[undefined,undefined,TRAILS]}>
      <boxGeometry args={[1,1,1]} /><meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  )
}
function Scene({ accelerate, frozen }){
  const group=useRef(); const { camera, pointer }=useThree()
  useFrame((_,dt)=>{ if(group.current&&!frozen)group.current.rotation.y+=dt*0.03
    camera.position.x+=(16+pointer.x*2.2-camera.position.x)*0.03
    camera.position.y+=(13-pointer.y*1.4-camera.position.y)*0.03
    camera.lookAt(0,0.5,0) })
  return (<>
    <fog attach="fog" args={['#0a0a0b',20,58]} />
    <ambientLight intensity={0.35} />
    <directionalLight position={[8,18,6]} intensity={0.5} color="#dfe6e0" />
    <group ref={group}><Blocks /><Trails accelerate={accelerate} frozen={frozen} /></group>
  </>)
}
export default function CityDiorama({ accelerate=false }){
  const reduced=usePrefersReducedMotion()
  return (
    <div className="fx-diorama" aria-hidden="true">
      <Canvas dpr={[1,1.5]} frameloop={reduced?'demand':'always'}
        gl={{ antialias:false, powerPreference:'low-power' }}
        camera={{ position:[16,13,16], fov:38 }}>
        <color attach="background" args={['#0a0a0b']} />
        <Scene accelerate={accelerate} frozen={reduced} />
      </Canvas>
    </div>
  )
}
```

### `src/fx/fx.css`
```css
.fx-flap{display:inline-flex;white-space:pre;}
.fx-flap-char{display:inline-block;transform-origin:center 55%;backface-visibility:hidden;}
.fx-flap-char.flipping{animation:fx-flap-tick var(--fx-flap-ms,40ms) linear;}
@keyframes fx-flap-tick{0%{transform:rotateX(0)}49%{transform:rotateX(-88deg);filter:brightness(.6)}
  51%{transform:rotateX(88deg);filter:brightness(.6)}100%{transform:rotateX(0)}}
.fx-odo{display:inline-flex;font-variant-numeric:tabular-nums;}
.fx-odo-col{display:inline-block;position:relative;height:1.15em;overflow:hidden;line-height:1.15em;}
.fx-odo-digit{display:inline-block;}
.fx-scramble{white-space:pre-wrap;}
.fx-spark-canvas{position:fixed;inset:0;pointer-events:none;z-index:9999;}
.fx-diorama,.fx-diorama-fallback{position:absolute;inset:0;}
.fx-diorama-fallback{background:radial-gradient(90% 70% at 50% 85%,#131316 0%,#0a0a0b 70%);}
@media (prefers-reduced-motion: reduce){.fx-flap-char.flipping{animation:none;}}
```

---

## 4. `src/WorldCommand.jsx` + `WorldCommand.css` — redesign spec

Full working source for both files is preserved in the assistant's session transcript for
2026-07-09; the structural spec below is the source of truth for rebuild. **Keep ALL existing data
flow**: `useWorldSocket`, the single map rAF loop (dead-reckon + `buildAgentLayers` + lightPreset,
the ONLY map-driving rAF — add no competing loops), dual map init (Mapbox Standard vs
MapLibre+CARTO), weather overlays wiring, `flyTo`, speed endpoint.

**Imports added**: `lazy, Suspense` from react; `AnimatePresence, motion` from framer-motion;
`SplitFlap, Odometer, TextScramble, MagneticButton, ClickSpark` from `./fx/*`;
`const CityDiorama = lazy(() => import('./fx/CityDiorama'))`. CSS starts with
`@import './theme/signal.css'; @import './fx/fx.css';`.

**New state**: `statusWord` (cycles `['RESOLVING REGION','BUILDING ROADS','WAKING AGENTS']` on a
1.6s interval while `status==='starting'`). Constants `EASE=[0.16,1,0.3,1]`, `railVariants`
(staggerChildren .06, delayChildren .15), `chipVariants` (y:8→0 fade, .4s).

**Idle** (`status idle|ended`): a `.wc-stage` layer renders `<Suspense fallback={<div class="fx-diorama-fallback"/>}><CityDiorama accelerate={status==='starting'}/></Suspense>` + ONE `.wc-scrim`.
`<AnimatePresence mode="wait">` wraps hero: `<h1>` = `.wc-kicker` SplitFlap "LIVING" + SplitFlap
"WORLD"; `.wc-tag` = `<TextScramble>` tagline; `motion.form layoutId="command" .wc-prompt` with mono
input (lime caret) + `<MagneticButton type="submit">SIMULATE</MagneticButton>`; stamped mono chips
`.wc-suggestions`. **Deleted**: `.wc-aurora`, all gradients/glass.

**Launch**: `status==='starting'` → `motion.div layoutId="command" .wc-starting` rail (morphs from
the command bar) showing `<SplitFlap text={statusWord}/>` + `.wc-starting-bar` lime hairline. Diorama
stays mounted with `accelerate` during starting, **unmounts at `live`** (stage only renders when
`idle || starting`).

**Live HUD** (`live && world.hello`, all under `railVariants`/`chipVariants` stagger):
- `.wc-topbar`: `.wc-region` chip = `<SplitFlap>` of `display_name.toUpperCase()` (keep fallback
  `<em>` roads note); weather chip stays **2nd child** (`.wc-chip:nth-child(2)` — verify depends on
  DOM order region→weather→clock); `.wc-clock` = `world.metrics.sim_clock` **plain text** (byte-stable
  tick check); optional tokenless `community basemap` chip; `.wc-speeds` segmented control — active
  button holds `motion.span layoutId="speed-ind" .wc-speed-ind` (sliding lime indicator, label in
  `<span>` above it); `.wc-stop` END button (alert-outline).
- `.wc-metrics`: four flat tiles, values in `<b>` = `<Odometer>` (en_route int; avg_speed_kmh
  decimals=1; congestion decimals=1 + static `%` in a `.wc-unit span`, `<b class="is-alert">` when
  `congestion>60`; arrived int). **First `<b>` textContent must be a bare integer** for verify.
- `.wc-thoughts`: `.sig-label` head + `<AnimatePresence mode="popLayout">` of up to 6 `.wc-thought`
  `motion.button` mono ticker cards (mood accent = 2px left border, SIGNAL family), staggered.
- Report tab = `motion.button layoutId="report" .wc-report-tab`; report sheet =
  `motion.div layoutId="report" .wc-panel.wc-report` (tab morphs into sheet). Sentinel sheet =
  `.wc-panel` spring side-sheet (x:40→0) inside `<AnimatePresence>`. Keep `.wc-panel h3`, `.wc-close`,
  all fields.

`<ClickSpark />` mounted once in `.wc-root`. Rain/haze overlays (`.wc-rain`/`.wc-haze` +
`data-testid="rain-overlay"|"haze-overlay"`) unchanged (diegetic). CSS: full rewrite on `--sig-*`
tokens — hairline panels, mono, one CTA shadow, mood-* borders in SIGNAL family, `@media
(prefers-reduced-motion)` kills the progress-bar/rain speed. (Full CSS in transcript; ~300 lines.)

### `src/world/agentLayers.js` — MOOD_COLORS remap (only change)
Lines ~102–107: `stable:[204,255,0]`, `optimistic:[255,255,255]`, `frustrated:[255,154,61]`,
`panicked:[255,77,0]`. Nothing else in the file changes.

---

## 5. Phasing & commits (commit + PUSH each — do not batch)

- **S1**: signal.css + fx library (+ useReducedMotion + fx.css) + CityDiorama + /world idle redesign.
  Commit `SIGNAL S1: design tokens, fx library, living-city idle hero`.
- **S2**: /world live-HUD choreography (rail, odometer tiles, segmented speed, sheets, layout morphs)
  + agentLayers MOOD_COLORS. Commit `SIGNAL S2: choreographed live HUD (odometers, split-flap, layout morphs)`.
- **S3**: /hive re-skin (`HiveCommand.jsx`/`.css` onto signal.css tokens; verdict via SplitFlap, KPIs
  via Odometer, precision command input; kill the Bebas dependency on that route; deck.gl / Mapbox
  dark-v11 / SSE untouched) + verify + ledger updates + PR #1 refresh.

Commit trailers (chat-only model id must NOT appear in commits):
```
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018yfuESUFkhzyHFav3kmjLn
```

## 6. Verification gauntlet (before each commit)

1. `cd landing-react && npm run build` → clean.
2. Servers: from repo root `(uvicorn app:app --port 8000 --log-level warning >/dev/null 2>&1 &)`
   and `cd landing-react && (npm run dev -- --port 5173 >/dev/null 2>&1 &)`; wait with
   `until curl -sf http://localhost:5173 >/dev/null; do sleep 2; done` (bare foreground `sleep` is
   blocked — always wrap in an until-loop). Playwright launches with
   `chromium.launch({ executablePath:'/opt/pw-browsers/chromium' })`.
3. `node verify_world_ui.mjs` → must print `VERIFY PASSED`. Extend it to assert: idle has a
   `.wc-hero canvas` (diorama); when `.wc-topbar` present, `document.querySelectorAll('canvas').length === 1`
   (diorama unmounted); keep the 0-console-error gate (sandbox-blocked hosts already filtered); add a
   `reducedMotion:'reduce'` smoke (hero present, no errors). Screenshots → scratchpad
   (world-idle/live/weather.png). Kill servers after.
4. `python3 -m pytest -q` from repo root → **254 passed, 2 skipped** (backend untouched).
5. Send idle/live/rain screenshots to the user (diorama + flap timing is their visual call).

## 7. Guardrails
No Tailwind; only the two @fontsource deps. No cyan/purple, no text gradients, max one scrim, no
other backdrop-blur, no glow dots. `HiveCommand.*` untouched until S3. Backend untouched. Never add
`__init__.py` under `tests/`. Landing page untouched.

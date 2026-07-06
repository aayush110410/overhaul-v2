# Hyperframes Composition Brief: OVERHAUL

## Objective
Create a short cinematic launch-style brag video for OVERHAUL — a city/earth simulation platform that simulates traffic, air quality, and 3D flyovers of real corridors.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 20 seconds

## Source Material
- Project root: `/Users/aayushsharma/Desktop/Overhaul/OVERHAUL-main`
- Primary files read: `landing-react/index.html`, `landing-react/src/App.jsx`, `landing-react/src/styles.css`
- Product name: OVERHAUL (wordmark: OVER + lime HAUL, with ™)
- Tagline / strongest claim: "THE WORLD REIMAGINED" / "Simulating tomorrow, today." / "REDEFINING HOW CITIES MOVE & BREATHE"
- Key UI to recreate: the simulator — dark map card (lime border) + control panel with ORIGIN/DESTINATION inputs, the lime `SIMULATE →` button, a route line between green/orange pins, a live mono log, and a stats strip.
- Copy that must appear verbatim:
  - CITIES MOVE. CITIES BREATHE.
  - THE WORLD REIMAGINED
  - EDUCATION SIMULATION PLATFORM
  - SIMULATE
  - QWEN 3 · GEMINI 3 PRO · OPENSTREETMAP
  - SIMULATING TOMORROW, TODAY.
  - 10,000+ / 47% / 150+ / 2.3M (real platform stats)

## Creative Direction
- Tone preset: cinematic
- Creative direction: "a bold product trailer for a city-scale simulation engine — brutalist, lime-on-black, confident, no jokes"
- Interpretation: 5 full-bleed scenes, big Bebas Neue type, dramatic scale-in reveals (0.95→1.0) with short crossfades, deep bell accents on two hero beats, restraint elsewhere. The scale of the claims carries the energy, not speed.
- Angle: Treat OVERHAUL like a blockbuster trailer for a world-simulation engine — lean into the site's own epic voice, then pay it off on the real working simulator UI, not just marketing.
- Hook: black + lime corridor lines → "CITIES MOVE. CITIES BREATHE." slams in.
- Outro / punchline: OVERHAUL™ logo slam in lime + "SIMULATING TOMORROW, TODAY." + `LAUNCH THE SIMULATOR`.
- Avoid: generic SaaS language; abstract filler visuals; redesigning the brand.

## Visual Identity
- Background: #0a0a0a
- Text: #ffffff (mono labels rgba(255,255,255,0.6))
- Accent: #CCFF00 (lime, primary) + #ff4d00 (orange, cursor/destination)
- Display font: Bebas Neue (fallback 'Arial Narrow', sans-serif)
- Body/mono font: Space Mono (fallback monospace); Inter for paragraph
- Visual references: brutalist OVER+lime HAUL wordmark; lime-bordered dark cards; lime gradient SIMULATE button; green origin / orange destination pins; mono log lines; jackpot stat counters.

## Storyboard
Use `brag-output/brag-plan.md` as the creative contract. Scene summary (global time):
1. Hook — 0.0–3.2s — corridor lines draw, "CITIES MOVE. CITIES BREATHE." + `TRAFFIC · AIR · PEOPLE`.
2. Wordmark — 3.0–6.7s — OVER+HAUL lock with bell, "THE WORLD REIMAGINED", tag pill.
3. Product (centerpiece) — 6.5–11.7s — simulator UI; cursor clicks `SIMULATE →`; route draws between pins; log lines + stats populate.
4. Numbers — 11.5–16.2s — 4 stat cards count up (10,000+ / 47% / 150+ / 2.3M) + AI stack line.
5. Outro — 16.0–20.0s — OVERHAUL™ logo slam + tagline + CTA.

## Audio
- Audio role: cinematic support — steady clean bed + two big bell accents on the hero beats.
- Audio arc: fade in under the hook → carry wordmark + live demo with light UI accents → build through counting stats → swell into the final logo slam → fade to silence.
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (copied into `composition/assets/music/`).
- Music treatment: data-volume 0.35; fade in 0→0.6s; fade out 18.5→20.0s under the outro (animated `volume` on the timeline).
- Music cue guidance: bundled preset `happy-beats-business-moves-vol-12...music-cues.json` (~110 BPM). Strong-cue locks: SIMULATE click/route → 8.74s; big-stat payoff → 13.11s; logo slam → 17.47s. Beat grid available for staggered cards/log lines.
- Audio-reactive treatment: subtle — implemented as deterministic, timeline-driven "breathing" glow on the lime wordmark/accents and a slow bg glow pulse (seek-safe). True per-frame RMS extraction was NOT wired to keep the render deterministic and robust; documented per step-3 ("if extraction is unavailable, note it and skip"). No waveform/equalizer visuals.
- Audio-coupled moments:
  - Scene 1 headline slam — soft impact.
  - Scene 2 wordmark lock — deep bell.
  - Scene 3 cursor click on SIMULATE — UI click; log lines — soft drops; route complete — soft impact.
  - Scene 4 card reveals — chip stacks; 2.3M payoff — bell (beat-locked 13.11).
  - Scene 5 logo slam — bell (beat-locked 17.47).
- SFX selection guidance: match motion/interaction; cinematic restraint. Chosen files (copied into `composition/assets/sfx/`): impact/impactSoft_medium_000–001, impact/impactBell_heavy_000/003/004, interface/click_001, interface/drop_001–002, casino/chips-stack-1–3.
- SFX analysis guidance: `~/.claude/skills/brag/assets/sfx/sfx-analysis.md` — chosen low/medium HF-risk families (impactBell, impactSoft, drop, click, chips-stack).
- Audio files: copied into `brag-output/composition/assets/` (music + sfx). Relative paths from `composition/`.

## Hyperframes Instructions
- Standalone composition (`index.html`), one paused timeline on `window.__timelines["main"]`, built synchronously.
- Shared `#bg` layer (#0a0a0a) + transparent timed scene clips, each on its own track-index (1–5), short crossfade overlaps; wrapper opacity/scale animated (never animate `.clip` visibility).
- Show the real simulator UI (Scene 3) — the working product, not just landing copy.
- Count-up via deterministic GSAP onUpdate proxies (seek-safe).
- Beat locks marked `// beat-locked` in the timeline script (3 strong cues).
- Run `npm run check` (lint + validate + inspect) and snapshot key frames before render.

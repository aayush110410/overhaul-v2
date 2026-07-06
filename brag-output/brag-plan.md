# Brag Plan: OVERHAUL

## What is this app?
OVERHAUL is an education-first city/earth simulation platform: pick a real corridor on a map and it simulates traffic flow, air-quality, and a 3D flyover — combining a deterministic simulation engine with multi-model AI (Qwen 3 + Gemini 3 Pro) and OpenStreetMap to teach systems thinking.

## The angle
Treat it like a blockbuster trailer for a *world simulation engine*. The site's own voice is already epic — "THE WORLD REIMAGINED", "REDEFINING HOW CITIES MOVE & BREATHE", "Simulating tomorrow, today." We lean all the way in: lime-on-black, brutalist, huge type, dramatic reveals — then drop into the actual product (the dark map + lime control panel) so the trailer pays off on a real working tool, not just marketing. Specific to OVERHAUL because no generic SaaS would say "cities move & breathe" or count up 2,300,000 data points/day.

## Hook (first 2-3 seconds)
Black. Faint lime corridor lines draw across the frame. A line slams in, Bebas Neue, full-bleed:
**"CITIES MOVE. CITIES BREATHE."** — then a mono subline: `TRAFFIC · AIR · PEOPLE`. The hook is the world-statement; the product hasn't even appeared yet.

## Key moments (the middle)
- **The wordmark builds** — `OVER` (white) + `HAUL` (lime) lock to full scale with a deep bell hit; subtitle "THE WORLD REIMAGINED", tag "EDUCATION SIMULATION PLATFORM".
- **The product actually runs** (centerpiece) — recreate the simulator: dark map card with a lime border + a control panel. A cursor clicks the lime **SIMULATE →** button; a route draws from a green origin pin to an orange destination pin; mono log lines type in: `ROUTING…` → `AIR QUALITY MODELED` → `3D FLYOVER READY`.
- **The numbers** — the real jackpot stats count up one by one: `10,000+ SIMULATIONS RUN`, `47% EFFICIENCY GAIN`, `150+ CITIES`, `2,300,000 DATA POINTS / DAY`, with the AI stack line `QWEN 3 · GEMINI 3 PRO · OPENSTREETMAP`.

## Outro / punchline
Cut to black. `OVERHAUL™` slams full-screen in lime with a final bell + music swell. Tagline: **"SIMULATING TOMORROW, TODAY."** Small CTA underline: `LAUNCH THE SIMULATOR`. Hold, fade.

## User flow worth showing
Entry → key action → result, pulled straight from the real `/demo2` simulator + `/flyover` flow:
1. **Entry** — corridor inputs on the control panel (origin / destination).
2. **Action** — cursor clicks the lime `SIMULATE →` button.
3. **Result** — route line draws across the dark map + live log + stats panel populate (route found, AQI modeled, flyover ready). This is Scene 3, the centerpiece.

## Tone
- Preset: cinematic
- Creative direction: "a bold product trailer for a city-scale simulation engine — brutalist, lime-on-black, confident, no jokes"
- Interpretation: 5 full-bleed scenes, big Bebas Neue type, dramatic scale-in reveals (0.95→1.0) over hard cuts, deep bell accents on the two hero beats, restraint everywhere else — the scale of the claims carries the energy, not speed.

## Format: landscape — 1920x1080
## Duration: 20s (5 scenes)

## Visual identity (from the project)
- Background: #0a0a0a
- Accent: #CCFF00 (lime) — primary brand
- Secondary accent: #ff4d00 (orange) — cursor / destination pin / alerts
- Text: #ffffff (with rgba(255,255,255,0.6) mono labels)
- Display font: Bebas Neue (headings, wordmark, stat values)
- Body font: Space Mono (labels, logs, tags) + Inter (paragraph)
- Strongest visual element: the brutalist `OVER`+lime`HAUL` wordmark, and the dark map simulator UI — lime-bordered cards, the lime gradient `SIMULATE` button, the live log + stats grid, green/orange route pins.

## Share copy (draft)
Built OVERHAUL — pick any real city corridor and simulate its traffic, air quality, and a 3D flyover in one click. The world, reimagined. 🌐

## Audio direction
- Role: cinematic support — a steady, clean bed with two big bell accents on the hero beats.
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (steady and clean; bundled cinematic pick).
- Music treatment: start at 0.0, volume 0.35, 0.5s fade-in, fade out over the last ~1.5s under the outro slam. Let it swell into the final logo.
- Music cue guidance: preset read (vol-12, ~110 BPM). Lock 3 beats — SIMULATE click/route → **8.74s** (0.99); final stat payoff → **13.11s** (0.98); outro logo slam → **17.47s** (0.99, or 18.56s). Beat grid available for staggered log lines / stat cards.
- Audio-reactive treatment: subtle; use music RMS/bass to make the lime glow on the wordmark and the map card presence breathe. No waveform/equalizer visuals.
- SFX posture: sparse, motion-matched, cinematic restraint — 2-3 deep bells + a couple of UI accents. Nothing busy.
- Audio-coupled moments: cursor click on SIMULATE; log lines typing/dropping in; stat counters ticking up; logo slams.
- Restraint rule: no more than two heavy bell hits; SFX must never stack into noise; music never above 0.4.

## Storyboard

### Scene 1 — Hook: "Cities move. Cities breathe." — 3.0s
Black field, #0a0a0a. Faint lime (#CCFF00 @ low opacity) corridor/grid lines draw horizontally across the frame. Headline slams in Bebas Neue, huge, centered: "CITIES MOVE. CITIES BREATHE." (white, with "BREATHE" in lime). At ~1.6s a Space Mono subline fades under it: `TRAFFIC · AIR · PEOPLE`.
Sequential/interaction: yes — grid lines draw in first, then headline slams (0.3s), then subline.
Audio intent: low cinematic swell rising from silence; one soft impact as the headline lands.
Audio-coupled idea: impact/impactSoft_medium on the headline slam (~0.3s).
Music: vol-12 begins, fading in, low and steady.
Transition mood: dramatic (scale + fade to black flash) → Scene 2

### Scene 2 — Wordmark reveal — 3.5s
Full-bleed. `OVER` (white) + `HAUL` (lime) assemble to center and lock from scale 0.95→1.0 with a subtle lime glow. Subtitle in Space Mono below: "THE WORLD REIMAGINED". Top tag pill: `EDUCATION SIMULATION PLATFORM`. Deep bell on the lock.
Sequential/interaction: yes — OVER then HAUL settle, then subtitle, then tag.
Audio intent: the brand arrives — confident, resonant.
Audio-coupled idea: impact/impactBell_heavy_000 at the wordmark lock; lock toward strong cue ~8.74s if pacing allows.
Music: steady bed, gaining presence.
Transition mood: dramatic wipe → Scene 3

### Scene 3 — The product runs (CENTERPIECE) — 5.0s
Recreate the simulator UI: left = dark map card (lime 1px border, rgba(255,255,255,0.02) fill, faint street lines); right = control panel with two inputs (`ORIGIN`, `DESTINATION` in Space Mono) and a lime gradient `SIMULATE →` button. An orange (#ff4d00) cursor moves to the button and clicks it (button depresses + pulses). A route line draws across the map from a green origin pin to an orange destination pin (0→100% over ~1s). A mono log panel types three lines in sequence: `> ROUTING…` then `> AIR QUALITY MODELED` then `> 3D FLYOVER READY` (lime). A small stats strip flickers to life (ETA / AQI).
Sequential/interaction: yes — cursor clicks SIMULATE, route draws, then 3 log lines appear one by one (hold each ~0.8s; keep all visible after).
Audio intent: the tool feels alive and responsive.
Audio-coupled idea: interface/click_001 on the cursor click (~lock to 8.74s); interface/drop_001 per log line; soft impact when the route completes.
Music: steady, driving under the action.
Transition mood: clean hard cut → Scene 4

### Scene 4 — The numbers — 4.5s
Dark frame, section label `THE NUMBERS` (mono). Four stat cards arrive one by one, each value counting up in Bebas Neue: `10,000+ SIMULATIONS RUN`, `47% EFFICIENCY GAIN`, `150+ CITIES`, `2,300,000 DATA POINTS / DAY`. Under them, the AI stack line in mono: `QWEN 3 · GEMINI 3 PRO · OPENSTREETMAP`. The largest number (2.3M) lands as the payoff.
Sequential/interaction: yes — 4 cards reveal staggered (~0.6s apart, all in by ~3.0s), then HOLD the full set ~1.5s; counters tick up as motion. Flag: hold all cards on screen after the last reveal so every label is readable.
Audio intent: momentum and scale — each card lands with weight, the big number is the peak.
Audio-coupled idea: casino/chips-stack per card as counters tick; impact/impactBell_heavy_004 on the 2.3M payoff — lock toward strong cue ~13.11s.
Music: building toward the swell.
Transition mood: dramatic → Scene 5

### Scene 5 — Outro / logo slam — 4.0s
Cut to black. `OVERHAUL™` slams in full-screen, lime, scale 0.95→1.0 with glow. Tagline in Space Mono: "SIMULATING TOMORROW, TODAY." A small lime-underlined CTA below: `LAUNCH THE SIMULATOR`. Final bell + music swell, then both fade as it holds on black.
Sequential/interaction: yes — logo slam, then tagline, then CTA underline draws.
Audio intent: the payoff — biggest, most resonant moment, then graceful fade.
Audio-coupled idea: impact/impactBell_heavy_003 on the logo slam — lock toward strong cue ~17.47s; music fade-out over the final ~1.5s.
Music: swell into the slam, then fade to silence.
Transition mood: hold on black (end)

**Music mood for this video:** cinematic
**Audio summary:** A steady, clean ~110 BPM bed fades in under the world-statement hook, carries the wordmark and live product demo with restrained UI accents, builds through the counting stats, and swells into a final deep-bell logo slam before fading to black — two heavy bell hits total, everything else sparse.

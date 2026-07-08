# Cloud Context — Bugs Ledger

> Every bug detected in cloud sessions: symptom → root cause → fix → status. Purpose: a bug fixed once must never be re-introduced in a new session. Format:
> **[date] [component] Symptom** — root cause — fix (file:line) — **status**.

---

## Known pre-existing constraints (not bugs, but recorded so sessions don't misdiagnose them)
- **[2026-07-06] [llm] OpenRouter free-tier 429 throttling** — free models flap under load; the reasoning gateway degrades to physics fallback so runs always complete. Not a viz/code bug. Mitigation: ≤14 sentinels default, batch/cache; ~$5–10 credit enables full 49-sentinel runs.
- **[2026-07-06] [swarm] Injected-graph coordinate loss (latent bug, fix scheduled Phase 2)** — `swarm.py:253` overwrites `self._valid_edges` with NCR-only `reasoning.valid_edge_ids()`, and `build_hive_state` (swarm.py:897) / `_build_geojson` (swarm.py:936) resolve coords via NCR-only `node_coords()` → on any non-NCR injected graph, every sentinel silently disappears from output. Fix: derive valid edges from `self.edges`, add `self.nodes`-aware `_node_coords()`. **status: open, scheduled Phase 2 task 1.**

## Session-discovered bugs
- **[2026-07-06] [git] Push denied (403) on both channels** — local git proxy returns 403 on push (reads fine), and GitHub MCP `create_branch` returns "Resource not accessible by integration". Remote only shows `main`. Root cause: the Claude GitHub App integration currently lacks WRITE permission on `aayush110410/overhaul-v2`. Mitigations: commits `04661f678` (Phase 0) + `7611c2169` (Phase 1) are safe locally; a verified git bundle was sent to the user; an automatic push retry is scheduled every ~45 min. User action: grant the Claude GitHub App write access to this repo (github.com → Settings → Applications/Installations, or Claude's GitHub settings), then the retry will land the branch. — **status: open, auto-retrying.**
- (none yet)

# Cloud Context — Mistakes Ledger

> Mistakes made by the assistant (self-detected or user-flagged), recorded so they are NEVER repeated. Format per entry:
> **[date] Mistake** — what happened → **Rule** — what to do instead.

---

- **[2026-07-06] Duplicate anchor in plan-file edit** — an Edit that appended a new section heading identical to an existing pending heading created two "### Backend agent (pending)" anchors, breaking the next Edit (2 matches). → **Rule**: when editing scaffold headings, never re-emit a heading that already exists elsewhere in the file; verify anchor uniqueness before writing.
- **[2026-07-06] Subagent claimed the uploaded superpowers file "does not exist"** — a planning subagent searched only the repo, could not see `/root/.claude/uploads/…`, and flagged the task blocked. The parent session had already read the file. → **Rule**: subagents cannot see session uploads; never let a subagent's "file missing" verdict override a path the parent session has already read. Pass upload paths explicitly or handle them in the parent.
- **[2026-07-06] `tests/world/__init__.py` shadowed the real `world` package** — adding an `__init__.py` under `tests/world/` (while `tests/` itself has none) made pytest import the test dir as top-level package `world`, breaking `from world.region import …`. → **Rule**: this repo's tests use NO `__init__.py` files anywhere under `tests/`; never add one.
- **[2026-07-06] Built on unverified state after a harness reset** — after the session was interrupted and resumed, work continued assuming disk/git state was intact; a later commit revealed the container had rolled back and a whole commit was missing. → **Rule**: after ANY session interruption/resume, first re-verify `git log --oneline -3` and the existence of recently-created files before continuing.
- **[2026-07-06] Stale docs almost trusted** — `RENDERING_ENGINE_DELIVERY.md` / `DEMO4_CODEX_ARCHITECTURE.md` describe a Cesium engine that was deleted from the repo (0 code remains). → **Rule**: in this repo, verify every "✅ delivered" doc claim against actual files; `PATH.md` + `README.md` + code are the truth, older docs may describe deleted or aspirational work.

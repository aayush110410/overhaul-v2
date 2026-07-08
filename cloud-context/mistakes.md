# Cloud Context — Mistakes Ledger

> Mistakes made by the assistant (self-detected or user-flagged), recorded so they are NEVER repeated. Format per entry:
> **[date] Mistake** — what happened → **Rule** — what to do instead.

---

- **[2026-07-06] Duplicate anchor in plan-file edit** — an Edit that appended a new section heading identical to an existing pending heading created two "### Backend agent (pending)" anchors, breaking the next Edit (2 matches). → **Rule**: when editing scaffold headings, never re-emit a heading that already exists elsewhere in the file; verify anchor uniqueness before writing.
- **[2026-07-06] Subagent claimed the uploaded superpowers file "does not exist"** — a planning subagent searched only the repo, could not see `/root/.claude/uploads/…`, and flagged the task blocked. The parent session had already read the file. → **Rule**: subagents cannot see session uploads; never let a subagent's "file missing" verdict override a path the parent session has already read. Pass upload paths explicitly or handle them in the parent.
- **[2026-07-06] Stale docs almost trusted** — `RENDERING_ENGINE_DELIVERY.md` / `DEMO4_CODEX_ARCHITECTURE.md` describe a Cesium engine that was deleted from the repo (0 code remains). → **Rule**: in this repo, verify every "✅ delivered" doc claim against actual files; `PATH.md` + `README.md` + code are the truth, older docs may describe deleted or aspirational work.

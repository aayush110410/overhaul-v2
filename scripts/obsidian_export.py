#!/usr/bin/env python3
"""Export OVERHAUL code graph + MiroFish bridge + project docs to Obsidian vault.

Builds a navigable graph of .md notes with wikilinks, dataview-ready frontmatter,
and inline source for high-risk functions. Designed for Obsidian graph view
to show meaningful clusters and dependencies.

Vault: /Users/aayushsharma/Documents/Obsidian Vault/OVERHAUL/
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path("/Users/aayushsharma/Desktop/Overhaul/OVERHAUL-main")
VAULT_ROOT = Path("/Users/aayushsharma/Documents/Obsidian Vault/OVERHAUL")
GRAPH_DB = PROJECT_ROOT / ".code-review-graph" / "graph.db"
GRAPH_BRIDGE = PROJECT_ROOT / "engines/agent_simulation" / "graph_bridge.py"

# Map: kind -> subfolder
SUBFOLDERS = {
    "File": "files",
    "Class": "classes",
    "Function": "functions",
    "Test": "tests",
}
# Note slug helpers
PY_FENCE = "```python"
JS_FENCE = "```javascript"
TS_FENCE = "```typescript"
FENCE_BY_LANG = {"python": PY_FENCE, "javascript": JS_FENCE, "typescript": TS_FENCE, "tsx": TS_FENCE, "bash": "```bash"}


def slugify(qualified_name: str) -> str:
    """Convert 'engines/agent_simulation/swarm.py::UrbanSwarm.run' to a stable slug."""
    s = qualified_name.replace("/", "__").replace("::", "__")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s


def safe_note_name(qualified_name: str, kind: str) -> str:
    """Build a human-readable .md note filename."""
    base = qualified_name.split("::")[-1]
    return f"{base} ({kind.lower()}).md"


def connect() -> sqlite3.Connection:
    if not GRAPH_DB.exists():
        raise SystemExit(f"Graph DB not found: {GRAPH_DB}")
    return sqlite3.connect(str(GRAPH_DB))


def fetch_all(cur: sqlite3.Cursor, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def risk_map(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    cur = conn.cursor()
    rows = fetch_all(
        cur,
        """SELECT ri.qualified_name, ri.risk_score, ri.caller_count, ri.test_coverage,
                  ri.security_relevant, n.id AS node_id
           FROM risk_index ri LEFT JOIN nodes n ON ri.node_id = n.id""",
    )
    return {r["qualified_name"]: r for r in rows}


def all_nodes(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    return fetch_all(
        conn.cursor(),
        """SELECT id, kind, name, qualified_name, file_path, line_start, line_end,
                  language, parent_name, params, return_type, modifiers, is_test,
                  signature, community_id
           FROM nodes""",
    )


def all_edges(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    return fetch_all(
        conn.cursor(),
        """SELECT kind, source_qualified, target_qualified, file_path, line
           FROM edges""",
    )


def communities(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    return fetch_all(
        conn.cursor(),
        "SELECT id, name, level, parent_id, cohesion, size, dominant_language, description FROM communities",
    )


def flows(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    return fetch_all(
        conn.cursor(),
        """SELECT f.id, f.name, f.depth, f.node_count, f.file_count, f.criticality, f.path_json,
                  n.qualified_name AS entry_qualified, n.file_path AS entry_file
           FROM flows f LEFT JOIN nodes n ON f.entry_point_id = n.id
           ORDER BY f.criticality DESC""",
    )


def frontmatter(props: Dict[str, Any]) -> str:
    """YAML frontmatter for dataview + graph styling tags."""
    lines = ["---"]
    for k, v in props.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, str) and (":" in v or v.startswith("[") or v.startswith("{")):
            lines.append(f'{k}: "{v.replace(chr(34), chr(92)+chr(34))}"')
        elif v is None:
            lines.append(f"{k}: null")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def link(qname: str, kind: Optional[str] = None) -> str:
    """Render a wikilink to a node note (file-folder)."""
    base = qname.split("::")[-1]
    fname = f"{base} ({kind.lower()}).md" if kind else f"{base} (function).md"
    return f"[[{fname}]]"


def file_link(rel_path: str) -> str:
    """Render a wikilink to a file note (uses full relative path)."""
    name = Path(rel_path).name
    return f"[[{name} (file).md]]"


def fetch_source(file_path: str, line_start: int, line_end: int) -> str:
    """Pull a source slice from disk; returns '' if not found."""
    if not file_path or not line_start or not line_end:
        return ""
    full = Path("/Users/aayushsharma/Desktop/Overhaul/OVERHAUL-main") / file_path
    if not full.exists():
        return ""
    try:
        with full.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[max(0, line_start - 1):line_end])
    except Exception:
        return ""


def build_note_path(qname: str, kind: str) -> Path:
    folder = SUBFOLDERS.get(kind, "misc")
    return VAULT_ROOT / folder / safe_note_name(qname, kind)


def write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(content)


def emit_function_notes(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    risks: Dict[str, Dict[str, Any]],
) -> int:
    """One .md per Function/Test. High-risk functions get inline source."""
    by_qname = {n["qualified_name"]: n for n in nodes}

    # Outgoing/incoming edges by qualified name
    out_calls: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    in_calls: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in edges:
        if e["kind"] == "CALLS":
            out_calls[e["source_qualified"]].append(e)
            in_calls[e["target_qualified"]].append(e)

    count = 0
    for n in nodes:
        if n["kind"] not in ("Function", "Test"):
            continue
        qname = n["qualified_name"]
        r = risks.get(qname, {})
        risk = float(r.get("risk_score") or 0.0)
        untested = (r.get("test_coverage") or "unknown") == "untested"
        sec = bool(r.get("security_relevant"))

        tags = [
            f"kind/{n['kind'].lower()}",
            f"lang/{n['language'] or 'unknown'}",
        ]
        if sec:
            tags.append("security/relevant")
        if untested:
            tags.append("coverage/untested")
        if risk >= 0.6:
            tags.append("risk/high")
        elif risk >= 0.3:
            tags.append("risk/medium")
        else:
            tags.append("risk/low")
        if n["kind"] == "Test":
            tags.append("test/passing" if n.get("is_test") else "test/missing")

        props = {
            "qualified_name": qname,
            "kind": n["kind"],
            "file": n["file_path"],
            "line_start": n["line_start"],
            "line_end": n["line_end"],
            "language": n["language"],
            "parent": n["parent_name"] or "",
            "signature": n["signature"] or "",
            "risk_score": round(risk, 3),
            "caller_count": r.get("caller_count", 0) or 0,
            "test_coverage": r.get("test_coverage", "unknown"),
            "security_relevant": sec,
            "tags": tags,
        }
        body = [frontmatter(props), ""]

        # Summary
        body.append(f"# `{n['name']}`")
        body.append("")
        body.append(f"**Location**: {file_link(n['file_path'])} · L{n['line_start']}–L{n['line_end']}")
        body.append(f"**Kind**: {n['kind']} · **Language**: {n['language']}")
        if n.get("parent_name"):
            body.append(f"**Parent**: `{n['parent_name']}`")
        if n.get("params"):
            body.append(f"**Params**: `{n['params']}`")
        if n.get("return_type"):
            body.append(f"**Returns**: `{n['return_type']}`")
        if n.get("modifiers"):
            body.append(f"**Modifiers**: {n['modifiers']}")
        body.append("")
        body.append(f"**Risk**: {round(risk, 3)} · **Callers**: {r.get('caller_count', 0) or 0} · **Coverage**: {r.get('test_coverage', 'unknown')}")
        body.append("")

        # Calls
        calls = out_calls.get(qname, [])
        if calls:
            body.append("## Calls")
            body.append("")
            seen: Set[str] = set()
            for c in calls[:30]:
                tgt = c["target_qualified"]
                if tgt in seen or tgt == qname:
                    continue
                seen.add(tgt)
                tgt_kind = by_qname.get(tgt, {}).get("kind", "function")
                body.append(f"- {link(tgt, tgt_kind)}  _(L{c['line']})_")
            if len(calls) > 30:
                body.append(f"- _…and {len(calls) - 30} more_")
            body.append("")

        # Called by
        callers = in_calls.get(qname, [])
        if callers:
            body.append("## Called by")
            body.append("")
            seen = set()
            for c in callers[:30]:
                src = c["source_qualified"]
                if src in seen or src == qname:
                    continue
                seen.add(src)
                src_kind = by_qname.get(src, {}).get("kind", "function")
                body.append(f"- {link(src, src_kind)}  _(L{c['line']})_")
            if len(callers) > 30:
                body.append(f"- _…and {len(callers) - 30} more_")
            body.append("")

        # Source for high-risk functions
        if risk >= 0.45:
            src = fetch_source(n["file_path"], n["line_start"], n["line_end"])
            if src:
                fence = FENCE_BY_LANG.get(n["language"] or "python", PY_FENCE)
                body.append("## Source (high risk — inline)")
                body.append("")
                body.append(fence)
                body.append(src.rstrip())
                body.append(fence)
                body.append("")

        note_path = build_note_path(qname, n["kind"])
        write_note(note_path, "\n".join(body))
        count += 1
    return count


def emit_file_notes(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> int:
    """One .md per File. Contains children + back-references."""
    by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        if n["kind"] in ("Function", "Class", "Test"):
            by_file[n["file_path"]].append(n)

    # Imports per file
    imports: Dict[str, Set[str]] = defaultdict(set)
    imported_by: Dict[str, Set[str]] = defaultdict(set)
    for e in edges:
        if e["kind"] == "IMPORTS_FROM":
            imports[e["file_path"]].add(e["target_qualified"])
            imported_by[e["target_qualified"]].add(e["file_path"])

    count = 0
    for file_path, children in by_file.items():
        if not file_path:
            continue
        language = children[0]["language"] if children else "unknown"
        tags = [
            f"kind/file",
            f"lang/{language}",
        ]
        if "/tests/" in file_path or "/test_" in Path(file_path).name:
            tags.append("test/file")

        props = {
            "qualified_name": file_path,
            "kind": "File",
            "language": language,
            "function_count": sum(1 for c in children if c["kind"] == "Function"),
            "class_count": sum(1 for c in children if c["kind"] == "Class"),
            "test_count": sum(1 for c in children if c["kind"] == "Test"),
            "tags": tags,
        }
        body = [frontmatter(props), ""]
        body.append(f"# `{file_path}`")
        body.append("")
        body.append(f"**Language**: {language} · **{len(children)} symbols**")
        body.append("")

        # Functions
        fns = [c for c in children if c["kind"] == "Function"]
        if fns:
            body.append("## Functions")
            body.append("")
            for c in sorted(fns, key=lambda x: x["line_start"] or 0):
                body.append(f"- {link(c['qualified_name'], 'Function')}  L{c['line_start']}–L{c['line_end']}")
            body.append("")

        # Classes
        classes = [c for c in children if c["kind"] == "Class"]
        if classes:
            body.append("## Classes")
            body.append("")
            for c in sorted(classes, key=lambda x: x["line_start"] or 0):
                body.append(f"- {link(c['qualified_name'], 'Class')}  L{c['line_start']}–L{c['line_end']}")
            body.append("")

        # Tests
        tests = [c for c in children if c["kind"] == "Test"]
        if tests:
            body.append("## Tests")
            body.append("")
            for c in sorted(tests, key=lambda x: x["line_start"] or 0):
                body.append(f"- {link(c['qualified_name'], 'Test')}")
            body.append("")

        # Imports
        imp = imports.get(file_path, set())
        if imp:
            body.append("## Imports from")
            body.append("")
            for q in sorted(imp)[:30]:
                body.append(f"- `{q}`")
            if len(imp) > 30:
                body.append(f"- _…and {len(imp) - 30} more_")
            body.append("")

        # Imported by
        iby = imported_by.get(file_path, set())
        if iby:
            body.append("## Imported by")
            body.append("")
            for q in sorted(iby)[:30]:
                body.append(f"- `{q}`")
            if len(iby) > 30:
                body.append(f"- _…and {len(iby) - 30} more_")
            body.append("")

        note_path = build_note_path(file_path, "File")
        write_note(note_path, "\n".join(body))
        count += 1
    return count


def emit_class_notes(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> int:
    """One .md per Class with inheritance + member links."""
    by_qname = {n["qualified_name"]: n for n in nodes}
    inherits_from: Dict[str, List[str]] = defaultdict(list)
    inherited_by: Dict[str, List[str]] = defaultdict(list)
    for e in edges:
        if e["kind"] == "INHERITS":
            inherits_from[e["source_qualified"]].append(e["target_qualified"])
            inherited_by[e["target_qualified"]].append(e["source_qualified"])

    classes = [n for n in nodes if n["kind"] == "Class"]
    count = 0
    for n in classes:
        qname = n["qualified_name"]
        members = [c for c in nodes if c["kind"] in ("Function",) and c.get("parent_name") == n["name"] and c["file_path"] == n["file_path"]]
        tags = [
            f"kind/class",
            f"lang/{n['language'] or 'unknown'}",
        ]
        props = {
            "qualified_name": qname,
            "kind": "Class",
            "file": n["file_path"],
            "line_start": n["line_start"],
            "line_end": n["line_end"],
            "language": n["language"],
            "tags": tags,
        }
        body = [frontmatter(props), ""]
        body.append(f"# `{n['name']}`")
        body.append("")
        body.append(f"**Location**: {file_link(n['file_path'])} · L{n['line_start']}–L{n['line_end']}")
        body.append("")

        parents = inherits_from.get(qname, [])
        if parents:
            body.append("## Inherits from")
            body.append("")
            for p in parents:
                p_kind = by_qname.get(p, {}).get("kind", "class")
                body.append(f"- {link(p, p_kind)}")
            body.append("")

        kids = inherited_by.get(qname, [])
        if kids:
            body.append("## Inherited by")
            body.append("")
            for k in kids:
                k_kind = by_qname.get(k, {}).get("kind", "class")
                body.append(f"- {link(k, k_kind)}")
            body.append("")

        if members:
            body.append(f"## Members ({len(members)})")
            body.append("")
            for m in sorted(members, key=lambda x: x["line_start"] or 0):
                body.append(f"- {link(m['qualified_name'], 'Function')}  L{m['line_start']}–L{m['line_end']}")
            body.append("")

        note_path = build_note_path(qname, "Class")
        write_note(note_path, "\n".join(body))
        count += 1
    return count


def emit_mirofish_bridge() -> int:
    """Manually document the MiroFish bridge classes + NCR graph contents."""
    bridge_path = PROJECT_ROOT / "engines/agent_simulation" / "graph_bridge.py"
    if not bridge_path.exists():
        return 0

    notes_written = 0
    content = bridge_path.read_text(encoding="utf-8")
    classes_in_bridge = [
        ("engines/agent_simulation/graph_bridge.py::GraphEntity",
         "GraphEntity", "dataclass for a graph node (intersection, road, segment)"),
        ("engines/agent_simulation/graph_bridge.py::GraphRelation",
         "GraphRelation", "dataclass for an edge (connects_to, belongs_to_segment)"),
        ("engines/agent_simulation/graph_bridge.py::LocalKnowledgeGraph",
         "LocalKnowledgeGraph", "in-memory MiroFish knowledge graph of Delhi NCR"),
        ("engines/agent_simulation/graph_bridge.py::ZepKnowledgeGraph",
         "ZepKnowledgeGraph", "Zep Cloud backed graph with persistent agent memory"),
        ("engines/agent_simulation/graph_bridge.py::build_ncr_knowledge_graph",
         "build_ncr_knowledge_graph", "factory: builds 12 NCR nodes + 28+ roads + 7 segments"),
    ]

    for qname, cname, desc in classes_in_bridge:
        tags = ["mirofish/bridge", "kind/class", "lang/python"]
        props = {
            "qualified_name": qname,
            "kind": "MiroFishClass",
            "file": "engines/agent_simulation/graph_bridge.py",
            "tags": tags,
            "description": desc,
        }
        body = [frontmatter(props), ""]
        body.append(f"# `{cname}` — MiroFish Bridge")
        body.append("")
        body.append(f"**Role**: {desc}")
        body.append(f"**Source**: {file_link('engines/agent_simulation/graph_bridge.py')}")
        body.append("")
        body.append("## Key Methods")
        body.append("")
        if cname == "LocalKnowledgeGraph":
            for m in ["add_entity", "add_relation", "get_entity", "get_neighbors",
                      "query_entities", "get_road_between", "update_entity_property",
                      "get_congestion_snapshot", "to_dict"]:
                body.append(f"- `{m}(...)`")
        elif cname == "ZepKnowledgeGraph":
            for m in ["add_entity", "add_relation", "persist_agent_memory", "recall_agent_memory",
                      "get_congestion_snapshot", "to_dict"]:
                body.append(f"- `{m}(...)`")
        elif cname == "build_ncr_knowledge_graph":
            for m in ["build_ncr_knowledge_graph(nodes, edges, zep_api_key)"]:
                body.append(f"- `{m}`")
        else:
            body.append("- _(dataclass — fields only)_")
            body.append("")
            body.append("## Fields")
            body.append("")
            if cname == "GraphEntity":
                body.append("- `entity_id: str`")
                body.append("- `entity_type: str`  (intersection | road | commuter_profile | freight_corridor)")
                body.append("- `properties: Dict[str, Any]`")
            elif cname == "GraphRelation":
                body.append("- `source_id: str`")
                body.append("- `target_id: str`")
                body.append("- `relation_type: str`  (connects_to | belongs_to_segment | serves_corridor)")
                body.append("- `properties: Dict[str, Any]`")
        body.append("")
        body.append("## Source")
        body.append("")
        body.append("```python")
        # Pull the class block
        if cname in ("GraphEntity", "GraphRelation"):
            m = re.search(rf"@dataclass\nclass {cname}.*?(?=\n\nclass |\nclass |\Z)", content, re.DOTALL)
            if m:
                body.append(m.group(0).rstrip())
        elif cname in ("LocalKnowledgeGraph", "ZepKnowledgeGraph", "build_ncr_knowledge_graph"):
            m = re.search(rf"class {cname}.*?(?=\n\nclass |\nclass |\ndef |\Z)", content, re.DOTALL)
            if m:
                body.append(m.group(0).rstrip())
        body.append("```")
        body.append("")

        # Save under mirofish/ subfolder
        path = VAULT_ROOT / "mirofish" / f"{cname}.md"
        write_note(path, "\n".join(body))
        notes_written += 1

    # Top-level index
    index_props = {"tags": ["mirofish/index", "kind/index"]}
    idx = [frontmatter(index_props), ""]
    idx.append("# MiroFish Knowledge Graph Bridge")
    idx.append("")
    idx.append("The bridge between OVERHAUL's NCR simulation and MiroFish's agent cognition layer.")
    idx.append("")
    idx.append("**Source file**: `engines/agent_simulation/graph_bridge.py` (295 lines)")
    idx.append("")
    idx.append("## Graph Contents")
    idx.append("")
    idx.append("- **12 NCR intersection nodes** (Delhi, Gurgaon, Noida, Greater Noida, Faridabad, Ghaziabad, etc.)")
    idx.append("- **28+ road entities** with BPR params (dist_km, free_speed_kmh, capacity_vph, lanes, current_congestion, current_flow)")
    idx.append("- **7 population segment profiles** (office_workers, gig_workers, students, service_sector, industrial_workers, senior_citizens, high_income)")
    idx.append("- **Bidirectional `connects_to` relations** between adjacent nodes")
    idx.append("- **Cross-run agent memory** via Zep (`persist_agent_memory` / `recall_agent_memory`)")
    idx.append("")
    idx.append("## Classes")
    idx.append("")
    for qname, cname, desc in classes_in_bridge:
        idx.append(f"- [[{cname}.md|{cname}]] — {desc}")
    idx.append("")
    idx.append("## Audit Status")
    idx.append("")
    idx.append("- ⚠️ **Per audit 2026-06-03**: Zep imports also exist in `brains/backend.py` (the new ABC) — duplicate implementations. The graph_bridge.py path is the legacy one.")
    idx.append("- The MiroFish integration is **referenced but not actually used** in the running hive loop. `swarm.py:_init_backend` always picks `LocalKnowledgeGraphBackend`, never `ZepBackend`.")
    idx.append("")
    write_note(VAULT_ROOT / "mirofish" / "_index.md", "\n".join(idx))
    return notes_written


def emit_project_docs() -> int:
    """Index PATH.md, CONTEXT.md, HISTORY.md as Obsidian notes."""
    written = 0
    for src_name, title, tags in [
        ("PATH.md", "PATH.md — Definitive Architecture & Build Path", ["doc/path", "source/of-truth"]),
        ("CONTEXT.md", "CONTEXT.md — Current Snapshot", ["doc/context", "snapshot"]),
        ("HISTORY.md", "HISTORY.md — Chronological Log", ["doc/history", "chronology"]),
    ]:
        src = PROJECT_ROOT / src_name
        if not src.exists():
            continue
        content = src.read_text(encoding="utf-8")
        # Strip the in-doc title to avoid double-header
        props = {
            "qualified_name": src_name,
            "kind": "Doc",
            "tags": tags,
        }
        body = [frontmatter(props), ""]
        body.append(f"# {title}")
        body.append("")
        body.append("> _Source-of-truth: PATH.md wins. CONTEXT.md is snapshot. HISTORY.md is log._")
        body.append("")
        # Copy verbatim; Obsidian will render the markdown
        body.append(content)
        body.append("")
        path = VAULT_ROOT / "docs" / f"{src_name.replace('.md', '')}.md"
        write_note(path, "\n".join(body))
        written += 1
    return written


def emit_index(nodes, edges, risks, communities, flows) -> None:
    """Top-level vault index with dataview queries and graph stats."""
    # Stats
    by_kind = defaultdict(int)
    by_lang = defaultdict(int)
    for n in nodes:
        by_kind[n["kind"]] += 1
        by_lang[n["language"] or "unknown"] += 1
    by_edge_kind = defaultdict(int)
    for e in edges:
        by_edge_kind[e["kind"]] += 1

    untested_high_risk = sorted(
        [(q, r.get("risk_score", 0)) for q, r in risks.items() if r.get("test_coverage") == "untested" and (r.get("risk_score") or 0) >= 0.5],
        key=lambda x: -x[1],
    )[:15]

    top_critical_flows = flows[:8]

    props = {"tags": ["index", "kind/index"]}
    body = [frontmatter(props), ""]
    body.append("# OVERHAUL — Obsidian Knowledge Graph")
    body.append("")
    body.append("> Mirror of `/Users/aayushsharma/Desktop/Overhaul/OVERHAUL-main` for graph-view navigation.")
    body.append("> Generated 2026-06-03. See [[_audit-2026-06-03.md]] for the latest findings.")
    body.append("")
    body.append("## Stats")
    body.append("")
    body.append(f"- **Nodes**: {len(nodes)}  ({by_kind['Function']} functions · {by_kind['Class']} classes · {by_kind['File']} files · {by_kind['Test']} tests)")
    body.append(f"- **Edges**: {len(edges)}  ({by_edge_kind['CALLS']} CALLS · {by_edge_kind['IMPORTS_FROM']} IMPORTS_FROM · {by_edge_kind['INHERITS']} INHERITS · {by_edge_kind['TESTED_BY']} TESTED_BY · {by_edge_kind['REFERENCES']} REFERENCES)")
    body.append(f"- **Risks indexed**: {len(risks)}")
    body.append(f"- **Communities**: {len(communities)}")
    body.append(f"- **Critical flows**: {len(flows)}")
    body.append("")
    body.append("## Languages")
    body.append("")
    for lang, c in sorted(by_lang.items(), key=lambda x: -x[1]):
        body.append(f"- {lang}: {c} nodes")
    body.append("")
    body.append("## Folders")
    body.append("")
    body.append("- `files/` — one note per source file, contains child function/class links")
    body.append("- `functions/` — one note per function (1,707 notes). Each shows callers + callees + risk.")
    body.append("- `classes/` — one note per class with members and inheritance.")
    body.append("- `tests/` — one note per test (83 notes).")
    body.append("- `mirofish/` — manual index of the MiroFish bridge classes.")
    body.append("- `docs/` — PATH.md / CONTEXT.md / HISTORY.md mirrored as notes.")
    body.append("- `flows/` — critical call paths extracted from the code graph.")
    body.append("- `communities/` — auto-detected code clusters.")
    body.append("")

    body.append("## 🔥 Untested + High-Risk Functions (priority for test work)")
    body.append("")
    body.append("| Function | Risk | Callers |")
    body.append("|---|---:|---:|")
    for qname, score in untested_high_risk:
        r = risks[qname]
        # Build wikilink to the function note
        base = qname.split("::")[-1]
        body.append(f"| [[{base} (function).md]] | {round(score, 3)} | {r.get('caller_count', 0) or 0} |")
    body.append("")

    body.append("## 🌊 Critical Flows (top 8)")
    body.append("")
    body.append("| Flow | Depth | Nodes | Files | Criticality |")
    body.append("|---|---:|---:|---:|---:|")
    for f in top_critical_flows:
        body.append(f"| {f['name']} | {f['depth']} | {f['node_count']} | {f['file_count']} | {round(f['criticality'], 3)} |")
    body.append("")

    body.append("## 🚨 Critical Audit (2026-06-03)")
    body.append("")
    body.append("> See [[_audit-2026-06-03.md]] for the full audit. Key findings:")
    body.append("")
    body.append("1. **50 Sentinels run Dijkstra** — `swarm.py:183` creates `SurgicalAgent(llm_provider=None)`")
    body.append("2. **7 SegmentBrains return canned strings** — `segment_brain.py:110`")
    body.append("3. **Sequential, not parallel, hive loop** — no `asyncio.gather`")
    body.append("4. **No `/simulate/hive` endpoint** — frontend calls `/chat`")
    body.append("5. **PATH.md §8 delete list unexecuted** — `llm_client.py`, `archive/`, `agents/`, `traffic-god/`, `services/` all still on disk")
    body.append("6. **Dead deps in requirements.txt + package.json**")
    body.append("7. **No `LLMProvider` interface / router / cache / quota**")
    body.append("")

    write_note(VAULT_ROOT / "_index.md", "\n".join(body))


def emit_audit_note() -> None:
    """Mirror the audit findings as a vault note."""
    audit_path = Path(
        "/Users/aayushsharma/.claude/projects/-Users-aayushsharma-Desktop-Overhaul-OVERHAUL-main/memory/audit-findings-2026-06-03.md"
    )
    if not audit_path.exists():
        return
    content = audit_path.read_text(encoding="utf-8")
    # Strip YAML frontmatter for embedding
    content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
    props = {"tags": ["audit/2026-06-03", "kind/audit"]}
    body = [frontmatter(props), ""]
    body.append("# Audit Findings — 2026-06-03")
    body.append("")
    body.append("> Adversarial audit of OVERHAUL conducted 2026-06-03.")
    body.append("> Source: `~/.claude/projects/.../memory/audit-findings-2026-06-03.md`")
    body.append("")
    body.append(content)
    body.append("")
    write_note(VAULT_ROOT / "_audit-2026-06-03.md", "\n".join(body))


def emit_flows(flows_data) -> int:
    """One .md per critical flow with the call path."""
    written = 0
    for f in flows_data:
        name = f["name"]
        path_json = f.get("path_json", "[]")
        try:
            path = json.loads(path_json)
        except Exception:
            path = []
        props = {
            "name": name,
            "depth": f["depth"],
            "node_count": f["node_count"],
            "file_count": f["file_count"],
            "criticality": round(f["criticality"], 3),
            "entry": f.get("entry_qualified", ""),
            "tags": ["flow/critical", f"flow/depth-{f['depth']}"],
        }
        body = [frontmatter(props), ""]
        body.append(f"# Flow: `{name}`")
        body.append("")
        body.append(f"**Depth**: {f['depth']} · **Nodes**: {f['node_count']} · **Files**: {f['file_count']} · **Criticality**: {round(f['criticality'], 3)}")
        body.append("")
        if f.get("entry_qualified"):
            base = f["entry_qualified"].split("::")[-1]
            body.append(f"**Entry**: [[{base} (function).md]]")
            body.append("")
        body.append("## Call Path")
        body.append("")
        # path is a list of node IDs; resolve to qualified names
        conn_local = sqlite3.connect(str(GRAPH_DB))
        cur_local = conn_local.cursor()
        for i, step in enumerate(path, 1):
            if isinstance(step, int):
                row = cur_local.execute("SELECT qualified_name FROM nodes WHERE id=?", (step,)).fetchone()
                qn = row[0] if row else f"node_{step}"
            elif isinstance(step, str):
                qn = step
            else:
                qn = step.get("qualified_name", str(step)) if isinstance(step, dict) else str(step)
            base = qn.split("::")[-1]
            kind = "function"
            if "." in base or base.endswith("md"):
                kind = "file"
            body.append(f"{i}. [[{base} ({kind}).md]]")
        conn_local.close()
        body.append("")
        path_md = VAULT_ROOT / "flows" / f"{name}.md"
        write_note(path_md, "\n".join(body))
        written += 1
    return written


def emit_communities(communities_data) -> int:
    """One .md per community, with member node list."""
    written = 0
    for c in communities_data:
        name = c["name"]
        props = {
            "name": name,
            "cohesion": round(c["cohesion"], 3),
            "size": c["size"],
            "language": c["dominant_language"],
            "level": c["level"],
            "tags": ["community", f"lang/{c['dominant_language'] or 'unknown'}"],
        }
        body = [frontmatter(props), ""]
        body.append(f"# Community: `{name}`")
        body.append("")
        body.append(f"**Size**: {c['size']} nodes · **Cohesion**: {round(c['cohesion'], 3)} · **Language**: {c['dominant_language']}")
        if c.get("description"):
            body.append(f"**Description**: {c['description']}")
        body.append("")
        # Find nodes with this community_id via separate query
        body.append("> Run a Dataview query in this folder to list members.")
        body.append("")
        path_md = VAULT_ROOT / "communities" / f"{name}.md"
        write_note(path_md, "\n".join(body))
        written += 1
    return written


def main() -> None:
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    conn = connect()
    print("✓ Connected to graph.db")
    nodes = all_nodes(conn)
    edges = all_edges(conn)
    risks = risk_map(conn)
    comms = communities(conn)
    flows_data = flows(conn)
    print(f"✓ Loaded {len(nodes)} nodes, {len(edges)} edges, {len(risks)} risk records")

    print("→ Emitting file notes...")
    f = emit_file_notes(nodes, edges)
    print(f"  ✓ {f} file notes")
    print("→ Emitting class notes...")
    c = emit_class_notes(nodes, edges)
    print(f"  ✓ {c} class notes")
    print("→ Emitting function/test notes (with inline source for high-risk)...")
    fn = emit_function_notes(nodes, edges, risks)
    print(f"  ✓ {fn} function/test notes")
    print("→ Emitting MiroFish bridge notes...")
    m = emit_mirofish_bridge()
    print(f"  ✓ {m} MiroFish notes + index")
    print("→ Emitting project docs (PATH/CONTEXT/HISTORY)...")
    d = emit_project_docs()
    print(f"  ✓ {d} doc notes")
    print("→ Emitting critical flows...")
    fl = emit_flows(flows_data)
    print(f"  ✓ {fl} flow notes")
    print("→ Emitting communities...")
    co = emit_communities(comms)
    print(f"  ✓ {co} community notes")
    print("→ Emitting top-level index...")
    emit_index(nodes, edges, risks, comms, flows_data)
    print("→ Emitting audit mirror...")
    emit_audit_note()
    print("✓ DONE. Vault at:", VAULT_ROOT)


if __name__ == "__main__":
    main()

"""Regional policy packs: curated law/budget/land facts the engines consume.

Honest-limits design: a pack is a set of dated, sourced claims — not
omniscience. Engines receive the pack when one exists for the region and an
explicit ``policy_pack_missing`` flag when it doesn't (surfaced as a result
warning). Freshness beyond the pack is the PolicyAgent's job (Gemini
Google-Search grounding through the gateway, cached) — not this loader's.

Pack schema (``data/policy_packs/{key}.json``)::

    {
      "region": str, "as_of": "YYYY-MM",
      "facts":  [{"claim", "value", "unit", "source", "as_of", "confidence"}],
      "budget": {"fiscal_year", "headline_cr"|"headline_usd_b", items...},
      "land":   {"authority", "ownership_model", "master_plan"},
      "acts":   [str, ...]
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PACKS_DIR = Path(__file__).resolve().parent.parent / "data" / "policy_packs"


def load_policy_pack(key: Optional[str], packs_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load a region's policy pack, or None (callers must handle absence)."""
    if not key:
        return None
    path = (Path(packs_dir) if packs_dir else _PACKS_DIR) / f"{key}.json"
    if not path.exists():
        return None
    try:
        pack = json.loads(path.read_text())
    except Exception:
        logger.warning("unreadable policy pack %s", path, exc_info=True)
        return None
    if not isinstance(pack.get("facts"), list):
        logger.warning("policy pack %s missing facts[]", path)
        return None
    return pack

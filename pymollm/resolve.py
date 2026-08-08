"""Resolve molecule names to PDB IDs via RCSB search."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from pymollm.httputil import request_json

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry"


def resolve_structure(query: str, max_hits: int = 5) -> Dict[str, Any]:
    """Search RCSB for structures matching a free-text name/query."""
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "Empty query", "candidates": []}

    if _looks_like_pdb_id(q):
        meta = _entry_meta(q.upper())
        if meta:
            return {
                "ok": True,
                "query": q,
                "direct_pdb": q.upper(),
                "candidates": [meta],
                "recommendation": "use_direct",
            }

    candidates = _text_search(q, rows=max_hits)
    if not candidates:
        token = q.split()[0]
        if _looks_like_pdb_id(token):
            meta = _entry_meta(token.upper())
            if meta:
                return {
                    "ok": True,
                    "query": q,
                    "candidates": [meta],
                    "recommendation": "use_direct",
                }
        return {
            "ok": True,
            "query": q,
            "candidates": [],
            "recommendation": "ask_user",
            "message": f"No RCSB hits for '{q}'. Ask the user for a PDB id or local path.",
        }

    recommendation = "use_top" if len(candidates) == 1 else "ask_user"
    return {
        "ok": True,
        "query": q,
        "candidates": candidates,
        "recommendation": recommendation,
        "message": (
            f"Single clear hit: {candidates[0]['pdb_id']}"
            if recommendation == "use_top"
            else "Multiple candidates; ask the user to choose."
        ),
    }


def _looks_like_pdb_id(s: str) -> bool:
    s = s.strip()
    return len(s) == 4 and s[0].isdigit() and s[1:].isalnum()


def _text_search(query: str, rows: int = 5) -> List[Dict[str, Any]]:
    payload = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query},
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": rows},
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "score", "direction": "desc"}],
        },
    }
    try:
        data = request_json("POST", RCSB_SEARCH, json_body=payload, timeout=30.0)
    except Exception as exc:
        return [{"error": f"RCSB search failed: {exc}"}]

    if data.get("_empty"):
        return []

    ids = [
        hit.get("identifier")
        for hit in data.get("result_set", [])
        if hit.get("identifier")
    ]
    out: List[Dict[str, Any]] = []
    for pdb_id in ids:
        meta = _entry_meta(pdb_id)
        if meta:
            out.append(meta)
        else:
            out.append({"pdb_id": pdb_id, "title": "(unknown title)"})
    return out


def _entry_meta(pdb_id: str) -> Optional[Dict[str, Any]]:
    try:
        data = request_json(
            "GET",
            f"{RCSB_ENTRY}/{quote(pdb_id)}",
            timeout=20.0,
        )
    except Exception:
        return None
    if data.get("_empty"):
        return None
    struct = data.get("struct") or {}
    info = data.get("rcsb_entry_info") or {}
    return {
        "pdb_id": pdb_id.upper(),
        "title": struct.get("title") or "",
        "method": (info.get("experimental_method") or [""])[0]
        if isinstance(info.get("experimental_method"), list)
        else info.get("experimental_method") or "",
        "resolution": info.get("resolution_combined") or info.get("resolution") or None,
        "polymer_entity_count": info.get("polymer_entity_count"),
    }

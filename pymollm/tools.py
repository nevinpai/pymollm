"""Tool schemas and dispatch for the pymollm agent."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from typing import Any, Dict, List, Optional, Tuple

from pymollm import export as export_mod
from pymollm import science
from pymollm.providers.base import ToolSpec
from pymollm.resolve import resolve_structure
from pymollm.safety import assert_safe, split_commands
from pymollm.verify import verify_state

# Sentinel returned by ask_user to pause the agent loop
ASK_USER = "ASK_USER"


def tool_specs() -> List[ToolSpec]:
    return [
        ToolSpec(
            name="inspect_session",
            description="Inspect the current PyMOL session: objects, selections, atom counts. Optionally detail one object.",
            parameters={
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "Optional object to inspect in detail",
                    }
                },
            },
        ),
        ToolSpec(
            name="resolve_structure",
            description="Resolve a molecule/protein name to PDB candidates via RCSB. Call before asking the user when only a name is known.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Protein or molecule name, or PDB id",
                    },
                    "max_hits": {"type": "integer", "description": "Max candidates (default 5)"},
                },
                "required": ["query"],
            },
        ),
        ToolSpec(
            name="load_or_fetch",
            description="Fetch a PDB id from RCSB or load a local structure file into PyMOL.",
            parameters={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "PDB id (e.g. 1A19) or local file path",
                    },
                    "name": {
                        "type": "string",
                        "description": "Object name in PyMOL",
                    },
                },
                "required": ["source"],
            },
        ),
        ToolSpec(
            name="color_by_bfactor",
            description="Color a selection by B-factor (temperature factor) using spectrum.",
            parameters={
                "type": "object",
                "properties": {
                    "selection": {"type": "string", "description": "PyMOL selection (default all)"},
                    "palette": {"type": "string", "description": "Spectrum palette (default rainbow)"},
                    "minimum": {"type": "number"},
                    "maximum": {"type": "number"},
                },
            },
        ),
        ToolSpec(
            name="select_residues",
            description="Create a named selection from residue numbers (e.g. '45+50-55+72').",
            parameters={
                "type": "object",
                "properties": {
                    "residues": {
                        "type": "string",
                        "description": "Residue numbers: '10+20-25' or '10,20,30'",
                    },
                    "name": {"type": "string", "description": "Selection name"},
                    "object_name": {"type": "string", "description": "Limit to object"},
                    "chain": {"type": "string", "description": "Limit to chain"},
                },
                "required": ["residues"],
            },
        ),
        ToolSpec(
            name="align_and_report_rmsd",
            description="Align one object/selection onto another and report RMSD.",
            parameters={
                "type": "object",
                "properties": {
                    "mobile": {"type": "string", "description": "Mobile object/selection"},
                    "target": {"type": "string", "description": "Target object/selection"},
                    "method": {
                        "type": "string",
                        "enum": ["align", "super", "cealign"],
                        "description": "Alignment method",
                    },
                },
                "required": ["mobile", "target"],
            },
        ),
        ToolSpec(
            name="show_solvent_around",
            description="Show solvent/water molecules near a selection.",
            parameters={
                "type": "object",
                "properties": {
                    "selection": {"type": "string"},
                    "radius": {"type": "number", "description": "Distance in Angstroms"},
                    "representation": {
                        "type": "string",
                        "description": "e.g. nb_spheres, spheres, lines",
                    },
                },
            },
        ),
        ToolSpec(
            name="run_pymol",
            description="Execute one or more raw PyMOL commands (PML). Use for capabilities not covered by typed tools. Prefer small batches.",
            parameters={
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of PyMOL commands",
                    },
                    "script": {
                        "type": "string",
                        "description": "Alternative: multiline/semicolon-separated PML",
                    },
                },
            },
        ),
        ToolSpec(
            name="verify_state",
            description="Verify post-conditions: objects exist, selections nonempty, min atom counts.",
            parameters={
                "type": "object",
                "properties": {
                    "objects_exist": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "selections_nonempty": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "min_atoms": {
                        "type": "array",
                        "description": "Minimum atom counts: [{selection, count}, ...]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "selection": {"type": "string"},
                                "count": {"type": "integer"},
                            },
                            "required": ["selection", "count"],
                        },
                    },
                },
            },
        ),
        ToolSpec(
            name="ask_user",
            description="Ask the user a clarifying question via the PyMOL CLI. The agent pauses until they reply with llm_answer. Include numbered candidates when helpful.",
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Clear question for the user",
                    },
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional candidate answers to list",
                    },
                },
                "required": ["question"],
            },
        ),
    ]


def inspect_session(object_name: str = "") -> Dict[str, Any]:
    try:
        from pymol import cmd
    except ImportError:
        return {"ok": False, "error": "pymol not available"}

    objects = list(cmd.get_object_list("all") or [])
    names = list(cmd.get_names("all") or [])
    selections = [n for n in names if n not in objects]
    summary: Dict[str, Any] = {
        "ok": True,
        "objects": [],
        "selections": selections,
    }
    for obj in objects:
        try:
            n_atoms = int(cmd.count_atoms(obj))
        except Exception:
            n_atoms = -1
        chains: List[str] = []
        try:
            from pymol import stored

            stored.chains = []
            cmd.iterate(obj, "stored.chains.append(chain)")
            chains = sorted({c for c in stored.chains if c})
        except Exception:
            chains = []
        entry: Dict[str, Any] = {
            "name": obj,
            "atoms": n_atoms,
            "chains": chains,
        }
        if object_name and obj == object_name:
            try:
                from pymol import stored

                stored.resis = []
                cmd.iterate(f"({obj}) and name CA", "stored.resis.append(resi)")
                resis = sorted({int(r) for r in stored.resis if str(r).lstrip("-").isdigit()})
                entry["ca_residues"] = resis[:50]
                entry["ca_residue_count"] = len(resis)
                if len(resis) > 50:
                    entry["ca_residues_note"] = "truncated to first 50 sorted"
            except Exception as exc:
                entry["detail_error"] = str(exc)
        summary["objects"].append(entry)
    return summary


def run_pymol(commands: Optional[List[str]] = None, script: str = "") -> Dict[str, Any]:
    cmds: List[str] = []
    if commands:
        cmds.extend(commands)
    if script:
        cmds.extend(split_commands(script))
    if not cmds:
        return {"ok": False, "error": "No commands provided"}
    try:
        safe = assert_safe(cmds)
    except PermissionError as exc:
        return {"ok": False, "error": str(exc), "blocked": True}

    try:
        from pymol import cmd
    except ImportError:
        return {"ok": False, "error": "pymol not available"}

    buf = io.StringIO()
    errors: List[str] = []
    with redirect_stdout(buf):
        for c in safe:
            try:
                cmd.do(c)
            except Exception as exc:
                errors.append(f"{c} -> {exc}")
    export_mod.append_commands(safe)
    # Post summary
    try:
        objects = list(cmd.get_object_list("all") or [])
    except Exception:
        objects = []
    return {
        "ok": not errors,
        "commands": safe,
        "stdout": buf.getvalue().strip(),
        "errors": errors,
        "objects_now": objects,
    }


def dispatch(
    name: str, arguments: Dict[str, Any]
) -> Tuple[str, Any]:
    """
    Execute a tool.
    Returns (status, payload) where status is 'ok' | 'error' | ASK_USER.
    For ASK_USER, payload is {"question": str, "choices": list}.
    """
    args = arguments or {}
    try:
        if name == "inspect_session":
            return "ok", inspect_session(object_name=str(args.get("object_name") or ""))
        if name == "resolve_structure":
            return "ok", resolve_structure(
                query=str(args.get("query") or ""),
                max_hits=int(args.get("max_hits") or 5),
            )
        if name == "load_or_fetch":
            return "ok", science.load_or_fetch(
                source=str(args.get("source") or ""),
                name=str(args.get("name") or ""),
            )
        if name == "color_by_bfactor":
            return "ok", science.color_by_bfactor(
                selection=str(args.get("selection") or "all"),
                palette=str(args.get("palette") or "rainbow"),
                minimum=args.get("minimum"),
                maximum=args.get("maximum"),
            )
        if name == "select_residues":
            return "ok", science.select_residues(
                residues=str(args.get("residues") or ""),
                name=str(args.get("name") or "sele_llm"),
                object_name=str(args.get("object_name") or ""),
                chain=str(args.get("chain") or ""),
            )
        if name == "align_and_report_rmsd":
            return "ok", science.align_and_report_rmsd(
                mobile=str(args.get("mobile") or ""),
                target=str(args.get("target") or ""),
                method=str(args.get("method") or "align"),
            )
        if name == "show_solvent_around":
            return "ok", science.show_solvent_around(
                selection=str(args.get("selection") or "all"),
                radius=float(args.get("radius") or 5.0),
                representation=str(args.get("representation") or "nb_spheres"),
            )
        if name == "run_pymol":
            return "ok", run_pymol(
                commands=args.get("commands"),
                script=str(args.get("script") or ""),
            )
        if name == "verify_state":
            return "ok", verify_state(
                objects_exist=args.get("objects_exist"),
                selections_nonempty=args.get("selections_nonempty"),
                min_atoms=_normalize_min_atoms(args.get("min_atoms")),
            )
        if name == "ask_user":
            question = str(args.get("question") or "").strip()
            choices = args.get("choices") or []
            if not question:
                return "error", {"error": "ask_user requires a question"}
            return ASK_USER, {"question": question, "choices": list(choices)}
        return "error", {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        return "error", {"error": f"{name} failed: {exc}"}


def format_tool_result(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


def _normalize_min_atoms(raw: Any) -> Optional[Dict[str, int]]:
    """Accept dict or [{selection, count}, ...] from the model."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items()}
    if isinstance(raw, list):
        out: Dict[str, int] = {}
        for item in raw:
            if isinstance(item, dict) and item.get("selection") is not None:
                out[str(item["selection"])] = int(item.get("count") or 0)
        return out or None
    return None

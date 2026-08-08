"""Typed science tools for reliable common PyMOL workflows."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any, Dict, List, Optional

from pymollm import export as export_mod
from pymollm.safety import assert_safe


def _cmd():
    from pymol import cmd

    return cmd


def _run(commands: List[str]) -> Dict[str, Any]:
    safe = assert_safe(commands)
    cmd = _cmd()
    buf = io.StringIO()
    errors: List[str] = []
    with redirect_stdout(buf):
        for c in safe:
            try:
                cmd.do(c)
            except Exception as exc:
                errors.append(f"{c} -> {exc}")
    export_mod.append_commands(safe)
    return {
        "ok": not errors,
        "commands": safe,
        "stdout": buf.getvalue().strip(),
        "errors": errors,
    }


def load_or_fetch(
    source: str,
    name: str = "",
    async_: int = 0,
) -> Dict[str, Any]:
    """Load a local structure file or fetch a PDB id."""
    src = (source or "").strip()
    if not src:
        return {"ok": False, "error": "source is required (PDB id or file path)"}
    obj = name.strip() if name else ""
    # Path-like?
    if any(ch in src for ch in ("/", "\\", ".")) and not _looks_like_pdb(src):
        obj = obj or _default_name_from_path(src)
        result = _run([f"load {src}, {obj}"])
        result["object"] = obj
        result["action"] = "load"
        return result
    pdb = src.upper()
    obj = obj or pdb
    # fetch TYPE, name=...
    result = _run([f"fetch {pdb}, async={int(async_)}, type=pdb, name={obj}"])
    result["object"] = obj
    result["action"] = "fetch"
    result["pdb_id"] = pdb
    return result


def color_by_bfactor(
    selection: str = "all",
    palette: str = "rainbow",
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> Dict[str, Any]:
    sel = selection or "all"
    cmds = [f"spectrum b, {palette}, {sel}"]
    if minimum is not None and maximum is not None:
        cmds = [f"spectrum b, {palette}, {sel}, minimum={minimum}, maximum={maximum}"]
    result = _run(cmds)
    result["note"] = f"Colored {sel} by B-factor using spectrum ({palette})"
    return result


def select_residues(
    residues: str,
    name: str = "sele_llm",
    object_name: str = "",
    chain: str = "",
) -> Dict[str, Any]:
    """Create a selection from residue numbers like '10+20-25+40' or '10,20,30'."""
    resi = _normalize_resi(residues)
    if not resi:
        return {"ok": False, "error": "residues string is empty or invalid"}
    parts = [f"resi {resi}"]
    if chain:
        parts.append(f"chain {chain}")
    if object_name:
        parts.append(object_name)
    expr = " and ".join(parts)
    sel_name = name or "sele_llm"
    result = _run([f"select {sel_name}, {expr}", f"indicate {sel_name}"])
    try:
        count = int(_cmd().count_atoms(sel_name))
    except Exception:
        count = -1
    result["selection"] = sel_name
    result["expression"] = expr
    result["atom_count"] = count
    if count == 0:
        result["ok"] = False
        result["error"] = f"Selection '{sel_name}' is empty ({expr})"
    return result


def align_and_report_rmsd(
    mobile: str,
    target: str,
    method: str = "align",
    cycles: int = 5,
    cutoff: float = 2.0,
    object_name: str = "",
) -> Dict[str, Any]:
    """Align mobile onto target and report RMSD."""
    cmd = _cmd()
    method = (method or "align").lower()
    if method not in ("align", "super", "cealign"):
        method = "align"
    buf = io.StringIO()
    rmsd = None
    raw = None
    err = None
    try:
        with redirect_stdout(buf):
            if method == "cealign":
                raw = cmd.cealign(target, mobile)
                # cealign returns dict-like with RMSD
                if isinstance(raw, dict):
                    rmsd = raw.get("RMSD") or raw.get("rmsd")
            elif method == "super":
                raw = cmd.super(
                    mobile,
                    target,
                    cycles=cycles,
                    cutoff=cutoff,
                    object=object_name or None,
                )
            else:
                raw = cmd.align(
                    mobile,
                    target,
                    cycles=cycles,
                    cutoff=cutoff,
                    object=object_name or None,
                )
        # align/super return tuple: (RMSD after refinement, ...)
        if isinstance(raw, (list, tuple)) and raw:
            rmsd = float(raw[0])
        export_mod.append_commands(
            [
                f"{method} {mobile}, {target}"
                + (f", object={object_name}" if object_name else "")
            ]
        )
    except Exception as exc:
        err = str(exc)

    # Also compute CA rms_cur after alignment for a clear number
    ca_rmsd = None
    try:
        ca_rmsd = float(
            cmd.rms_cur(
                f"({mobile}) and name CA",
                f"({target}) and name CA",
                matchmaker=4,
            )
        )
        export_mod.append_commands(
            [
                f"rms_cur ({mobile}) and name CA, ({target}) and name CA, matchmaker=4"
            ]
        )
    except Exception:
        pass

    ok = err is None
    return {
        "ok": ok,
        "method": method,
        "mobile": mobile,
        "target": target,
        "rmsd": rmsd,
        "ca_rmsd_cur": ca_rmsd,
        "raw": _stringify(raw),
        "stdout": buf.getvalue().strip(),
        "error": err,
        "summary": (
            f"Aligned '{mobile}' onto '{target}' via {method}. "
            f"RMSD={rmsd if rmsd is not None else 'n/a'}; "
            f"CA rms_cur={ca_rmsd if ca_rmsd is not None else 'n/a'}"
        ),
    }


def show_solvent_around(
    selection: str = "all",
    radius: float = 5.0,
    representation: str = "nb_spheres",
) -> Dict[str, Any]:
    sel = selection or "all"
    rep = representation or "nb_spheres"
    solvent_sel = f"solvent within {radius} of ({sel})"
    cmds = [
        f"show {rep}, {solvent_sel}",
        f"select solvents_llm, {solvent_sel}",
    ]
    result = _run(cmds)
    try:
        count = int(_cmd().count_atoms("solvents_llm"))
    except Exception:
        count = -1
    result["atom_count"] = count
    result["selection"] = "solvents_llm"
    result["note"] = f"Showing solvent within {radius} Å of {sel} ({count} atoms)"
    return result


def _normalize_resi(residues: str) -> str:
    s = residues.replace(",", "+").replace(" ", "")
    # already PyMOL-ish?
    return s


def _looks_like_pdb(s: str) -> bool:
    s = s.strip()
    return len(s) == 4 and s[0].isdigit() and s[1:].isalnum()


def _default_name_from_path(path: str) -> str:
    import os

    base = os.path.basename(path)
    name = base.split(".")[0]
    return name or "obj"


def _stringify(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_stringify(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _stringify(v) for k, v in obj.items()}
    return str(obj)

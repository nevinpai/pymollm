"""Post-condition verification against the live PyMOL session."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def verify_state(
    objects_exist: Optional[List[str]] = None,
    selections_nonempty: Optional[List[str]] = None,
    min_atoms: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Check that expected objects/selections exist and meet atom-count floors."""
    try:
        from pymol import cmd
    except ImportError:
        return {"ok": False, "error": "pymol not available"}

    failures: List[str] = []
    details: Dict[str, Any] = {}

    names = set(cmd.get_names("all"))
    objects = set(cmd.get_object_list("all") or [])

    for obj in objects_exist or []:
        present = obj in objects or obj in names
        details[f"object:{obj}"] = present
        if not present:
            failures.append(f"Missing object '{obj}'")

    for sel in selections_nonempty or []:
        try:
            n = int(cmd.count_atoms(sel))
        except Exception as exc:
            n = -1
            failures.append(f"Selection '{sel}' invalid: {exc}")
        details[f"selection:{sel}:atoms"] = n
        if n == 0:
            failures.append(f"Selection '{sel}' is empty")

    for sel, floor in (min_atoms or {}).items():
        try:
            n = int(cmd.count_atoms(sel))
        except Exception as exc:
            n = -1
            failures.append(f"Could not count atoms for '{sel}': {exc}")
            continue
        details[f"min_atoms:{sel}"] = {"have": n, "need": floor}
        if n < int(floor):
            failures.append(f"'{sel}' has {n} atoms; need >= {floor}")

    return {
        "ok": not failures,
        "failures": failures,
        "details": details,
        "objects": sorted(objects),
        "names": sorted(names),
    }

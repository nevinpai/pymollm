"""Session undo snapshots via PyMOL get_session / set_session."""

from __future__ import annotations

from typing import Any, Optional

_snapshot: Optional[Any] = None


def take_snapshot() -> bool:
    global _snapshot
    try:
        from pymol import cmd
    except ImportError:
        return False
    try:
        _snapshot = cmd.get_session()
        return True
    except Exception:
        _snapshot = None
        return False


def restore_snapshot() -> bool:
    global _snapshot
    if _snapshot is None:
        return False
    try:
        from pymol import cmd
    except ImportError:
        return False
    try:
        cmd.set_session(_snapshot)
        return True
    except Exception:
        return False


def has_snapshot() -> bool:
    return _snapshot is not None


def clear_snapshot() -> None:
    global _snapshot
    _snapshot = None

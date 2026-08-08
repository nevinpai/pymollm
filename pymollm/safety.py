"""Command safety checks before executing PyMOL commands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List

# Commands / patterns that must never be auto-run
_BLOCKED_PATTERNS = [
    re.compile(r"^\s*quit\b", re.I),
    re.compile(r"^\s*reinitialize\b", re.I),
    re.compile(r"^\s*delete\s+all\b", re.I),
    re.compile(r"^\s*remove\s+all\b", re.I),
    re.compile(r"^\s*system\b", re.I),
    re.compile(r"^\s*/\s*", re.I),  # shell escape in some PyMOL builds
    re.compile(r"^\s*shell\b", re.I),
    re.compile(r"^\s*spawn\b", re.I),
    re.compile(r"^\s*cd\b", re.I),
    re.compile(r"^\s*pwd\b", re.I),
    re.compile(r"python\s", re.I),
    re.compile(r"^\s*run\b", re.I),
    re.compile(r"^\s*@"),  # script include
    re.compile(r"__import__"),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"os\.system"),
    re.compile(r"subprocess"),
]


@dataclass
class SafetyResult:
    ok: bool
    blocked: List[str]
    commands: List[str]


def split_commands(text: str) -> List[str]:
    """Split a PML snippet into individual commands."""
    parts: List[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for piece in line.split(";"):
            piece = piece.strip()
            if piece:
                parts.append(piece)
    return parts


def check_commands(commands: Iterable[str]) -> SafetyResult:
    cleaned = [c.strip() for c in commands if c and str(c).strip()]
    blocked: List[str] = []
    for cmd in cleaned:
        for pat in _BLOCKED_PATTERNS:
            if pat.search(cmd):
                blocked.append(cmd)
                break
    return SafetyResult(ok=not blocked, blocked=blocked, commands=cleaned)


def assert_safe(commands: Iterable[str]) -> List[str]:
    result = check_commands(commands)
    if not result.ok:
        raise PermissionError(
            "Blocked unsafe PyMOL command(s): " + "; ".join(result.blocked)
        )
    return result.commands

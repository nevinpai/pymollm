"""pymollm — natural-language agent for PyMOL."""

from __future__ import annotations

__version__ = "0.1.0"


def __init_plugin__(app=None):
    """PyMOL plugin entrypoint."""
    from pymollm.cli import register

    register()
    print(f"pymollm {__version__} loaded. Try: llm_config | llm <prompt> | llm_status")


def setup():
    """Manual load helper: run pymollm.setup() or import + __init_plugin__."""
    __init_plugin__()

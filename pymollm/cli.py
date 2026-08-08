"""PyMOL CLI command implementations for pymollm."""

from __future__ import annotations

from typing import Any

from pymollm import agent
from pymollm import export as export_mod
from pymollm import session as session_mod
from pymollm.config import CONFIG_PATH, load_config, update_config


def _join_args(args: tuple) -> str:
    return " ".join(str(a) for a in args).strip()


def llm_cmd(*args: Any, _self=None, **kwargs: Any) -> None:
    """llm <natural language prompt>"""
    agent.run_prompt(_join_args(args))


def llm_answer_cmd(*args: Any, _self=None, **kwargs: Any) -> None:
    """llm_answer <text>"""
    agent.answer(_join_args(args))


_CONFIG_FIELDS = {
    "provider",
    "key",
    "api_key",
    "model",
    "base_url",
    "max_steps",
    "export_dir",
}


def _parse_config_text(text: str) -> dict:
    """Parse config tokens such as: provider gemini key AIza... model gemini-2.5-flash."""
    tokens = text.split()
    if not tokens:
        return {}
    out: dict = {}
    i = 0
    while i < len(tokens):
        field = tokens[i].lower()
        if field not in _CONFIG_FIELDS:
            raise ValueError(
                f"unknown config field '{tokens[i]}'. "
                "Fields: provider, key, model, base_url, max_steps, export_dir"
            )
        i += 1
        value_parts = []
        while i < len(tokens) and tokens[i].lower() not in _CONFIG_FIELDS:
            value_parts.append(tokens[i])
            i += 1
        if not value_parts:
            raise ValueError(f"missing value for '{field}'")
        value = " ".join(value_parts)
        if field in ("key", "api_key"):
            out["api_key"] = value
        elif field == "max_steps":
            out["max_steps"] = int(value)
        else:
            out[field] = value
    return out


def llm_config_cmd(*args: Any, _self=None, **kwargs: Any) -> None:
    """
    llm_config
    llm_config provider openai|anthropic|gemini
    llm_config key <api_key>
    llm_config model <model>
    llm_config base_url <url>
    llm_config max_steps <n>
    """
    text = _join_args(args)
    if not text:
        cfg = load_config()
        print("pymollm config:")
        for k, v in cfg.to_public_dict().items():
            print(f"  {k}: {v}")
        print(f"  config_file: {CONFIG_PATH}")
        return

    try:
        parsed = _parse_config_text(text)
        cfg = update_config(**parsed)
    except Exception as exc:
        print(f"pymollm: {exc}")
        return
    print("pymollm: config saved")
    for k, v in cfg.to_public_dict().items():
        print(f"  {k}: {v}")


def llm_status_cmd(*args: Any, _self=None, **kwargs: Any) -> None:
    """llm_status"""
    st = agent.status_dict()
    print("pymollm status:")
    for k, v in st.items():
        print(f"  {k}: {v}")


def llm_clear_cmd(*args: Any, _self=None, **kwargs: Any) -> None:
    """llm_clear — clear conversation and pending ask"""
    agent.clear_history()
    export_mod.reset_log()
    print("pymollm: conversation cleared")


def llm_undo_cmd(*args: Any, _self=None, **kwargs: Any) -> None:
    """llm_undo — restore session snapshot from start of last llm turn"""
    if not session_mod.has_snapshot():
        print("pymollm: no undo snapshot available")
        return
    if session_mod.restore_snapshot():
        print("pymollm: session restored")
    else:
        print("pymollm: failed to restore session")


def llm_export_cmd(*args: Any, _self=None, **kwargs: Any) -> None:
    """llm_export [path.pml] — export last command transcript"""
    path = _join_args(args) or None
    try:
        out = export_mod.export_pml(path)
    except Exception as exc:
        print(f"pymollm: export failed: {exc}")
        return
    print(f"pymollm: wrote {out}")


def register() -> None:
    """Register commands with pymol.cmd."""
    from pymol import cmd

    cmd.extend("llm", llm_cmd)
    cmd.extend("llm_answer", llm_answer_cmd)
    cmd.extend("llm_config", llm_config_cmd)
    cmd.extend("llm_status", llm_status_cmd)
    cmd.extend("llm_clear", llm_clear_cmd)
    cmd.extend("llm_undo", llm_undo_cmd)
    cmd.extend("llm_export", llm_export_cmd)

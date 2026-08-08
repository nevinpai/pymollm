"""Tool-calling agent loop with ask_user pause/resume."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pymollm import export as export_mod
from pymollm import session as session_mod
from pymollm.config import load_config
from pymollm.prompts import SYSTEM_PROMPT, session_context_preamble
from pymollm.providers import get_client
from pymollm.providers.base import Message, ToolCall
from pymollm.tools import ASK_USER, dispatch, format_tool_result, inspect_session, tool_specs


@dataclass
class PendingAsk:
    question: str
    choices: List[str]
    tool_call_id: str
    tool_name: str = "ask_user"


@dataclass
class AgentState:
    messages: List[Message] = field(default_factory=list)
    pending_ask: Optional[PendingAsk] = None
    last_error: str = ""
    last_summary: str = ""
    turn_active: bool = False


_state = AgentState()


def get_state() -> AgentState:
    return _state


def clear_history() -> None:
    _state.messages.clear()
    _state.pending_ask = None
    _state.last_error = ""
    _state.last_summary = ""
    _state.turn_active = False


def status_dict() -> Dict[str, Any]:
    cfg = load_config()
    return {
        "provider": cfg.provider,
        "model": cfg.resolved_model(),
        "api_key_set": bool(cfg.api_key),
        "pending_ask": (
            {
                "question": _state.pending_ask.question,
                "choices": _state.pending_ask.choices,
            }
            if _state.pending_ask
            else None
        ),
        "history_messages": len(_state.messages),
        "has_undo_snapshot": session_mod.has_snapshot(),
        "commands_logged": len(export_mod.get_log()),
        "last_error": _state.last_error or None,
        "last_summary": _state.last_summary or None,
    }


def _print(msg: str) -> None:
    print(f"pymollm: {msg}")


def _ensure_system() -> None:
    if not _state.messages or _state.messages[0].role != "system":
        _state.messages.insert(0, Message(role="system", content=SYSTEM_PROMPT))


def run_prompt(prompt: str) -> None:
    """Start a new user turn from `llm`."""
    text = (prompt or "").strip()
    if not text:
        _print('Usage: llm <natural language prompt>')
        return
    if _state.pending_ask:
        _print(
            "There is a pending question. Answer with llm_answer, "
            "or llm_clear to cancel."
        )
        _print_pending()
        return

    export_mod.reset_log()
    session_mod.take_snapshot()
    _ensure_system()

    # Inject live session context with the user message
    try:
        summary = json.dumps(inspect_session(), default=str)
    except Exception:
        summary = "(could not inspect session)"
    user_content = session_context_preamble(summary) + "\nUser request:\n" + text
    _state.messages.append(Message(role="user", content=user_content))
    _state.turn_active = True
    _run_loop()


def answer(text: str) -> None:
    """Resume after ask_user via `llm_answer`."""
    reply = (text or "").strip()
    if not reply:
        _print("Usage: llm_answer <your answer>")
        return
    if not _state.pending_ask:
        _print("No pending question. Use llm <prompt> to start.")
        return

    pending = _state.pending_ask
    _state.pending_ask = None
    # If user picked a number and choices exist, expand it
    expanded = reply
    if reply.isdigit() and pending.choices:
        idx = int(reply) - 1
        if 0 <= idx < len(pending.choices):
            expanded = pending.choices[idx]
            _print(f"Interpreted choice {reply} as: {expanded}")

    _state.messages.append(
        Message(
            role="tool",
            name=pending.tool_name,
            tool_call_id=pending.tool_call_id,
            content=format_tool_result({"user_answer": expanded, "raw": reply}),
        )
    )
    _state.turn_active = True
    _run_loop()


def _print_pending() -> None:
    if not _state.pending_ask:
        return
    q = _state.pending_ask.question
    _print(q)
    for i, c in enumerate(_state.pending_ask.choices, 1):
        _print(f"  {i}) {c}")
    _print("Reply with: llm_answer <text or choice number>")


def _run_loop() -> None:
    cfg = load_config()
    try:
        client = get_client(cfg)
    except Exception as exc:
        _state.last_error = str(exc)
        _print(str(exc))
        _state.turn_active = False
        return

    tools = tool_specs()
    max_steps = max(1, int(cfg.max_steps or 16))

    for step in range(max_steps):
        try:
            turn = client.complete(_state.messages, tools)
        except Exception as exc:
            _state.last_error = f"LLM error: {exc}"
            _print(_state.last_error)
            _state.turn_active = False
            return

        if turn.content and not turn.tool_calls:
            _state.messages.append(
                Message(
                    role="assistant",
                    content=turn.content,
                    raw_parts=list(turn.raw_parts or []),
                )
            )
            _state.last_summary = turn.content.strip()
            _print(turn.content.strip())
            _finish_turn()
            return

        if not turn.tool_calls:
            _print("(no response from model)")
            _state.turn_active = False
            return

        _state.messages.append(
            Message(
                role="assistant",
                content=turn.content or "",
                tool_calls=turn.tool_calls,
                raw_parts=list(turn.raw_parts or []),
            )
        )
        if turn.content:
            _print(turn.content.strip())

        # Process non-ask tools first so every tool_call_id gets a result
        # before we pause on ask_user (providers require paired tool results).
        ask_calls = [tc for tc in turn.tool_calls if tc.name == "ask_user"]
        other_calls = [tc for tc in turn.tool_calls if tc.name != "ask_user"]
        for tc in other_calls:
            _handle_tool_call(tc)
        if ask_calls:
            _handle_tool_call(ask_calls[0])
            # Satisfy any extra ask_user calls in the same turn
            for extra in ask_calls[1:]:
                _state.messages.append(
                    Message(
                        role="tool",
                        name=extra.name,
                        tool_call_id=extra.id,
                        content=format_tool_result(
                            {
                                "deferred": True,
                                "message": "Another question is already pending; answer that first.",
                            }
                        ),
                    )
                )
            return  # waiting for llm_answer

    _print(f"Stopped after {max_steps} tool steps. Continue with another llm prompt if needed.")
    _state.turn_active = False


def _handle_tool_call(tc: ToolCall) -> bool:
    """Dispatch one tool call. Returns True if agent paused for ask_user."""
    _print(f"→ {tc.name}({_brief_args(tc.arguments)})")
    status, payload = dispatch(tc.name, tc.arguments)

    if status == ASK_USER:
        _state.pending_ask = PendingAsk(
            question=payload["question"],
            choices=list(payload.get("choices") or []),
            tool_call_id=tc.id,
            tool_name=tc.name,
        )
        _print_pending()
        _state.turn_active = False
        return True

    result_text = format_tool_result(payload)
    if status == "error" or (isinstance(payload, dict) and payload.get("ok") is False):
        _state.last_error = result_text
        _print(f"tool issue: {_truncate(result_text, 300)}")
    else:
        # Compact success hint for typed tools
        if isinstance(payload, dict) and payload.get("summary"):
            _print(str(payload["summary"]))
        elif isinstance(payload, dict) and payload.get("note"):
            _print(str(payload["note"]))

    _state.messages.append(
        Message(
            role="tool",
            name=tc.name,
            tool_call_id=tc.id,
            content=result_text,
        )
    )
    return False


def _finish_turn() -> None:
    _state.turn_active = False
    log = export_mod.get_log()
    if log:
        _print("Commands executed:")
        for c in log:
            print(f"  {c}")
        _print("Export with: llm_export [path.pml]")


def _brief_args(args: Dict[str, Any]) -> str:
    try:
        s = json.dumps(args, default=str)
    except Exception:
        s = str(args)
    return _truncate(s, 120)


def _truncate(s: str, n: int) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"

"""Shared types for multi-provider LLM clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema object


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]
    # Gemini thinking models attach this to functionCall parts; must be echoed back.
    thought_signature: str = ""


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""  # tool name when role=tool
    # Opaque provider parts (e.g. Gemini model parts with thoughtSignature).
    # When set, Gemini replays these instead of rebuilding functionCall parts.
    raw_parts: List[Any] = field(default_factory=list)


@dataclass
class AssistantTurn:
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None
    raw_parts: List[Any] = field(default_factory=list)


class LLMClient(Protocol):
    def complete(
        self,
        messages: List[Message],
        tools: List[ToolSpec],
    ) -> AssistantTurn: ...

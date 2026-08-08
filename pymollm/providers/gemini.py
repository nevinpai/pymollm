"""Google Gemini generateContent API via HTTP."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List
from urllib.parse import quote

from pymollm.httputil import request_json
from pymollm.providers.base import AssistantTurn, Message, ToolCall, ToolSpec

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, messages: List[Message], tools: List[ToolSpec]) -> AssistantTurn:
        system = ""
        contents: List[Dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system = (system + "\n\n" + m.content).strip() if system else m.content
                continue
            contents.extend(_to_gemini_contents(m))

        body: Dict[str, Any] = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": _gemini_schema(t.parameters),
                        }
                        for t in tools
                    ]
                }
            ]

        url = (
            f"{API_ROOT}/models/{quote(self.model, safe='')}:generateContent"
            f"?key={quote(self.api_key)}"
        )
        data = request_json(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            json_body=body,
        )

        content_text = ""
        tool_calls: List[ToolCall] = []
        raw_parts: List[Any] = []
        try:
            raw_parts = list(
                (((data.get("candidates") or [{}])[0]).get("content") or {}).get("parts")
                or []
            )
            for part in raw_parts:
                if part.get("text") and not part.get("thought"):
                    content_text += part["text"]
                fc = part.get("functionCall")
                if fc:
                    sig = (
                        part.get("thoughtSignature")
                        or part.get("thought_signature")
                        or ""
                    )
                    tool_calls.append(
                        ToolCall(
                            id=f"gemini_{uuid.uuid4().hex[:12]}",
                            name=str(fc.get("name") or ""),
                            arguments=dict(fc.get("args") or {}),
                            thought_signature=str(sig) if sig else "",
                        )
                    )
        except (AttributeError, IndexError, TypeError, KeyError):
            pass

        return AssistantTurn(
            content=content_text,
            tool_calls=tool_calls,
            raw=data,
            raw_parts=copy.deepcopy(raw_parts),
        )


_GEMINI_SCHEMA_KEYS = {
    "type",
    "description",
    "properties",
    "required",
    "items",
    "enum",
    "nullable",
    "format",
    "minimum",
    "maximum",
    "minItems",
    "maxItems",
}


def _gemini_schema(schema: Any) -> Any:
    """Normalize a JSON Schema object for Gemini function declarations."""
    if isinstance(schema, list):
        return [_gemini_schema(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out: Dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _GEMINI_SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {k: _gemini_schema(v) for k, v in value.items()}
        elif key == "items":
            out[key] = _gemini_schema(value)
        else:
            out[key] = value
    if "properties" in out and "type" not in out:
        out["type"] = "OBJECT"
    type_map = {
        "object": "OBJECT",
        "array": "ARRAY",
        "string": "STRING",
        "integer": "INTEGER",
        "number": "NUMBER",
        "boolean": "BOOLEAN",
    }
    t = out.get("type")
    if isinstance(t, str) and t in type_map:
        out["type"] = type_map[t]
    return out


def _to_gemini_contents(m: Message) -> List[Dict[str, Any]]:
    if m.role == "tool":
        return [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": m.name or "tool",
                            "response": {"result": m.content},
                        }
                    }
                ],
            }
        ]
    if m.role == "assistant":
        if m.raw_parts:
            return [{"role": "model", "parts": copy.deepcopy(m.raw_parts)}]
        parts: List[Dict[str, Any]] = []
        if m.content:
            parts.append({"text": m.content})
        for tc in m.tool_calls:
            part: Dict[str, Any] = {
                "functionCall": {"name": tc.name, "args": tc.arguments}
            }
            if tc.thought_signature:
                part["thoughtSignature"] = tc.thought_signature
            parts.append(part)
        if not parts:
            parts.append({"text": ""})
        return [{"role": "model", "parts": parts}]
    return [{"role": "user", "parts": [{"text": m.content}]}]

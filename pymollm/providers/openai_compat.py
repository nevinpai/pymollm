"""OpenAI (and OpenAI-compatible) chat completions via HTTP."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from pymollm.httputil import request_json
from pymollm.providers.base import AssistantTurn, Message, ToolCall, ToolSpec

DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAICompatClient:
    def __init__(self, api_key: str, model: str, base_url: str = "") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or DEFAULT_BASE).rstrip("/")

    def complete(self, messages: List[Message], tools: List[ToolSpec]) -> AssistantTurn:
        oai_messages = [_to_openai_message(m) for m in messages]
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": oai_messages,
        }
        if oai_tools:
            body["tools"] = oai_tools
            body["tool_choice"] = "auto"

        data = request_json(
            "POST",
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json_body=body,
        )

        choice = (data.get("choices") or [{}])[0].get("message") or {}
        tool_calls: List[ToolCall] = []
        for tc in choice.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {"_raw": raw_args}
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or ""),
                    name=str(fn.get("name") or ""),
                    arguments=args,
                )
            )
        return AssistantTurn(
            content=choice.get("content") or "",
            tool_calls=tool_calls,
            raw=data,
        )


def _to_openai_message(m: Message) -> Dict[str, Any]:
    if m.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": m.tool_call_id,
            "content": m.content,
        }
    if m.role == "assistant" and m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ],
        }
    return {"role": m.role, "content": m.content}

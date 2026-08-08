"""Anthropic Claude messages API via HTTP."""

from __future__ import annotations

from typing import Any, Dict, List

from pymollm.httputil import request_json
from pymollm.providers.base import AssistantTurn, Message, ToolCall, ToolSpec

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, messages: List[Message], tools: List[ToolSpec]) -> AssistantTurn:
        system = ""
        anth_messages: List[Dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system = (system + "\n\n" + m.content).strip() if system else m.content
                continue
            anth_messages.append(_to_anthropic_message(m))

        anth_messages = _merge_messages(anth_messages)

        body: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": anth_messages,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]

        data = request_json(
            "POST",
            API_URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            json_body=body,
        )

        content_text = ""
        tool_calls: List[ToolCall] = []
        for block in data.get("content") or []:
            btype = block.get("type")
            if btype == "text":
                content_text += block.get("text") or ""
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=str(block.get("id") or ""),
                        name=str(block.get("name") or ""),
                        arguments=dict(block.get("input") or {}),
                    )
                )
        return AssistantTurn(content=content_text, tool_calls=tool_calls, raw=data)


def _to_anthropic_message(m: Message) -> Dict[str, Any]:
    if m.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content,
                }
            ],
        }
    if m.role == "assistant":
        content: List[Dict[str, Any]] = []
        if m.content:
            content.append({"type": "text", "text": m.content})
        for tc in m.tool_calls:
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
            )
        if not content:
            content.append({"type": "text", "text": ""})
        return {"role": "assistant", "content": content}
    return {"role": "user", "content": m.content}


def _merge_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not messages:
        return messages
    merged: List[Dict[str, Any]] = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"]:
            prev = merged[-1]["content"]
            cur = msg["content"]
            if isinstance(prev, str) and isinstance(cur, str):
                merged[-1]["content"] = prev + "\n" + cur
            else:
                prev_list = (
                    [{"type": "text", "text": prev}] if isinstance(prev, str) else list(prev)
                )
                cur_list = (
                    [{"type": "text", "text": cur}] if isinstance(cur, str) else list(cur)
                )
                merged[-1]["content"] = prev_list + cur_list
        else:
            merged.append(msg)
    return merged

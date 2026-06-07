"""MiniMax-compatible LLM wrapper for LiveKit Agents voice sessions.

MiniMax's OpenAI-compatible API rejects some message shapes LiveKit generates
(multiple system messages, extra_content on tool calls, unsupported extra params).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from livekit.agents.llm import _provider_format
from livekit.plugins.openai.llm import LLM as OpenAILLM
from livekit.plugins.openai.llm import LLMStream as OpenAILLMStream

_MINIMAX_STRIP_EXTRA = (
    "reasoning_effort",
    "verbosity",
    "prompt_cache_retention",
    "service_tier",
    "parallel_tool_calls",
    "response_format",
    "metadata",
    "store",
    "safety_identifier",
    "prompt_cache_key",
)
_MINIMAX_THINKING_DISABLED = {"type": "disabled"}

_USER_FALLBACK = "Hello."
_ASSISTANT_FALLBACK = "Okay."
_TOOL_FALLBACK = "{}"


def _non_empty(text: str, fallback: str) -> str:
    value = text.strip()
    return value if value else fallback


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("input_text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def sanitize_messages_for_minimax(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge system prompts and strip fields MiniMax rejects (error 2013)."""
    system_parts: list[str] = []
    sanitized: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")
        if role == "system":
            text = _message_text(message.get("content"))
            if text:
                system_parts.append(text)
            continue

        clean: dict[str, Any]
        if role == "assistant":
            content = _message_text(message.get("content"))
            tool_calls = message.get("tool_calls") or []
            clean = {"role": "assistant"}
            if tool_calls:
                clean["tool_calls"] = [
                    {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": (tc.get("function") or {}).get("name"),
                            "arguments": (tc.get("function") or {}).get("arguments") or "{}",
                        },
                    }
                    for tc in tool_calls
                ]
                if content.strip():
                    clean["content"] = content
            else:
                clean["content"] = _non_empty(content, _ASSISTANT_FALLBACK)
        elif role == "tool":
            clean = {
                "role": "tool",
                "tool_call_id": message.get("tool_call_id"),
                "content": _non_empty(_message_text(message.get("content")), _TOOL_FALLBACK),
            }
        elif role == "user":
            clean = {"role": "user", "content": _non_empty(_message_text(message.get("content")), _USER_FALLBACK)}
        else:
            clean = {"role": role, "content": _non_empty(_message_text(message.get("content")), _USER_FALLBACK)}

        sanitized.append(clean)

    if system_parts:
        sanitized = [{"role": "system", "content": "\n\n".join(system_parts)}, *sanitized]

    if not any(msg.get("role") == "user" for msg in sanitized):
        sanitized.append({"role": "user", "content": _USER_FALLBACK})

    return sanitized


@contextmanager
def _minimax_provider_format():
    openai_mod = _provider_format.openai
    original = openai_mod.to_chat_ctx

    def patched(chat_ctx, *, inject_dummy_user_message=True):
        messages, meta = original(chat_ctx, inject_dummy_user_message=inject_dummy_user_message)
        return sanitize_messages_for_minimax(messages), meta

    openai_mod.to_chat_ctx = patched
    try:
        yield
    finally:
        openai_mod.to_chat_ctx = original


class MiniMaxLLMStream(OpenAILLMStream):
    async def _run(self) -> None:
        for key in _MINIMAX_STRIP_EXTRA:
            self._extra_kwargs.pop(key, None)
        with _minimax_provider_format():
            await super()._run()


class MiniMaxLLM(OpenAILLM):
    def chat(self, *args, **kwargs):  # noqa: ANN002, ANN003
        stream = super().chat(*args, **kwargs)
        stream.__class__ = MiniMaxLLMStream
        return stream


def get_minimax_thinking_param(disable: bool) -> dict[str, dict[str, str]] | None:
    """Return MiniMax thinking control payload.

    `reasoning` can be disabled only for M3-class models; for M2.x and older models
    the provider may ignore this and still include thinking output.
    """
    if not disable:
        return None
    return {"thinking": _MINIMAX_THINKING_DISABLED}

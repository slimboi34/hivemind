"""
OpenAI Chat Completions compatibility helpers.

This module keeps existing behavior for legacy models/providers while
gracefully adapting request parameters for GPT-5 family models.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Claude model ids, optionally with a provider prefix (e.g. "us.anthropic.claude-sonnet-5-5").
_CLAUDE_ID = re.compile(r"(?:^|[./:])claude-(?:opus|sonnet|haiku|fable)-(\d+)")


def is_gpt5_family(model: Optional[str]) -> bool:
    """Return True when model belongs to GPT-5 family aliases/snapshots."""
    if not model:
        return False
    return model.strip().lower().startswith("gpt-5")


def is_claude5_family(model: Optional[str]) -> bool:
    """
    Return True for Claude 5 and later on Anthropic's OpenAI-compatible endpoint.

    These models reject `temperature` ("deprecated for this model") and accept
    only `json_schema` response formats, not `json_object`. Earlier Claude
    models (e.g. claude-haiku-4-5) accept both and keep the legacy request shape.
    """
    match = _CLAUDE_ID.search((model or "").strip().lower())
    return bool(match) and int(match.group(1)) >= 5


def create_chat_completion(
    client: Any,
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Create a chat completion with model-specific request parameters.

    Compatibility strategy:
    - For GPT-5 family, avoid sending temperature by default.
    - For token limit, use `max_completion_tokens` on GPT-5, `max_tokens` otherwise.
    - For Claude 5 family, avoid sending temperature, and omit `json_object`
      response_format (the prompts already require JSON; this is the same request
      the JSON-mode fallback sends to providers without JSON mode).
    - Preserve the legacy request shape for every other model/provider.
    - Propagate provider errors unchanged instead of guessing from message text.
    """
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    gpt5_family = is_gpt5_family(model)
    claude5_family = is_claude5_family(model)

    if response_format is not None and not (
        claude5_family and response_format.get("type") == "json_object"
    ):
        kwargs["response_format"] = response_format

    if temperature is not None and not gpt5_family and not claude5_family:
        kwargs["temperature"] = temperature

    if max_tokens is not None:
        if gpt5_family:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

    return client.chat.completions.create(**kwargs)


def extract_chat_completion_text(response: Any) -> str:
    """Extract plain text from chat completion response across SDK content shapes."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return ""

    content = getattr(message, "content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text_obj = item.get("text")
                if isinstance(text_obj, dict):
                    text_obj = text_obj.get("value")
                if isinstance(text_obj, str):
                    chunks.append(text_obj)
                elif isinstance(item.get("content"), str):
                    chunks.append(item["content"])
                continue

            text_obj = getattr(item, "text", None)
            if isinstance(text_obj, dict):
                text_obj = text_obj.get("value")
            if isinstance(text_obj, str):
                chunks.append(text_obj)
                continue

            content_obj = getattr(item, "content", None)
            if isinstance(content_obj, str):
                chunks.append(content_obj)

        return "".join(chunks).strip()

    return str(content or "")

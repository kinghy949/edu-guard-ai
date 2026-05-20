"""OpenAI 兼容 chat completions 客户端。

接入方传入 ``base_url`` / ``api_key`` / ``model``；未传则回退读取 settings。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


class LLMError(RuntimeError):
    pass


@dataclass
class LLMRuntime:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.3


def resolve_runtime(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> LLMRuntime:
    rt = LLMRuntime(
        base_url=(base_url or settings.LLM_BASE_URL).rstrip("/"),
        api_key=api_key or settings.LLM_API_KEY,
        model=model or settings.LLM_MODEL,
        temperature=temperature if temperature is not None else 0.3,
    )
    if not rt.api_key:
        raise LLMError("未配置 LLM API Key")
    return rt


def _headers(rt: LLMRuntime) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {rt.api_key}",
        "Content-Type": "application/json",
    }


def chat(
    messages: list[dict[str, str]],
    *,
    runtime: LLMRuntime | None = None,
    **overrides: Any,
) -> str:
    rt = runtime or resolve_runtime(**overrides)
    body = {
        "model": rt.model,
        "messages": messages,
        "temperature": rt.temperature,
        "stream": False,
    }
    try:
        r = httpx.post(f"{rt.base_url}/chat/completions", json=body, headers=_headers(rt), timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        raise LLMError(f"LLM 调用失败: {e}") from e
    except (KeyError, IndexError) as e:
        raise LLMError(f"LLM 响应解析失败: {e}") from e


async def chat_stream(
    messages: list[dict[str, str]],
    *,
    runtime: LLMRuntime | None = None,
    **overrides: Any,
) -> AsyncIterator[str]:
    rt = runtime or resolve_runtime(**overrides)
    body = {
        "model": rt.model,
        "messages": messages,
        "temperature": rt.temperature,
        "stream": True,
    }
    url = f"{rt.base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=120)) as client:
        try:
            async with client.stream("POST", url, json=body, headers=_headers(rt)) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        return
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {}).get("content")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except httpx.HTTPError as e:
            raise LLMError(f"LLM 流式调用失败: {e}") from e

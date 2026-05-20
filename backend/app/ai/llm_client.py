"""OpenAI 兼容 chat completions 客户端。

仅依赖 httpx，避免锁定特定 SDK。可切换 DeepSeek / 通义 / Claude（OpenAI 兼容路由）。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings


class LLMError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.LLM_API_KEY:
        raise LLMError("未配置 LLM_API_KEY")
    return {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }


def chat(messages: list[dict[str, str]], *, model: str | None = None, temperature: float = 0.3) -> str:
    """同步获取一次完整回复。"""
    body: dict[str, Any] = {
        "model": model or settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    try:
        r = httpx.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            json=body, headers=_headers(), timeout=60,
        )
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
    model: str | None = None,
    temperature: float = 0.3,
) -> AsyncIterator[str]:
    """异步流式生成回复（OpenAI SSE 协议），逐 token 产出文本增量。"""
    body: dict[str, Any] = {
        "model": model or settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=120)) as client:
        try:
            async with client.stream("POST", url, json=body, headers=_headers()) as r:
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

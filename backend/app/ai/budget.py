from __future__ import annotations

TRUNCATED_SUFFIX = "…(已截断)"


def estimate_tokens(text: str) -> int:
    """轻量 token 估算：中文约 1 token/2 chars，留 1 个余量。"""
    if not text:
        return 1
    return len(text) // 2 + 1


def _message_tokens(message: dict[str, str]) -> int:
    # role、JSON 包装等有额外开销，粗略加 4。
    return estimate_tokens(message.get("content", "")) + 4


def total_tokens(messages: list[dict[str, str]]) -> int:
    return sum(_message_tokens(m) for m in messages)


def _truncate_content(content: str, max_tokens: int) -> str:
    if estimate_tokens(content) <= max_tokens:
        return content
    # 估算函数约等于 len//2，因此 chars 取 token*2 再给后缀留空间。
    keep_chars = max((max_tokens - estimate_tokens(TRUNCATED_SUFFIX)) * 2, 0)
    return content[:keep_chars].rstrip() + TRUNCATED_SUFFIX


def fit_messages(messages: list[dict[str, str]], max_tokens: int) -> list[dict[str, str]]:
    """裁剪 Chat Completions messages，使估算 token 不超过上限。

    规则：
    - 永远保留第一条 system 与最后一条 user。
    - 中间历史从旧到新丢弃，优先保留越新的历史。
    - 如果 system 或最后一条 user 自身过长，则截尾并标注。
    """
    if max_tokens <= 0 or len(messages) <= 2:
        return messages

    system = dict(messages[0])
    latest = dict(messages[-1])
    history = [dict(m) for m in messages[1:-1]]

    # 先给 system 和最新用户输入各自截到不超过总预算的 45%，避免一条消息吃满。
    per_critical = max(max_tokens // 2 - 8, 1)
    system["content"] = _truncate_content(system.get("content", ""), per_critical)
    latest["content"] = _truncate_content(latest.get("content", ""), per_critical)

    kept = [system, latest]
    remaining = max_tokens - total_tokens(kept)
    if remaining <= 0:
        # 两条关键消息仍然过长时，继续等比例收缩最后用户输入。
        latest_budget = max(max_tokens - _message_tokens(system), 1)
        latest["content"] = _truncate_content(latest.get("content", ""), latest_budget)
        return [system, latest]

    selected: list[dict[str, str]] = []
    for item in reversed(history):
        cost = _message_tokens(item)
        if cost > remaining:
            continue
        selected.append(item)
        remaining -= cost

    return [system, *reversed(selected), latest]

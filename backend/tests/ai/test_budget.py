from __future__ import annotations

from app.ai.budget import TRUNCATED_SUFFIX, estimate_tokens, fit_messages, total_tokens


def test_estimate_tokens_is_lightweight_chinese_friendly():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcdef") == 4
    assert estimate_tokens("中文测试") == 3


def test_short_messages_are_unchanged():
    messages = [
        {"role": "system", "content": "系统"},
        {"role": "user", "content": "你好"},
    ]

    assert fit_messages(messages, 100) == messages


def test_fit_messages_drops_old_history_but_keeps_latest_user_and_system():
    messages = [{"role": "system", "content": "系统提示"}]
    for i in range(40):
        messages.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"历史 {i} " + "x" * 80})
    messages.append({"role": "user", "content": "最新问题必须保留"})

    fitted = fit_messages(messages, 120)

    assert fitted[0]["role"] == "system"
    assert fitted[0]["content"] == "系统提示"
    assert fitted[-1] == {"role": "user", "content": "最新问题必须保留"}
    assert total_tokens(fitted) <= 120
    assert len(fitted) < len(messages)


def test_fit_messages_truncates_overlong_system_and_latest_user():
    messages = [
        {"role": "system", "content": "S" * 1000},
        {"role": "assistant", "content": "旧历史"},
        {"role": "user", "content": "U" * 1000},
    ]

    fitted = fit_messages(messages, 100)

    assert fitted[0]["role"] == "system"
    assert fitted[-1]["role"] == "user"
    assert fitted[0]["content"].endswith(TRUNCATED_SUFFIX)
    assert fitted[-1]["content"].endswith(TRUNCATED_SUFFIX)
    assert total_tokens(fitted) <= 100

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class SendOutcome:
    ok: bool
    detail: str = ""
    payload: dict[str, Any] | None = None


class Notifier(Protocol):
    channel: str

    def send(self, target: str, subject: str, content: str, config: dict[str, Any]) -> SendOutcome:
        ...

    # 可选：返回配置错误清单（为空视为合规）。实现者可不提供。
    def validate_config(self, config: dict[str, Any]) -> list[str]:  # pragma: no cover - 协议默认
        return []

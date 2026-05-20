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

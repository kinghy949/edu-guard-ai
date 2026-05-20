"""站内消息渠道：不需要外部传输，直接落库即视为送达。"""
from typing import Any

from app.notifiers.base import SendOutcome


class InboxNotifier:
    channel = "inbox"

    def send(self, target: str, subject: str, content: str, config: dict[str, Any]) -> SendOutcome:
        # 站内消息的落库由 dispatcher 统一写入 Notification 表，这里只表示"已投递"。
        return SendOutcome(ok=True, detail="inbox delivered")

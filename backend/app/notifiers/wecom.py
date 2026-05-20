"""企业微信群机器人。

config:
  webhook: 完整 webhook URL
"""
from typing import Any

import httpx

from app.notifiers.base import SendOutcome


class WecomNotifier:
    channel = "wecom"

    def send(self, target: str, subject: str, content: str, config: dict[str, Any]) -> SendOutcome:
        webhook = config.get("webhook")
        if not webhook:
            return SendOutcome(ok=False, detail="缺少 webhook")
        body = {
            "msgtype": "markdown",
            "markdown": {"content": f"**{subject}**\n\n{content}\n\n> 接收人: {target}"},
        }
        try:
            r = httpx.post(webhook, json=body, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("errcode", 0) != 0:
                return SendOutcome(ok=False, detail=f"wecom errcode={data.get('errcode')} {data.get('errmsg')}", payload=data)
        except Exception as e:
            return SendOutcome(ok=False, detail=f"wecom 请求失败: {e}")
        return SendOutcome(ok=True, detail="sent")

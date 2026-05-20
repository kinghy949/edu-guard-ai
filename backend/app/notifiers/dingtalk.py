"""钉钉群机器人。

config:
  webhook: 完整 webhook URL（含 access_token）
  secret:  可选签名密钥（若开启加签）
"""
import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any

import httpx

from app.notifiers.base import SendOutcome


def _sign(secret: str) -> tuple[int, str]:
    ts = round(time.time() * 1000)
    raw = f"{ts}\n{secret}".encode("utf-8")
    sign = base64.b64encode(hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest())
    return ts, urllib.parse.quote_plus(sign)


class DingTalkNotifier:
    channel = "dingtalk"

    def send(self, target: str, subject: str, content: str, config: dict[str, Any]) -> SendOutcome:
        webhook = config.get("webhook")
        if not webhook:
            return SendOutcome(ok=False, detail="缺少 webhook")
        secret = config.get("secret")
        url = webhook
        if secret:
            ts, sign = _sign(secret)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}timestamp={ts}&sign={sign}"

        body = {
            "msgtype": "markdown",
            "markdown": {"title": subject, "text": f"### {subject}\n\n{content}\n\n> 接收人: {target}"},
        }
        try:
            r = httpx.post(url, json=body, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("errcode", 0) != 0:
                return SendOutcome(ok=False, detail=f"dingtalk errcode={data.get('errcode')} {data.get('errmsg')}", payload=data)
        except Exception as e:
            return SendOutcome(ok=False, detail=f"dingtalk 请求失败: {e}")
        return SendOutcome(ok=True, detail="sent")

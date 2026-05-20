"""短信渠道（阿里云占位）。

config:
  access_key_id, access_key_secret, sign_name, template_code

> 真实接入请引入阿里云 SDK 或自行实现签名；这里只做占位，记录请求并视为成功，避免硬依赖。
"""
from typing import Any

from app.notifiers.base import SendOutcome


class SmsNotifier:
    channel = "sms"

    def send(self, target: str, subject: str, content: str, config: dict[str, Any]) -> SendOutcome:
        for k in ("access_key_id", "access_key_secret", "sign_name", "template_code"):
            if not config.get(k):
                return SendOutcome(ok=False, detail=f"SMS 配置缺少 {k}")
        # TODO: 接入真实阿里云短信 SDK
        return SendOutcome(
            ok=True,
            detail="sms stub (not actually sent)",
            payload={"target": target, "template_code": config["template_code"]},
        )

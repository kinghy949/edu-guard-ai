"""SMTP 邮件渠道。

config:
  host, port, user, password, from, use_ssl(bool, default true)
"""
import smtplib
from email.message import EmailMessage
from typing import Any

from app.notifiers.base import SendOutcome


class EmailNotifier:
    channel = "email"

    def send(self, target: str, subject: str, content: str, config: dict[str, Any]) -> SendOutcome:
        host = config.get("host")
        port = int(config.get("port", 465))
        user = config.get("user")
        password = config.get("password")
        sender = config.get("from") or user
        use_ssl = bool(config.get("use_ssl", True))

        if not all([host, user, password, sender]):
            return SendOutcome(ok=False, detail="SMTP 配置不完整")

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = target
        msg["Subject"] = subject
        msg.set_content(content)

        try:
            client_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
            with client_cls(host, port, timeout=15) as s:
                if not use_ssl:
                    s.starttls()
                s.login(user, password)
                s.send_message(msg)
        except Exception as e:
            return SendOutcome(ok=False, detail=f"SMTP 失败: {e}")
        return SendOutcome(ok=True, detail="sent")

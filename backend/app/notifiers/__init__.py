"""通知渠道适配器。

每个 notifier 实现统一接口 ``send(target, subject, content, config) -> SendOutcome``。
"""
from app.notifiers.base import Notifier, SendOutcome
from app.notifiers.dingtalk import DingTalkNotifier
from app.notifiers.email import EmailNotifier
from app.notifiers.inbox import InboxNotifier
from app.notifiers.sms import SmsNotifier
from app.notifiers.wecom import WecomNotifier

REGISTRY: dict[str, Notifier] = {
    InboxNotifier.channel: InboxNotifier(),
    EmailNotifier.channel: EmailNotifier(),
    WecomNotifier.channel: WecomNotifier(),
    DingTalkNotifier.channel: DingTalkNotifier(),
    SmsNotifier.channel: SmsNotifier(),
}

__all__ = ["REGISTRY", "Notifier", "SendOutcome"]

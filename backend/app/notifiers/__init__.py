"""通知渠道适配器。

每个 notifier 实现统一接口 ``send(target, subject, content, **kwargs)``，
通过 ``NotificationConfig`` 启停。
"""

# TODO(M3):
# - email.py      SMTP
# - wecom.py      企业微信群机器人 Webhook
# - dingtalk.py   钉钉群机器人 Webhook
# - sms.py        阿里云短信
# - inbox.py      站内消息

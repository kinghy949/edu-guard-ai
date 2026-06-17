# 通知中心

支持渠道：站内 / 邮件 / 企业微信群机器人 / 钉钉群机器人 / 短信（阿里云占位）。

## 渠道配置

每个渠道一条记录，存在 `notification_configs` 表，由管理员通过接口维护：

```
PUT /api/v1/notifications/configs/{channel}
{
  "enabled": true,
  "config": { ... }
}
```

各 `config` 字段：

| channel | 字段 |
| --- | --- |
| `inbox` | 无需配置 |
| `email` | `host`, `port`, `user`, `password`, `from`, `use_ssl`(默认 true) |
| `wecom` | `webhook` |
| `dingtalk` | `webhook`, `secret`(可选加签) |
| `sms` | `provider`(mock\|aliyun，默认 mock)；aliyun 时还需 `access_key_id`/`access_key_secret`/`sign_name`/`template_code`；可选 `template_param`(dict)、`endpoint` |

### 配置校验

`PUT /api/v1/notifications/configs/{channel}` 启用渠道时会调用对应
notifier 的 `validate_config`，缺字段直接返回 400 并指明缺项；SMS
provider=mock 时无需任何 access key。

## 触发方式

- **批量预警生成时自动派发**：`POST /api/v1/warnings/generate`，传 `auto_dispatch: true` 与可选 `channels: ["email","wecom"]`
- **对单条预警派发**：`POST /api/v1/notifications/warnings/{warning_id}/dispatch`
- **测试一条通知**：`POST /api/v1/notifications/test`，指定 channel + target + 文案

## 投递记录

每次发送都会写入 `notifications` 表：
- `status`：`pending / sent / failed`
- `error`：失败原因
- `payload`：渠道返回原文（便于排查）

学生只能查看 `user_id = self` 的通知。

## 模板

预警通知模板内置 Jinja2，渲染上下文取自 `Warning.detail`：

- subject：`【学业预警-{级别}】{姓名}（{学号}）`
- body：摘要 + 总学分要求/已修/在修/缺口 + 各分类明细 + 挂科提醒

如需自定义，编辑 `app/services/notify_dispatcher.py` 的 `WARNING_SUBJECT_TPL` / `WARNING_BODY_TPL`，或后续抽到模板文件。

# 操作手册

面向系统部署、日常运维与教务管理员。涵盖：默认账号、通知渠道配置、AI 模型切换、常用运维命令。

---

## 一、默认账号

### 1.1 系统账号（由 `scripts/bootstrap.py` 自动创建）

部署完成后开箱即用：

| 角色 | 用户名 | 密码 | 来源 |
| --- | --- | --- | --- |
| 管理员 | `admin` | `admin123` | `backend/.env` 中的 `BOOTSTRAP_ADMIN_*` |

> ⚠️ **生产部署前** 必须先改 `backend/.env`：
> ```
> BOOTSTRAP_ADMIN_USERNAME=admin
> BOOTSTRAP_ADMIN_PASSWORD=<强随机串>
> BOOTSTRAP_ADMIN_EMAIL=admin@your-school.edu.cn
> SEED_DEMO=false
> ```
> 该脚本仅在「数据库无任何用户」时创建管理员；后续启动幂等。

登录后立刻：
1. **管理后台 → 用户管理 → 修改密码**
2. **管理后台 → AI 模型**填入 LLM 凭据
3. **管理后台 → 通知渠道**配置邮件/企微/钉钉

---

### 1.2 演示账号（仅当 `SEED_DEMO=true`）

适用于教学演示、UAT 验证。全部学生密码 = 学号。

#### 系统角色

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `admin123` |
| 辅导员 | `counselor` | `counselor123` |

#### 学生（25 名 / 3 个专业）

按典型场景挑选了典型样本：

| 学号 | 姓名 | 入学年 | 班级 | 场景 | 触发预警 |
| --- | --- | --- | --- | --- | --- |
| 20210101 | 刘洋 | 2021 | 计科 2101 | 大四，操作系统/编译原理挂科 | 🔴 severe |
| 20210103 | 周静怡 | 2021 | 计科 2102 | 大四，临近毕业接近达标 | 🟡 warn |
| 20220201 | 张伟 | 2022 | 计科 2201 | 大三末，整体落后 | 🔴 severe |
| 20220202 | 李娜 | 2022 | 计科 2201 | 大三末，按部就班 | ℹ️ info |
| 20220501 | 韩立诚 | 2022 | 软工 2201 | 大三末，按部就班 | ℹ️ info |
| 20220701 | 顾明轩 | 2022 | 网工 2201 | 大三末，专业必修不足 | 🔴 severe |
| 20230301 | 黄思远 | 2023 | 计科 2301 | 大二下，进度正常 | 🟡 warn |
| 20240401 | 马一鸣 | 2024 | 计科 2401 | 大一下，正常 | — |

> 全部 25 名学生覆盖 4 个年级、3 个专业、10 个班级，密码均为学号。

#### 重置演示数据

```bash
docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_demo
```

幂等：已存在的学生/方案/预警不会重复创建；想完全重置请先 `docker compose down -v` 清空数据卷再 `up -d`。

---

## 二、AI 模型配置

支持 OpenAI 兼容协议的任意厂商，DB 配置优先于 `.env`。

**管理后台 → AI 模型**：

| 字段 | 说明 |
| --- | --- |
| Base URL | 厂商提供的兼容端点根路径 |
| API Key | 凭据；保存后再次查看会脱敏显示 `sk-x…xxxx` |
| Model | 模型 id 或部署接入点 |
| Temperature | 0–2，问答场景建议 0.2–0.4 |
| 启用 | 关闭后 chat 调用会失败 |

**国内零成本接入示例**（持续变化，以厂商官网为准）：

| 厂商 | Base URL | Model |
| --- | --- | --- |
| 阿里 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` / `qwen-plus` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash`（免费） |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 火山豆包 | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-1-5-lite-32k`（model 填接入点 ID） |
| Moonshot Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |

修改后立即生效，无需重启容器。点"测试连通"会让当前配置发送一句 `你好` 验证。

---

## 三、通知渠道配置

支持 5 个渠道：站内 / 邮件 / 企业微信群机器人 / 钉钉群机器人 / 短信。
入口：**管理后台 → 通知渠道**。

### 3.1 站内消息（inbox）

无需任何配置，启用即可。学生登录后在 `GET /api/v1/notifications` 看到本人记录。

### 3.2 邮件（email · SMTP）

**第一步：申请 SMTP 授权码**

主流邮箱不允许使用登录密码作为 SMTP 凭据，需在邮箱后台开启 SMTP 服务并生成专用授权码：

| 邮箱 | 后台入口 | host | port | use_ssl |
| --- | --- | --- | --- | --- |
| QQ 邮箱 | 设置 → 账户 → POP3/SMTP → 生成授权码 | `smtp.qq.com` | 465 | true |
| 163 邮箱 | 设置 → POP3/SMTP/IMAP → 客户端授权密码 | `smtp.163.com` | 465 | true |
| 阿里云邮 | 设置 → 客户端授权密码 | `smtp.qiye.aliyun.com` | 465 | true |
| Outlook / 365 | 账户安全 → 应用密码 | `smtp.office365.com` | 587 | false |
| Gmail | Google 账户 → 两步验证 → 应用专用密码 | `smtp.gmail.com` | 587 | false |
| 自建 | 询问运维 | — | — | — |

**第二步：填入 config JSON**

```json
{
  "host": "smtp.qq.com",
  "port": 465,
  "user": "your-mailbox@qq.com",
  "password": "<刚刚生成的授权码，非登录密码>",
  "from": "your-mailbox@qq.com",
  "use_ssl": true
}
```

`use_ssl=false` 时走 STARTTLS（典型 587 端口）。

**第三步：测试**

页面底部「测试发送」：渠道选 `email`，目标填你自己的邮箱，点测试。成功会看到 `succeeded: 1`，失败则在 `notifications` 表 `error` 字段查看原因。

**常见报错**：

| 报错 | 原因 |
| --- | --- |
| `SMTP 配置不完整` | JSON 字段拼写错误（如 `from` 漏掉） |
| `Username and Password not accepted` | 用了邮箱登录密码而非授权码 |
| `SMTP AUTH extension not supported` | SSL/STARTTLS 端口不匹配，QQ/163 改回 465+`use_ssl: true` |
| `Connection timed out` | 云服务器（阿里云/腾讯云）默认封禁 25/465 出站，需提工单解封或改用 587/STARTTLS |
| `BadCredentials` | 授权码过期或被收回，重新生成 |

### 3.3 企业微信群机器人（wecom）

```json
{
  "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx"
}
```

获取方式：企业微信群 → 右上角 ⋯ → 添加群机器人 → 复制 Webhook 地址。
消息以 markdown 发送，群机器人**对所有群成员可见**，不区分收件人。

### 3.4 钉钉群机器人（dingtalk）

```json
{
  "webhook": "https://oapi.dingtalk.com/robot/send?access_token=xxxx",
  "secret": "SECxxxxxxxxxxxxxxxx"
}
```

钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义 → 安全设置勾选「加签」，把 secret 一并填入。
未启用加签时省略 `secret` 字段。

### 3.5 短信（sms · 阿里云占位）

```json
{
  "access_key_id": "...",
  "access_key_secret": "...",
  "sign_name": "学业预警",
  "template_code": "SMS_xxxxxxxx"
}
```

目前只有占位实现（标记成功但不实际发送），生产接入需在 `backend/app/notifiers/sms.py` 引入阿里云短信 SDK 完成签名与调用，模板需先在控制台审核通过。

### 3.6 触发派发

**单条预警**：列表页 → 「详情」→ 调用 `POST /api/v1/notifications/warnings/{id}/dispatch`，传 `channels` 数组。
**批量**：管理后台 → 批量预警 → 勾「自动派发」+ 选渠道 → 生成。

收件路由（除站内/群机器人）：
- email → `users.email`
- sms → `users.phone`
未填写则该渠道记录 `failed: 缺少收件人`，不影响其他渠道。

### 3.7 模板自定义

预警邮件 subject / body 是 Jinja2 模板，集中在 `backend/app/services/notify_dispatcher.py` 顶部的 `WARNING_SUBJECT_TPL` 与 `WARNING_BODY_TPL`，可直接编辑后重启 backend：

```bash
docker compose -f docker-compose.prod.yml restart backend
```

---

## 四、日常运维命令

```bash
# 查看容器状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f backend

# 进入后端容器排查
docker compose -f docker-compose.prod.yml exec backend bash

# 备份数据库
docker compose -f docker-compose.prod.yml exec db pg_dump -U eduguard eduguard > backup-$(date +%F).sql

# 恢复
cat backup-2026-05-21.sql | docker compose -f docker-compose.prod.yml exec -T db psql -U eduguard eduguard

# 手动触发预警生成（按学院过滤）
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login -d "username=admin&password=<密码>" | jq -r .access_token)
curl -X POST http://localhost/api/v1/warnings/generate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"college":"信息与计算机科学学院","auto_dispatch":true,"channels":["inbox","email"]}'

# 创建追加管理员（不依赖 bootstrap）
docker compose -f docker-compose.prod.yml exec backend python -m scripts.create_admin <user> <password>

# 重置演示数据（先清库再起）
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d
```

---

## 五、批量导入说明

详见 [`import-templates.md`](import-templates.md)。
四类入口都在 **管理后台 → 批量导入**：

- 学生名册：学号即用户名 + 初始密码
- 课程主数据：课程库 upsert
- 培养方案：每行一门课在方案中的归属（含学分桶要求）
- 成绩：按 `学生 × 课程 × 学期` upsert

模板列名可调 `GET /api/v1/imports/templates` 查看。

---

## 六、数据合规清单

试点期间按最小化原则采集和使用学生数据：

- 学生名册仅导入系统必需字段：学号、姓名、学院、专业、班级、入学年、邮箱、手机号；不导入身份证号、家庭住址、家庭成员等非必要敏感信息。
- 学生列表、审计详情等日常页面默认脱敏展示邮箱和手机号；确需核对联系方式时，仅在学生详情页由 staff 点击临时显示完整值。
- 学生账号离校、转专业或试点结束后，应由管理员停用账号，并按学校数据保留制度导出、归档或删除相关数据。
- Excel 导出文件只用于校内学业帮扶工作，不通过个人网盘、微信群、公共邮箱转发；导出后应存放在受控目录，使用完毕及时删除。
- AI 问答仅作辅助解释，页面和系统提示均声明最终以教务处文件、培养方案原文和学校正式通知为准。
- 运维排查优先使用 request_id、job_runs、audit_logs 定位问题，避免直接复制包含学生联系方式和成绩明细的原始数据到外部工具。
- 数据库备份文件包含全量个人信息，必须限制系统用户读写权限，并按 14 份轮转策略清理过期备份。

---

## 七、单 worker 约束（重要）

定时任务使用进程内 APScheduler 调度，登录限流使用进程内计数器。
**生产部署必须保持 uvicorn 单 worker**，否则会出现：

- 同一定时任务被重复触发（advisory lock 是双保险，仍建议遵守）
- IP 登录限流统计偏差

```bash
# Dockerfile / compose 启动命令保持
uvicorn app.main:app --host 0.0.0.0 --port 8000   # 默认单 worker
```

如需水平扩展，请改用外部调度（如 cron + 调 /admin/jobs/.../run-now）。

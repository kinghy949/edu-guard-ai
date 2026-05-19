# EduGuard-AI · 智能学业预警系统

> 面向高校的学生学业完成情况自动预警与智能问答系统。

![status](https://img.shields.io/badge/status-WIP-orange) ![license](https://img.shields.io/badge/license-MIT-blue) ![stack](https://img.shields.io/badge/stack-Vue3%20%2B%20FastAPI%20%2B%20PostgreSQL-green)

## 一、项目背景

大量高校学生在校期间，对自己已修课程、学分构成、毕业要求是否达标缺乏清晰认知。当前学院的常见做法是：辅导员/班主任手工导出全班选课与积分情况，再在 QQ/微信群里通知谁还差什么。这种方式存在明显问题：

- **滞后**：通常只在大三、大四才大规模核对，错过最佳补修窗口。
- **低效**：每学期人工导出、人工核对，工作量巨大。
- **易错**：培养方案分类繁多（必修 / 限选 / 任选 / 通识 / 实践 / 创新创业 …），人工比对容易遗漏。
- **被动**：学生本人很少主动去关注完成情况，等到毕业季才发现学分不够，被迫补修甚至延期毕业。

**EduGuard-AI** 的目标，是把这套流程自动化、智能化：

> 自动对比 培养方案 ↔ 学生成绩 → 分阶段生成预警 → 多渠道主动通知学生与辅导员 → 提供 AI 对话式答疑。

## 二、核心特性

- 📊 **培养方案数字化**：将各专业培养方案录入系统，按学分类别（必修/限选/任选/通识/实践等）拆分要求。
- 📥 **教务数据接入**：支持 CSV/Excel 批量导入学生成绩与选课信息，后续可对接教务系统 API。
- ⚖️ **自动比对引擎**：分桶累计已修/在修学分，按分类输出缺口及推荐课程。
- 🚨 **分阶段预警**：在每学期末按完成度生成 `提示 / 警告 / 严重` 三档预警。
- 🔔 **多渠道通知**：站内消息、邮件、企业微信/钉钉机器人、短信，**可在后台自由配置切换**。
- 🤖 **AI 学业问答**：学生可对话式询问"我还差什么没修？""下学期建议选什么？"，基于个人上下文 + 培养方案进行回答。
- 👥 **多角色**：学生、辅导员/班主任、教学管理员，权限分级。

## 三、技术架构

**单体架构，前后端分离**：一个前端 + 一个后端 + 一个数据库，`docker-compose` 一键启动。

```
┌────────────────┐         HTTPS         ┌─────────────────────┐         ┌──────────────┐
│  Vue3 前端     │  ───────────────────▶ │   FastAPI 后端       │ ──────▶ │ PostgreSQL    │
│  (Element Plus)│  ◀───────────────────  │  (SQLAlchemy/Alembic)│         └──────────────┘
└────────────────┘         JSON          │   ├─ 比对引擎         │
                                          │   ├─ 预警调度         │
                                          │   ├─ 通知中心 ───────┐│         ┌──────────────┐
                                          │   └─ AI 学业问答 ────┼┼──────▶ │ LLM Provider  │
                                          └─────────────────────┘│         └──────────────┘
                                                                  │
                                                  ┌───────────────┼────────────────┐
                                                  ▼               ▼                ▼
                                              邮件 SMTP      企业微信/钉钉机器人    短信网关
```

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 · Vite · TypeScript · Element Plus · Pinia · Vue Router |
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 |
| 数据库 | PostgreSQL 15 |
| AI | OpenAI 兼容协议（可切换 DeepSeek / 通义千问 / Claude 等） |
| 通知 | SMTP · 企业微信机器人 · 钉钉机器人 · 阿里云短信（占位） |
| 部署 | Docker · docker-compose |

## 四、目录结构

```
edu-guard-ai/
├── backend/        FastAPI 后端
│   └── app/
│       ├── api/v1/       REST 路由
│       ├── core/         配置、数据库、安全
│       ├── models/       ORM 模型
│       ├── schemas/      Pydantic Schema
│       ├── services/     业务服务（比对/预警/通知分发）
│       ├── ai/           LLM 客户端与 Prompt
│       └── notifiers/    各渠道通知适配器
├── frontend/       Vue3 前端
│   └── src/
│       ├── api/          后端接口封装
│       ├── views/        登录 / 工作台 / 预警详情 / AI 问答 / 管理后台
│       ├── components/   通用组件
│       ├── stores/       Pinia
│       └── router/       路由
├── docs/           设计文档（架构、数据模型、路线图）
└── docker-compose.yml
```

## 五、快速开始

### 环境要求

- Node.js ≥ 18
- Python ≥ 3.11
- PostgreSQL ≥ 15（或直接用 docker-compose 起）
- Docker（可选）

### 方式一：docker-compose 一键起（推荐）

```bash
git clone https://github.com/kinghy949/edu-guard-ai.git
cd edu-guard-ai
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up -d
# 前端: http://localhost:5173   后端: http://localhost:8000/docs
```

### 方式二：本地分别启动

后端：

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## 六、路线图

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M0 | 仓库初始化 + 架构骨架 | ✅ |
| M1 | 数据模型 + 教务导入 + 基础 CRUD | ✅ |
| M2 | 培养方案比对引擎 + 预警生成 | ✅ |
| M3 | 通知中心（邮件 / 企微 / 钉钉 / 短信） | ⏳ |
| M4 | AI 学业问答 | ⏳ |
| M5 | 管理后台 + 权限 + 部署文档 | ⏳ |

详见 [`docs/roadmap.md`](docs/roadmap.md)。

## 七、文档

- [架构说明](docs/architecture.md)
- [数据模型](docs/data-model.md)
- [路线图](docs/roadmap.md)

## 八、贡献

欢迎 Issue / PR。本项目为公益性教育工具，不收集任何商业目的的学生数据，部署方需自行确保数据合规。

## 九、License

[MIT](LICENSE)

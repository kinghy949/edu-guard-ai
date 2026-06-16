# 部署指南

## 开发模式（带热更新）

```bash
cp backend/.env.example backend/.env     # 配好 DATABASE_URL / LLM_API_KEY
cp frontend/.env.example frontend/.env
docker compose up -d
# 前端 http://localhost:5173  后端 http://localhost:8000/docs
```

## 生产模式（单机 docker-compose）

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env：
#  - APP_ENV=prod            # 启动前会校验 SECRET_KEY 强度，弱密钥直接拒绝启动
#  - SECRET_KEY=$(openssl rand -hex 32)  # 必须 ≥ 32 字符
#  - CORS_ORIGINS=https://eduguard.example.edu.cn   # 列出真实前端域名，禁止使用 *
#  - DATABASE_URL=postgresql+psycopg://eduguard:<强密码>@db:5432/eduguard
#  - LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

docker compose -f docker-compose.prod.yml up -d --build
# 国内服务器构建慢可加: PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple docker compose -f docker-compose.prod.yml build
# 前端经 nginx 暴露 80 端口，并把 /api/ 反代到 backend:8000
#
# 后端启动时自动：
#   1) alembic upgrade head （建表 / 升级到最新版本）
#   2) python -m scripts.bootstrap （幂等）
#        - 库内无用户时按 BOOTSTRAP_ADMIN_* 创建默认管理员
#        - 若 SEED_DEMO=true 且无任何培养方案则导入演示数据
#   3) 启动 uvicorn
#
# 如需自定义首次管理员账号或关闭演示数据，部署前编辑 backend/.env：
#   BOOTSTRAP_ADMIN_USERNAME=admin
#   BOOTSTRAP_ADMIN_PASSWORD=<强密码>
#   SEED_DEMO=false   # 生产建议关掉，避免引入测试数据
```

打开 `http://<server-ip>/` 即可访问；默认账号 `admin / admin123`（务必首次部署前改密码）。

## 演示数据

`SEED_DEMO=true` 时首次启动会自动生成：3 个培养方案、97 门课程、25 名学生、1 名辅导员、24 条预警（含已处理）、通知与 AI 会话样例。
后续启动不会重复导入。手动重新执行：

```bash
docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_demo
```

## 反向代理与 HTTPS

生产建议在前端 nginx 前再套一层网关（Caddy / Traefik / 云厂商 SLB）配 HTTPS。本仓库内置 nginx 仅做静态托管 + 后端反代，未启用 TLS。

## 备份

- 数据库：`docker compose exec db pg_dump -U eduguard eduguard > backup.sql`
- 卷：`pgdata` 命名卷，直接挂载到外部目录或者定时 `pg_dump` 上传对象存储

## 升级

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

迁移自动随后端启动执行（`alembic upgrade head`）。

## 环境变量速查

后端：见 `backend/.env.example`，主要是 `DATABASE_URL`、`SECRET_KEY`、`LLM_*`。

前端构建时：`VITE_API_BASE` 默认 `/api/v1`，与 nginx 反代路径一致，通常无需改动。

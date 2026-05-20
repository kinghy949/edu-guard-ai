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
#  - SECRET_KEY 改为长随机串
#  - DATABASE_URL=postgresql+psycopg://eduguard:<强密码>@db:5432/eduguard
#  - LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

docker compose -f docker-compose.prod.yml up -d --build
# 前端经 nginx 暴露 80 端口，并把 /api/ 反代到 backend:8000
# 启动时自动执行 alembic upgrade head

# 创建初始管理员
docker compose -f docker-compose.prod.yml exec backend python -m scripts.create_admin admin <strong-password>
```

打开 `http://<server-ip>/` 即可访问，登录后台后导入数据。

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

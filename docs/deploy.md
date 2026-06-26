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
#  - ENCRYPTION_KEY=<Fernet key>         # 生产必填，用于加密 LLM/通知敏感配置
#  - CORS_ORIGINS=https://eduguard.example.edu.cn   # 列出真实前端域名，禁止使用 *
#  - DATABASE_URL=postgresql+psycopg://eduguard:<强密码>@db:5432/eduguard
#  - LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / CHAT_DAILY_MESSAGE_LIMIT

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

生产必须启用 HTTPS。以下示例以 Ubuntu + nginx + certbot 为准，域名示例为
`eduguard.example.edu.cn`，请替换为学校实际域名。

### 1. DNS 与防火墙

确认域名 A/AAAA 记录已指向服务器公网 IP，安全组放行 80/443。

生产若使用宿主机 nginx 统一处理 TLS，请先把 `docker-compose.prod.yml`
中 frontend 的端口改为仅监听本机 8080，避免容器占用宿主 80：

```yaml
frontend:
  ports:
    - "127.0.0.1:8080:80"
```

### 2. 安装 nginx 与 certbot

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 3. 先配置 HTTP 反向代理

`/etc/nginx/sites-available/eduguard.conf`：

```nginx
server {
    listen 80;
    server_name eduguard.example.edu.cn;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用并检查：

```bash
sudo ln -sf /etc/nginx/sites-available/eduguard.conf /etc/nginx/sites-enabled/eduguard.conf
sudo nginx -t
sudo systemctl reload nginx
```

### 4. 签发证书并强制 80 跳 443

```bash
sudo certbot --nginx -d eduguard.example.edu.cn --redirect
sudo certbot renew --dry-run
```

`--redirect` 会把 HTTP 自动改为 301 跳转 HTTPS。签发后确认：

```bash
curl -I http://eduguard.example.edu.cn
curl -I https://eduguard.example.edu.cn
```

生产 `.env` 中的 CORS 必须同步改为 HTTPS 域名：

```bash
CORS_ORIGINS=https://eduguard.example.edu.cn
```

## 环境变量清单

后端读取 `backend/.env`，生产请至少检查下表。完整样例见 `backend/.env.example`。

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `APP_NAME` | 否 | 应用名称，默认 `EduGuard-AI` |
| `APP_ENV` | 是 | 生产设为 `prod`，会启用强密钥校验 |
| `SECRET_KEY` | 是 | JWT 签名密钥，生产用 `openssl rand -hex 32` 生成 |
| `ENCRYPTION_KEY` | 是 | Fernet 密钥，生产必须显式设置 |
| `CORS_ORIGINS` | 是 | 前端 HTTPS 来源，逗号分隔或 JSON 数组 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | 登录 token 有效期，默认 1440 |
| `LOGIN_MAX_FAILED` | 否 | 账号锁定前允许失败次数 |
| `LOGIN_LOCK_MINUTES` | 否 | 登录失败锁定分钟数 |
| `LOGIN_IP_RATE_LIMIT` | 否 | 单 IP 每分钟登录请求上限，0 关闭 |
| `DATABASE_URL` | 是 | PostgreSQL 连接串 |
| `LLM_BASE_URL` | 是 | OpenAI 兼容 API 根地址 |
| `LLM_API_KEY` | 否 | 可先留空，后续在管理后台配置 |
| `LLM_MODEL` | 是 | 默认模型 |
| `LLM_MAX_CONTEXT_TOKENS` | 否 | AI 上下文估算 token 上限 |
| `CHAT_DAILY_MESSAGE_LIMIT` | 否 | 每用户每日 AI 消息上限，0 不限 |
| `SMTP_ENABLED` / `WECOM_ENABLED` / `DINGTALK_ENABLED` / `SMS_ENABLED` | 否 | 兼容旧配置；实际渠道配置以管理后台 DB 配置为准 |

密钥生成：

```bash
openssl rand -hex 32
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

前端构建时：`VITE_API_BASE` 默认 `/api/v1`，与 nginx 反代路径一致，通常无需改动。

## 首次上线 checklist

1. 修改 `backend/.env`：`APP_ENV=prod`、强 `SECRET_KEY`、显式 `ENCRYPTION_KEY`、真实 `CORS_ORIGINS`、强数据库密码、`SEED_DEMO=false`。
2. `docker compose -f docker-compose.prod.yml up -d --build`，确认 `docker compose -f docker-compose.prod.yml ps` 中 db/backend/frontend 均 healthy/running。
3. 登录管理员账号，立即修改默认密码。
4. 管理后台配置 LLM 与通知渠道，使用“测试连通/测试发送”验证。
5. 批量导入：字段映射模板 → dry-run 预检 → 下载错误报告修正 → 确认导入。
6. 配置预警规则与定时自动预警，手动运行一次并检查 `job_runs`。
7. 配置备份 crontab，执行一次 `scripts/db_backup.sh`，确认 `backups/` 下生成 dump。
8. 用学生账号验证：学业地图、消息中心、AI 问答、预警详情均可访问。

## 备份

```bash
scripts/db_backup.sh
```

脚本生成 `backups/eduguard_YYYYmmdd_HHMM.dump`，默认保留最近 14 份。定时 crontab 与恢复演练步骤见
[`docs/operations.md`](operations.md)。

## 升级

升级前先备份：

```bash
scripts/db_backup.sh
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1/health
```

迁移自动随后端启动执行（`alembic upgrade head`）。如启动失败，优先查看：

```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

## 回滚

若新版本发布后出现不可接受问题：

```bash
docker compose -f docker-compose.prod.yml stop backend frontend
git checkout <上一稳定提交或 tag>
docker compose -f docker-compose.prod.yml up -d --build backend frontend
```

若数据库迁移已经写入且需要回到备份时点：

```bash
docker compose -f docker-compose.prod.yml stop backend frontend
scripts/db_restore.sh backups/eduguard_YYYYmmdd_HHMM.dump
docker compose -f docker-compose.prod.yml up -d backend frontend
```

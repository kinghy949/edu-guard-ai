# CentOS 公网服务器部署指南（2C2G 实战）

适用：CentOS 7 / 8 / Stream，2 核 2G 内存的云服务器，已预装 Docker。通过公网 IP 直接访问。

> 2G 内存属于"刚够用"，必须先加 swap 防止前端构建被 OOM kill。
> 实测最低耗时约 8–15 分钟（取决于网络）。

---

## 一、上传代码并解压

适用于"从 GitHub 下载 ZIP 包 → 上传到服务器"的场景（无 SSH key 直接 clone 时）。

### 1.1 上传

本地 Mac/Win 把 `edu-guard-ai-main.zip` 通过 scp / rz / OSS / 云控制台文件管理传到服务器，比如 `/root/edu-guard-ai-main.zip`。

### 1.2 解压

```bash
# CentOS 默认可能没有 unzip
sudo yum -y install unzip

cd /opt
sudo unzip ~/edu-guard-ai-main.zip   # 路径换成你实际的 zip 路径

# GitHub 的 zip 默认带 -main 后缀，重命名清爽
sudo mv edu-guard-ai-main edu-guard-ai
cd edu-guard-ai
ls   # 应看到 backend/ frontend/ docker-compose.prod.yml docs/ 等
```

或者用 `git clone` 替代上面两步（推荐，后续 `git pull` 升级方便）：

```bash
sudo yum -y install git
cd /opt
sudo git clone https://github.com/kinghy949/edu-guard-ai.git
cd edu-guard-ai
```

---

## 二、服务器准备（一次性）

### 2.1 加 2G swap（**关键**，防止 OOM）

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h    # 验证已生效，Swap 那行应有 2G
```

### 2.2 装 docker compose 插件

```bash
docker compose version || sudo yum -y install docker-compose-plugin
```

若仓库源里没有，独立版安装：

```bash
sudo curl -L https://github.com/docker/compose/releases/download/v2.29.0/docker-compose-linux-x86_64 \
     -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
# 注意：独立版命令是 `docker-compose`（带横线），下文若提示找不到 `docker compose`，请相应替换
```

### 2.3 配置镜像加速器（国内必备）

Docker Hub 在国内常拉不动 `postgres:15-alpine` / `nginx:1.27-alpine` 等基础镜像。

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run",
    "https://dockerproxy.com"
  ]
}
EOF
sudo systemctl restart docker
docker info | grep -A4 "Registry Mirrors"   # 验证生效
```

### 2.4 开放 80 端口

```bash
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --reload
```

> ⚠️ **云厂商安全组**：阿里云 / 腾讯云 / 华为云控制台 → 安全组 / 防火墙 → 入方向规则 → 加 TCP/80。
> 即使服务器内防火墙放行了，云端安全组不开外部仍然访问不到。

---

## 三、配置环境变量

```bash
cd /opt/edu-guard-ai
sudo cp backend/.env.example backend/.env
sudo vi backend/.env
```

至少修改以下几项：

```env
# 强随机串，用 openssl rand -base64 48 生成
SECRET_KEY=<生成的随机串>

# 数据库连接，密码与 docker-compose.prod.yml 的 POSTGRES_PASSWORD 保持一致
DATABASE_URL=postgresql+psycopg://eduguard:<DB强密码>@db:5432/eduguard

# 首次部署管理员账号（容器启动时由 bootstrap 自动创建）
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=<管理员强密码>
BOOTSTRAP_ADMIN_EMAIL=admin@your-school.edu.cn

# 是否自动注入演示数据
#   true  → 27 个账号 + 3 个培养方案 + 97 课程 + 25 学生 + 24 预警
#   false → 仅创建管理员（生产推荐）
SEED_DEMO=true

# LLM（可选；部署后也可在 管理后台 → AI 模型 在线改）
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxxxxxxxxxxx
LLM_MODEL=qwen-turbo
```

同步 `docker-compose.prod.yml` 顶层的 `POSTGRES_PASSWORD`，或在 shell 里 `export POSTGRES_PASSWORD=...`（compose 会读取）。

---

## 四、构建并启动

```bash
# 国内构建用清华 pip 镜像，加速 backend 镜像构建
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  sudo -E docker compose -f docker-compose.prod.yml build

sudo docker compose -f docker-compose.prod.yml up -d

# 跟踪启动日志，等到 Uvicorn running 出现
sudo docker compose -f docker-compose.prod.yml logs -f backend
```

正常输出（首次部署应看到）：

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial schema
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, llm config table
[bootstrap] 创建默认管理员: admin
[bootstrap] 开始导入演示数据 ...      # 若 SEED_DEMO=true
✅ 培养方案 3，课程 97
✅ 学生 25（含成绩）
✅ 新增预警: {'info': 2, 'warn': 18, 'severe': 4}
INFO:     Uvicorn running on http://0.0.0.0:8000
```

`Ctrl+C` 退出日志跟踪（容器继续在后台运行）。

---

## 五、验证

```bash
# 服务器本机
curl http://localhost/api/v1/ping         # {"pong":true}
curl -I http://localhost/                 # HTTP/1.1 200 OK
```

浏览器访问 `http://<服务器公网IP>/`：
- 用 `BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD` 登录
- 进 **管理后台 → AI 模型** 检查 LLM 配置（可现场切换）
- 进 **管理后台 → 通知渠道** 配置邮件（详见 `operations.md`）

---

## 六、若内存不够，构建失败（OOM）

2G 内存 + 2G swap 一般够。若仍报 `JavaScript heap out of memory` 或被 kill：

### 方案 A：限制 Node 内存 + 跳过类型检查（最快）

编辑 `frontend/Dockerfile.prod`：

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
ENV NODE_OPTIONS=--max-old-space-size=1024
COPY package.json ./
RUN npm install
COPY . .
RUN npx vite build           # 替代 npm run build，省掉 vue-tsc 占用
```

省约 500MB 内存。重新 `docker compose build`。

### 方案 B：本地构建好镜像传到服务器

```bash
# 本地（你的 Mac，有充足内存）
docker compose -f docker-compose.prod.yml build
docker save edu-guard-ai-backend edu-guard-ai-frontend | gzip > images.tgz

# 传到服务器
scp images.tgz user@server:/opt/edu-guard-ai/

# 服务器加载并启动（跳过 build）
gunzip -c images.tgz | sudo docker load
sudo docker compose -f docker-compose.prod.yml up -d --no-build
```

---

## 七、可选：上 HTTPS

申请了域名后推荐套一层 Caddy（自动签 Let's Encrypt 证书）：

新建 `caddy/Caddyfile`：

```caddy
yourdomain.com {
  reverse_proxy frontend:80
}
```

`docker-compose.prod.yml` 加一个 `caddy` 服务，监听 80/443，把现在 `frontend` 的端口映射改成只暴露给 caddy。详细 patch 文件按需求生成。

云厂商安全组需再加 443 入站。

---

## 八、日常运维

```bash
cd /opt/edu-guard-ai

# 查看状态
sudo docker compose -f docker-compose.prod.yml ps

# 查看日志
sudo docker compose -f docker-compose.prod.yml logs -f backend

# 重启
sudo docker compose -f docker-compose.prod.yml restart backend

# 升级（如果用 git clone 的方式）
sudo git pull
sudo docker compose -f docker-compose.prod.yml up -d --build

# 备份数据库
sudo docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U eduguard eduguard > backup-$(date +%F).sql

# 还原
cat backup-2026-05-21.sql | sudo docker compose -f docker-compose.prod.yml \
  exec -T db psql -U eduguard eduguard

# 完全重置（清数据卷重建演示数据）
sudo docker compose -f docker-compose.prod.yml down -v
sudo docker compose -f docker-compose.prod.yml up -d
```

更多运维细节见 [`operations.md`](operations.md)。

---

## 九、常见问题速查

| 现象 | 原因 / 解决 |
| --- | --- |
| `failed to resolve reference docker.io/...` | 镜像源没配好或失效，参考 §2.3 换源 |
| `EOF` / SSL 错误 | 网络抖动，重试 build；或换其他镜像源 |
| 浏览器访问超时 | 云安全组没开 80，参考 §2.4 |
| `Connection refused` 但 80 已开 | 容器没起来，`docker compose ps` 看状态 |
| 后端 `Connection refused @ db:5432` | DB 还没 healthy；compose 里已有 healthcheck，等几秒会自动重试 |
| `password cannot be longer than 72 bytes` | bcrypt 版本冲突，已在 `pyproject.toml` 锁定 `<4.1`，新构建即可 |
| `JavaScript heap out of memory` | 2G 内存 + swap 仍不够，按 §6 方案 A 跳类型检查 |
| AI 问答返回 "未配置 LLM API Key" | DB 和 .env 都没配，去 管理后台 → AI 模型 填入凭据 |
